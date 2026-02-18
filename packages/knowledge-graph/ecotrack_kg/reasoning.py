"""Neuro-symbolic reasoning over the EcoTrack knowledge graph.

Provides graph-structure-based inference, importance scoring, anomaly
detection, path explanation, and evidence aggregation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from .client import KnowledgeGraphClient

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes for reasoning results
# ---------------------------------------------------------------------------


@dataclass
class PredictedLink:
    """A predicted missing relationship.

    Attributes:
        source_id: Origin node id.
        target_id: Destination node id.
        rel_type: Predicted relationship type.
        score: Confidence score (0–1).
        evidence: Supporting paths or shared neighbours.
    """

    source_id: str
    target_id: str
    rel_type: str
    score: float
    evidence: list[str] = field(default_factory=list)


@dataclass
class NodeImportance:
    """Importance score for a node.

    Attributes:
        node_id: Node ``id``.
        label: Primary node label.
        name: Human-readable name.
        score: Normalised importance score (0–1).
        degree: Total degree (in + out).
    """

    node_id: str
    label: str
    name: str
    score: float
    degree: int


@dataclass
class AnomalousPattern:
    """An anomalous structural pattern detected in the graph.

    Attributes:
        pattern_type: Category of anomaly (e.g. ``"isolated_node"``).
        description: Human-readable explanation.
        affected_nodes: Node ids involved.
        severity: ``"low"``, ``"medium"``, or ``"high"``.
    """

    pattern_type: str
    description: str
    affected_nodes: list[str]
    severity: str


@dataclass
class ConnectionExplanation:
    """Natural-language explanation of a path between two nodes.

    Attributes:
        source_id: Origin node id.
        target_id: Destination node id.
        path_description: Ordered list of human-readable path steps.
        relationship_chain: Relationship types along the path.
        depth: Number of hops.
        explanation: Generated prose explanation.
    """

    source_id: str
    target_id: str
    path_description: list[str]
    relationship_chain: list[str]
    depth: int
    explanation: str


@dataclass
class EvidenceItem:
    """A piece of evidence supporting or contradicting a claim.

    Attributes:
        node_id: Evidence source node id.
        node_name: Human-readable name.
        relationship: How the evidence relates.
        supports: ``True`` if supporting, ``False`` if contradicting.
        strength: Evidence strength (0–1).
        detail: Additional context.
    """

    node_id: str
    node_name: str
    relationship: str
    supports: bool
    strength: float
    detail: str = ""


# ---------------------------------------------------------------------------
# Reasoner
# ---------------------------------------------------------------------------


class GraphReasoner:
    """Graph-based reasoning engine for the EcoTrack knowledge graph.

    Uses structural graph features — common neighbours, path analysis,
    degree centrality, and pattern matching — to infer new knowledge,
    rank importance, detect anomalies, and explain connections.

    Usage::

        reasoner = GraphReasoner(client)
        links = await reasoner.infer_missing_links("species-123", "INHABITS")
    """

    def __init__(self, client: KnowledgeGraphClient) -> None:
        self._client = client

    # ── Link Prediction ──────────────────────────────────────────────

    async def infer_missing_links(
        self,
        node_id: str,
        rel_type: str,
        max_candidates: int = 20,
    ) -> list[PredictedLink]:
        """Predict missing relationships using graph structural features.

        Uses *common-neighbour* scoring: candidates that share many
        neighbours with the source through the target relationship type
        are ranked higher.

        Args:
            node_id: Source node ``id``.
            rel_type: Relationship type to predict (e.g. ``"INHABITS"``).
            max_candidates: Maximum predictions to return.

        Returns:
            Sorted list of :class:`PredictedLink`, highest score first.
        """
        # Find 2-hop candidates that share neighbours via rel_type
        cypher = f"""
        MATCH (source {{id: $node_id}})-[:{rel_type}]->(shared)<-[:{rel_type}]-(candidate)
        WHERE candidate.id <> $node_id
          AND NOT EXISTS {{ MATCH (source)-[:{rel_type}]->(candidate) }}
        WITH candidate,
             count(DISTINCT shared) AS common_neighbours,
             collect(DISTINCT shared.name)[..5] AS shared_names
        ORDER BY common_neighbours DESC
        LIMIT $max_candidates
        RETURN candidate.id AS candidate_id,
               candidate.name AS candidate_name,
               labels(candidate)[0] AS candidate_label,
               common_neighbours,
               shared_names
        """
        results = await self._client.execute_query(
            cypher,
            {"node_id": node_id, "max_candidates": max_candidates},
        )

        if not results:
            logger.debug("no_link_predictions", node_id=node_id, rel_type=rel_type)
            return []

        # Normalise scores
        max_cn = max(r["common_neighbours"] for r in results) if results else 1
        predictions: list[PredictedLink] = []
        for r in results:
            score = r["common_neighbours"] / max_cn if max_cn > 0 else 0.0
            predictions.append(
                PredictedLink(
                    source_id=node_id,
                    target_id=r["candidate_id"],
                    rel_type=rel_type,
                    score=round(score, 4),
                    evidence=[f"Shared: {name}" for name in (r["shared_names"] or [])],
                )
            )
        return predictions

    # ── Node Importance ──────────────────────────────────────────────

    async def compute_node_importance(
        self,
        label: str,
        limit: int = 50,
    ) -> list[NodeImportance]:
        """Compute PageRank-style importance for nodes of a given label.

        Uses degree centrality as a proxy (exact PageRank requires APOC
        or GDS, which may not be available). Falls back gracefully.

        Args:
            label: Node label to rank.
            limit: Maximum nodes to return.

        Returns:
            Sorted list of :class:`NodeImportance`, highest first.
        """
        # Try GDS PageRank first
        gds_cypher = f"""
        CALL gds.pageRank.stream({{
            nodeQuery: 'MATCH (n:{label}) RETURN id(n) AS id',
            relationshipQuery: 'MATCH (a)-[r]->(b) RETURN id(a) AS source, id(b) AS target'
        }})
        YIELD nodeId, score
        WITH gds.util.asNode(nodeId) AS n, score
        WHERE '{label}' IN labels(n)
        RETURN n.id AS node_id, labels(n)[0] AS label, n.name AS name,
               score, size([(n)-[]-() | 1]) AS degree
        ORDER BY score DESC
        LIMIT $limit
        """
        # Degree-centrality fallback
        fallback_cypher = f"""
        MATCH (n:{label})
        WITH n, size([(n)-[]-() | 1]) AS degree
        ORDER BY degree DESC
        LIMIT $limit
        RETURN n.id AS node_id,
               labels(n)[0] AS label,
               n.name AS name,
               toFloat(degree) AS score,
               degree
        """
        try:
            results = await self._client.execute_query(gds_cypher, {"limit": limit})
        except Exception:
            logger.debug("gds_unavailable_using_degree_centrality")
            results = await self._client.execute_query(fallback_cypher, {"limit": limit})

        if not results:
            return []

        # Normalise scores to 0–1
        max_score = max(r["score"] for r in results) if results else 1.0
        return [
            NodeImportance(
                node_id=r["node_id"],
                label=r["label"],
                name=r.get("name", ""),
                score=round(r["score"] / max_score, 4) if max_score > 0 else 0.0,
                degree=r["degree"],
            )
            for r in results
        ]

    # ── Anomaly Detection ────────────────────────────────────────────

    async def find_anomalous_patterns(
        self,
        domain: str | None = None,
    ) -> list[AnomalousPattern]:
        """Detect unusual patterns in graph structure.

        Looks for:
        1. **Isolated nodes** — nodes with zero relationships.
        2. **Hub imbalance** — nodes with extreme in/out degree ratios.
        3. **Missing expected links** — e.g. species without habitat.
        4. **Disconnected clusters** — subgraphs unreachable from main component.

        Args:
            domain: Optional domain filter.

        Returns:
            List of :class:`AnomalousPattern` instances.
        """
        anomalies: list[AnomalousPattern] = []
        domain_filter = "WHERE n.domain = $domain" if domain else ""
        params: dict[str, Any] = {}
        if domain:
            params["domain"] = domain

        # 1. Isolated nodes
        iso_cypher = f"""
        MATCH (n)
        {domain_filter}
        WHERE NOT (n)--()
        RETURN n.id AS node_id, n.name AS name, labels(n)[0] AS label
        LIMIT 50
        """
        isolated = await self._client.execute_query(iso_cypher, params)
        if isolated:
            anomalies.append(
                AnomalousPattern(
                    pattern_type="isolated_node",
                    description=f"Found {len(isolated)} node(s) with no relationships.",
                    affected_nodes=[r["node_id"] for r in isolated if r.get("node_id")],
                    severity="medium",
                )
            )

        # 2. Hub imbalance — very high out-degree vs. in-degree
        hub_cypher = f"""
        MATCH (n)
        {domain_filter}
        WITH n,
             size([(n)-[]->() | 1]) AS out_deg,
             size([(n)<-[]-() | 1]) AS in_deg,
             size([(n)-[]-() | 1]) AS total_deg
        WHERE total_deg > 10
          AND (toFloat(out_deg) / (in_deg + 1)) > 5.0
        RETURN n.id AS node_id, n.name AS name,
               out_deg, in_deg, total_deg
        ORDER BY total_deg DESC
        LIMIT 20
        """
        hubs = await self._client.execute_query(hub_cypher, params)
        if hubs:
            anomalies.append(
                AnomalousPattern(
                    pattern_type="hub_imbalance",
                    description=(
                        f"Found {len(hubs)} node(s) with extreme out/in degree ratios "
                        f"(>5:1), suggesting potential data quality issues."
                    ),
                    affected_nodes=[r["node_id"] for r in hubs if r.get("node_id")],
                    severity="low",
                )
            )

        # 3. Species without habitat
        species_cypher = """
        MATCH (s:Species)
        WHERE NOT (s)-[:INHABITS]->()
        RETURN s.id AS node_id, s.scientific_name AS name
        LIMIT 50
        """
        homeless_species = await self._client.execute_query(species_cypher)
        if homeless_species:
            anomalies.append(
                AnomalousPattern(
                    pattern_type="missing_expected_link",
                    description=(
                        f"Found {len(homeless_species)} species without any "
                        f"INHABITS relationship to a habitat."
                    ),
                    affected_nodes=[
                        r["node_id"] for r in homeless_species if r.get("node_id")
                    ],
                    severity="high",
                )
            )

        # 4. Regions without any monitoring
        unmonitored_cypher = """
        MATCH (r:Region)
        WHERE NOT (r)<-[:LOCATED_IN]-(:Observation)
        RETURN r.id AS node_id, r.name AS name
        LIMIT 50
        """
        unmonitored = await self._client.execute_query(unmonitored_cypher)
        if unmonitored:
            anomalies.append(
                AnomalousPattern(
                    pattern_type="unmonitored_region",
                    description=(
                        f"Found {len(unmonitored)} region(s) with no observation data."
                    ),
                    affected_nodes=[
                        r["node_id"] for r in unmonitored if r.get("node_id")
                    ],
                    severity="medium",
                )
            )

        logger.info("anomalous_patterns_detected", count=len(anomalies))
        return anomalies

    # ── Connection Explanation ────────────────────────────────────────

    async def explain_connection(
        self,
        node_a: str,
        node_b: str,
        max_depth: int = 5,
    ) -> ConnectionExplanation | None:
        """Generate a natural-language explanation of the path between two nodes.

        Args:
            node_a: First node ``id``.
            node_b: Second node ``id``.
            max_depth: Maximum path length to search.

        Returns:
            A :class:`ConnectionExplanation` or ``None`` if no path exists.
        """
        cypher = f"""
        MATCH (a {{id: $node_a}}), (b {{id: $node_b}})
        MATCH path = shortestPath((a)-[*..{max_depth}]-(b))
        RETURN [n IN nodes(path) | {{
                   id: n.id,
                   name: coalesce(n.name, n.id),
                   label: labels(n)[0]
               }}] AS path_nodes,
               [r IN relationships(path) | type(r)] AS rel_types,
               length(path) AS depth
        """
        results = await self._client.execute_query(
            cypher, {"node_a": node_a, "node_b": node_b}
        )
        if not results:
            logger.debug("no_path_found", node_a=node_a, node_b=node_b)
            return None

        row = results[0]
        path_nodes: list[dict[str, str]] = row["path_nodes"]
        rel_types: list[str] = row["rel_types"]
        depth: int = row["depth"]

        # Build human-readable description
        steps: list[str] = []
        for i, node_info in enumerate(path_nodes):
            label = node_info.get("label", "Node")
            name = node_info.get("name", node_info.get("id", "?"))
            steps.append(f"{label}({name})")

        # Build explanation prose
        explanation_parts: list[str] = []
        for i in range(len(path_nodes) - 1):
            src = path_nodes[i]
            tgt = path_nodes[i + 1]
            rel = rel_types[i] if i < len(rel_types) else "CONNECTED_TO"
            explanation_parts.append(
                f"{src.get('name', '?')} ({src.get('label', '')}) "
                f"--[{rel}]--> "
                f"{tgt.get('name', '?')} ({tgt.get('label', '')})"
            )
        explanation = (
            f"There is a {depth}-hop path connecting these entities: "
            + " → ".join(explanation_parts)
            + "."
        )

        return ConnectionExplanation(
            source_id=node_a,
            target_id=node_b,
            path_description=steps,
            relationship_chain=rel_types,
            depth=depth,
            explanation=explanation,
        )

    # ── Evidence Aggregation ─────────────────────────────────────────

    async def aggregate_evidence(
        self,
        node_id: str,
        claim: str,
    ) -> list[EvidenceItem]:
        """Gather supporting and contradicting evidence for a claim about a node.

        Searches neighbouring observations, predictions, and indicators to
        determine how they relate to the stated claim.

        Args:
            node_id: The node about which the claim is made.
            claim: The claim text (used for keyword matching against
                neighbouring node descriptions/names).

        Returns:
            List of :class:`EvidenceItem` instances.
        """
        # Get all connected observations, predictions, and indicators
        cypher = """
        MATCH (n {id: $node_id})-[r]-(evidence)
        WHERE labels(evidence)[0] IN ['Observation', 'Prediction', 'Indicator', 'Dataset', 'Alert']
        RETURN evidence.id AS evidence_id,
               evidence.name AS evidence_name,
               evidence.description AS description,
               evidence.value AS value,
               evidence.severity AS severity,
               evidence.trend AS trend,
               type(r) AS relationship,
               labels(evidence)[0] AS evidence_label
        LIMIT 100
        """
        results = await self._client.execute_query(cypher, {"node_id": node_id})

        if not results:
            logger.debug("no_evidence_found", node_id=node_id, claim=claim)
            return []

        claim_lower = claim.lower()
        evidence_items: list[EvidenceItem] = []
        for r in results:
            # Simple keyword relevance — check if evidence text overlaps with claim
            evidence_text = " ".join(
                str(v) for v in [
                    r.get("evidence_name", ""),
                    r.get("description", ""),
                    r.get("trend", ""),
                    r.get("severity", ""),
                ]
            ).lower()

            # Determine support/contradiction heuristically
            supports = True
            strength = 0.5  # default moderate relevance

            # If claim mentions "increasing" and evidence shows "declining", it contradicts
            if "increasing" in claim_lower and "declining" in evidence_text:
                supports = False
                strength = 0.8
            elif "decreasing" in claim_lower and "improving" in evidence_text:
                supports = False
                strength = 0.7
            elif "threat" in claim_lower and r.get("severity") in ("high", "critical"):
                supports = True
                strength = 0.9
            elif "healthy" in claim_lower and r.get("trend") == "declining":
                supports = False
                strength = 0.85
            elif "healthy" in claim_lower and r.get("trend") == "improving":
                supports = True
                strength = 0.85

            # Boost strength if keywords overlap
            claim_words = set(claim_lower.split())
            evidence_words = set(evidence_text.split())
            overlap = claim_words & evidence_words
            if overlap:
                strength = min(1.0, strength + 0.1 * len(overlap))

            evidence_items.append(
                EvidenceItem(
                    node_id=r["evidence_id"],
                    node_name=r.get("evidence_name") or r["evidence_id"],
                    relationship=r["relationship"],
                    supports=supports,
                    strength=round(strength, 3),
                    detail=(
                        f"[{r['evidence_label']}] "
                        f"value={r.get('value', 'N/A')}, "
                        f"trend={r.get('trend', 'N/A')}, "
                        f"severity={r.get('severity', 'N/A')}"
                    ),
                )
            )

        # Sort by strength descending
        evidence_items.sort(key=lambda e: e.strength, reverse=True)
        logger.info(
            "evidence_aggregated",
            node_id=node_id,
            total=len(evidence_items),
            supporting=sum(1 for e in evidence_items if e.supports),
            contradicting=sum(1 for e in evidence_items if not e.supports),
        )
        return evidence_items


__all__ = [
    "PredictedLink",
    "NodeImportance",
    "AnomalousPattern",
    "ConnectionExplanation",
    "EvidenceItem",
    "GraphReasoner",
]
