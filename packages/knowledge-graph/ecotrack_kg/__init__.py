"""EcoTrack Knowledge Graph — Environmental knowledge graph construction and querying."""
from __future__ import annotations

__version__ = "0.1.0"

from .client import KnowledgeGraphClient, Neo4jConfig
from .ontology import (
    EnvironmentalOntology,
    NodeType,
    OntologyTerm,
    RelationshipType,
    SchemaDefinition,
)
from .queries import QueryTemplates
from .builder import KnowledgeGraphBuilder
from .reasoning import (
    AnomalousPattern,
    ConnectionExplanation,
    EvidenceItem,
    GraphReasoner,
    NodeImportance,
    PredictedLink,
)

__all__ = [
    "__version__",
    # Client
    "Neo4jConfig",
    "KnowledgeGraphClient",
    # Ontology
    "NodeType",
    "RelationshipType",
    "OntologyTerm",
    "EnvironmentalOntology",
    "SchemaDefinition",
    # Queries
    "QueryTemplates",
    # Builder
    "KnowledgeGraphBuilder",
    # Reasoning
    "PredictedLink",
    "NodeImportance",
    "AnomalousPattern",
    "ConnectionExplanation",
    "EvidenceItem",
    "GraphReasoner",
]
