"""
Common modules for Confluence Q&A System

This package contains shared modules used across the project:
- config: Configuration management
- graph_models: Graph data models
- graph_operations: Graph database operations
"""

__version__ = "1.0.0"
__author__ = "Confluence Q&A Team"

# Import main classes for easy access
from .config import GraphConfig, SearchConfig, ContainerNames, NodeTypes, EdgeTypes
from .graph_models import (
    BaseNode, BaseEdge, PageNode, SpaceNode, LinkNode,
    GraphModelFactory, validate_node_data
)
from .graph_operations import GraphOperations

__all__ = [
    # Config
    "GraphConfig",
    "SearchConfig", 
    "ContainerNames",
    "NodeTypes",
    "EdgeTypes",
    
    # Models
    "BaseNode",
    "BaseEdge", 
    "PageNode",
    "SpaceNode",
    "LinkNode",
    "GraphModelFactory",
    "validate_node_data",
    
    # Operations
    "GraphOperations",
]
