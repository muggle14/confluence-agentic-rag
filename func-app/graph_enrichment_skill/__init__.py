import logging
import json
import azure.functions as func

from common.config import GraphConfig
from common.graph_operations import GraphOperations

# --- Best Practice: Initialize clients outside the main function ---
# Initialize GraphOperations without connecting immediately
cfg = GraphConfig.from_environment()
ops = GraphOperations(cfg)

async def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Azure Function to enrich a document with graph metrics from Cosmos DB.
    Triggered by the WebApiSkill in the Azure AI Search skillset.
    """
    logging.info('Graph enrichment function processed a request.')

    # Ensure database connection is established
    if not ops.client:
        try:
            logging.info("Initializing Cosmos DB connection...")
            ops.connect()
            logging.info("✅ Cosmos DB connection successful.")
        except Exception as e:
            import traceback
            logging.error(f"❌ Failed to initialize Cosmos DB connection: {e}")
            logging.error(traceback.format_exc())
            return func.HttpResponse("Database connection is not available.", status_code=500)

    # --- Input Validation ---
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON in request body.", status_code=400)

    records = body.get("values", [])
    if not records:
        return func.HttpResponse("Request body must contain 'values' array.", status_code=400)

    out_vals = []

    for rec in records:
        try:
            rid = rec["recordId"]
            pid = rec["data"].get("page_id")
            
            if not pid:
                logging.warning(f"Missing page_id in record {rid}")
                out_vals.append({
                    "recordId": rid,
                    "data": {
                        "parent_page_id": None,
                        "hierarchy_depth": 0,
                        "children_ids": [],
                        "adjacent_ids": [],
                        "graph_centrality_score": 0.0
                    }
                })
                continue

            # Get graph data
            props = ops.get_graph_props(pid)
            children = ops.get_children_ids(pid)
            siblings = ops.get_sibling_ids(pid)
            parent_id = props.get("parent_page_id")
            adjacent = list({*children, *siblings, parent_id} - {None})

            out_vals.append({
                "recordId": rid,
                "data": {
                    "parent_page_id": parent_id,
                    "hierarchy_depth": props.get("hierarchy_depth", 0),
                    "children_ids": children,
                    "adjacent_ids": adjacent,
                    "graph_centrality_score": props.get("graph_centrality_score", 0.0)
                }
            })
            
            logging.info(f"Successfully enriched page {pid} (record {rid})")

        except Exception as e:
            logging.error(f"Error processing record {rec.get('recordId', 'unknown')}: {e}")
            import traceback
            logging.error(traceback.format_exc())
            
            # Return default response for this record
            out_vals.append({
                "recordId": rec.get("recordId", "unknown"),
                "data": {
                    "parent_page_id": None,
                    "hierarchy_depth": 0,
                    "children_ids": [],
                    "adjacent_ids": [],
                    "graph_centrality_score": 0.0
                }
            })

    return func.HttpResponse(
        json.dumps({"values": out_vals}),
        mimetype="application/json",
        status_code=200
    )



