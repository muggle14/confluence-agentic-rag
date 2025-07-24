"""
graph_metrics.py  –  Compute & persist hierarchy depth, child count and PageRank‑like
centrality for Confluence Page vertices stored in Azure Cosmos DB (Gremlin API).
"""

from __future__ import annotations
import os
import logging
from typing import Dict, List, Tuple

import gremlin_python.driver.client as gp_client
import networkx as nx
from tqdm import tqdm
import json

from common.config import GraphConfig
from common.graph_operations import GraphOperations

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class GraphMetrics:
    """High‑level façade that pulls the page hierarchy into memory, computes
    metrics with *networkx*, and writes them back to Cosmos DB in batches."""

    def __init__(self, cfg: GraphConfig) -> None:
        self.cfg = cfg
        self.ops = GraphOperations(cfg)
        self.ops.connect()  # Establish connection
        self.batch_size = int(os.getenv("GRAPH_METRICS_BATCH_SIZE", 100))

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def run_all(self) -> Dict[str, int]:
        """Compute depth / child_count / centrality and persist to the graph.
        Returns a dict with counts of updated vertices."""
        logger.info("Fetching page hierarchy …")
        edges = self._fetch_parent_edges()
        logger.info("Fetched %d parent/child edges", len(edges))

        logger.info("Computing hierarchy depth & child_count …")
        depth_map, child_map = self._compute_hierarchy_metrics(edges)

        logger.info("Computing PageRank centrality …")
        centrality_map = self._compute_centrality(edges)

        logger.info("Persisting metrics back to Cosmos DB …")
        updated = self._persist_metrics(depth_map, child_map, centrality_map)
        logger.info("Updated %d Page vertices", updated)

        return {
            "pages_updated": updated,
            "unique_pages": len(depth_map)
        }

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _fetch_parent_edges(self) -> List[Tuple[str, str]]:
        """
        Returns a list of (parent_id, child_id) tuples for every ParentOf edge
        in the graph.
        """
        query = "g.E().hasLabel('ParentOf').project('p','c')" \
                ".by(outV().values('id'))" \
                ".by(inV().values('id'))"
        res = self.ops.client.submit(query).all().result()
        # res is a list of dicts: [{'p': '123', 'c': '456'}, …]
        return [(e['p'], e['c']) for e in res]

    @staticmethod
    def _compute_hierarchy_metrics(
        edges: List[Tuple[str, str]]
    ) -> Tuple[Dict[str, int], Dict[str, List[str]]]:
        """
        Builds a directed graph, roots it, and returns:
          • depth_map  : page_id -> int
          • child_ids_map  : page_id -> list of child IDs
        """
        G = nx.DiGraph()
        G.add_edges_from(edges)

        # Identify roots (pages that are never 'child' in an edge)
        children = {c for _, c in edges}
        roots = [n for n in G.nodes if n not in children]
        
        # Initialize depth_map with all nodes at depth 0
        depth_map = {n: 0 for n in G.nodes}
        
        # Compute depths from each root
        for root in roots:
            for node, depth in nx.single_source_shortest_path_length(G, root).items():
                # Only update if this path gives a deeper depth
                depth_map[node] = max(depth_map[node], depth)

        # Build child_ids_map: {parent_id: [child_id1, child_id2, ...]}
        child_ids_map = {}
        for parent_id, child_id in edges:
            child_ids_map.setdefault(parent_id, []).append(child_id)
        
        # Ensure all nodes have an entry (even if they have no children)
        for node in G.nodes:
            if node not in child_ids_map:
                child_ids_map[node] = []
        
        return depth_map, child_ids_map

    @staticmethod
    def _compute_centrality(
        edges: List[Tuple[str, str]]
    ) -> Dict[str, float]:
        """
        Run PageRank (directed) to obtain centrality scores in range [0,1].
        """
        G = nx.DiGraph()
        G.add_edges_from(edges)
        return nx.pagerank(G, alpha=0.85, max_iter=100)

    def _persist_metrics(
        self,
        depth_map: Dict[str, int],
        child_ids_map: Dict[str, List[str]],
        centrality_map: Dict[str, float]
    ) -> int:
        """
        Writes properties back to the graph in batched parallel requests.
        """
        updates = 0
        batch = []
        for pid, depth in depth_map.items():
            child_ids = child_ids_map.get(pid, [])
            child_count = len(child_ids)
            centrality = round(centrality_map.get(pid, 0.0), 6)
            stmt = (
                f"g.V('{pid}')"
                f".property('hierarchy_depth', {depth})"
                f".property('graph_centrality_score', {centrality})"
                f".property('children_ids', '{json.dumps(child_ids)}')"
                f".property('child_count', {child_count})"
            )
            batch.append(stmt)
            
            if len(batch) == self.batch_size:
                # Execute batch
                for query in batch:
                    try:
                        if self.ops.client:
                            self.ops.client.submit(query).all().result()
                            updates += 1
                    except Exception as e:
                        logger.error(f"Failed to update node: {e}")
                batch = []
                
        if batch:   # leftover
            for query in batch:
                try:
                    if self.ops.client:
                        self.ops.client.submit(query).all().result()
                        updates += 1
                except Exception as e:
                    logger.error(f"Failed to update node: {e}")
        return updates


# ---------------------------------------------------------------------- #
# CLI helper
# ---------------------------------------------------------------------- #
if __name__ == "__main__":
    cfg = GraphConfig.from_environment()
    gm = GraphMetrics(cfg)
    stats = gm.run_all()
    print(stats)