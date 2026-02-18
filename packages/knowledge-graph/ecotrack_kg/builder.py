"""Knowledge graph construction from EcoTrack domain data.

Ingests core domain model instances (climate observations, species records,
air-quality readings, etc.) and materialises them as nodes and relationships
in the Neo4j-backed knowledge graph.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import structlog

from .client import KnowledgeGraphClient
from .ontology import NodeType, RelationshipType

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _model_to_props(model: Any) -> dict[str, Any]:
    """Convert a Pydantic model to a flat Neo4j-safe property dict.

    Nested objects, ``None`` values, and non-primitive types are dropped or
    stringified so that Neo4j can store them as node properties.
    """
    raw: dict[str, Any] = {}
    try:
        raw = model.model_dump()
    except AttributeError:
        raw = dict(model) if hasattr(model, "__iter__") else {}

    props: dict[str, Any] = {}
    for key, val in raw.items():
        if val is None:
            continue
        if isinstance(val, (str, int, float, bool)):
            props[key] = val
        elif isinstance(val, datetime):
            props[key] = val.isoformat()
        elif isinstance(val, uuid.UUID):
            props[key] = str(val)
        elif isinstance(val, dict):
            # Flatten one level for simple dicts
            for sub_key, sub_val in val.items():
                if isinstance(sub_val, (str, int, float, bool)):
                    props[f"{key}_{sub_key}"] = sub_val
        elif isinstance(val, (list, tuple)):
            # Store as list if elements are primitives
            if all(isinstance(v, (str, int, float, bool)) for v in val):
                props[key] = list(val)
        else:
            props[key] = str(val)
    # Ensure an id property exists
    if "id" not in props:
        props["id"] = str(uuid.uuid4())
    else:
        props["id"] = str(props["id"])
    return props


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


class KnowledgeGraphBuilder:
    """Constructs and enriches the EcoTrack knowledge graph.

    Usage::

        async with KnowledgeGraphClient(config) as client:
            builder = KnowledgeGraphBuilder(client)
            await builder.ingest_climate_data(observations)
            await builder.build_ecosystem_graph(regions)
    """

    def __init__(self, client: KnowledgeGraphClient) -> None:
        self._client = client

    # ── Climate Data ─────────────────────────────────────────────────

    async def ingest_climate_data(
        self,
        observations: list[Any],
    ) -> dict[str, int]:
        """Create climate observation nodes and link them to regions.

        Each :class:`ClimateObservation` becomes an ``Observation`` node with
        a ``MONITORS`` relationship to the closest ``Region``.

        Args:
            observations: List of ``ClimateObservation`` model instances.

        Returns:
            Counts of nodes and relationships created.
        """
        if not observations:
            logger.warning("ingest_climate_data_empty")
            return {"nodes": 0, "relationships": 0}

        node_dicts: list[dict[str, Any]] = []
        for obs in observations:
            props = _model_to_props(obs)
            props["node_type"] = NodeType.OBSERVATION.value
            # Flatten location
            if hasattr(obs, "location") and obs.location:
                props["latitude"] = obs.location.latitude
                props["longitude"] = obs.location.longitude
                if obs.location.elevation_m is not None:
                    props["elevation_m"] = obs.location.elevation_m
            node_dicts.append(props)

        result = await self._client.bulk_create_nodes(
            NodeType.OBSERVATION.value, node_dicts
        )
        nodes_created = result.get("nodes_created", 0)
        logger.info("climate_observations_ingested", count=nodes_created)

        # Link observations to matching regions by spatial overlap
        link_cypher = """
        MATCH (obs:Observation)
        WHERE obs.domain = 'climate' AND obs.latitude IS NOT NULL
        MATCH (r:Region)
        WHERE r.min_lat <= obs.latitude AND obs.latitude <= r.max_lat
          AND r.min_lon <= obs.longitude AND obs.longitude <= r.max_lon
        MERGE (obs)-[:LOCATED_IN]->(r)
        RETURN count(*) AS linked
        """
        link_result = await self._client.execute_query(link_cypher)
        rels = link_result[0].get("linked", 0) if link_result else 0
        return {"nodes": nodes_created, "relationships": rels}

    # ── Species / Biodiversity Data ──────────────────────────────────

    async def ingest_species_data(
        self,
        species: list[Any],
        observations: list[Any] | None = None,
    ) -> dict[str, int]:
        """Create species nodes, observation nodes, and habitat relationships.

        Args:
            species: List of ``Species`` model instances.
            observations: Optional list of ``SpeciesObservation`` instances.

        Returns:
            Counts of nodes and relationships created.
        """
        total_nodes = 0
        total_rels = 0

        if species:
            species_dicts = [_model_to_props(s) for s in species]
            result = await self._client.bulk_create_nodes(
                NodeType.SPECIES.value, species_dicts
            )
            total_nodes += result.get("nodes_created", 0)

        if observations:
            obs_dicts: list[dict[str, Any]] = []
            for obs in observations:
                props = _model_to_props(obs)
                props["node_type"] = NodeType.OBSERVATION.value
                if hasattr(obs, "location") and obs.location:
                    props["latitude"] = obs.location.latitude
                    props["longitude"] = obs.location.longitude
                obs_dicts.append(props)

            result = await self._client.bulk_create_nodes(
                NodeType.OBSERVATION.value, obs_dicts
            )
            total_nodes += result.get("nodes_created", 0)

            # Link observations to species
            link_cypher = """
            MATCH (obs:Observation)
            WHERE obs.domain = 'biodiversity' AND obs.species_name IS NOT NULL
            MATCH (s:Species {scientific_name: obs.species_name})
            MERGE (obs)-[:MONITORS]->(s)
            RETURN count(*) AS linked
            """
            link_result = await self._client.execute_query(link_cypher)
            total_rels += link_result[0].get("linked", 0) if link_result else 0

        # Create INHABITS relationships between species and habitats
        inhabit_cypher = """
        MATCH (obs:Observation)-[:MONITORS]->(s:Species)
        WHERE obs.latitude IS NOT NULL
        MATCH (h:Habitat)
        WHERE h.min_lat <= obs.latitude AND obs.latitude <= h.max_lat
          AND h.min_lon <= obs.longitude AND obs.longitude <= h.max_lon
        MERGE (s)-[:INHABITS]->(h)
        RETURN count(*) AS linked
        """
        try:
            inhabit_result = await self._client.execute_query(inhabit_cypher)
            total_rels += inhabit_result[0].get("linked", 0) if inhabit_result else 0
        except Exception:
            logger.debug("habitat_linking_skipped_no_habitats")

        logger.info(
            "species_data_ingested",
            nodes=total_nodes,
            relationships=total_rels,
        )
        return {"nodes": total_nodes, "relationships": total_rels}

    # ── Air Quality Data ─────────────────────────────────────────────

    async def ingest_air_quality(
        self,
        readings: list[Any],
    ) -> dict[str, int]:
        """Create air quality reading nodes linked to locations.

        Args:
            readings: List of ``AirQualityReading`` model instances.

        Returns:
            Counts of nodes and relationships created.
        """
        if not readings:
            return {"nodes": 0, "relationships": 0}

        node_dicts: list[dict[str, Any]] = []
        for reading in readings:
            props = _model_to_props(reading)
            props["node_type"] = NodeType.OBSERVATION.value
            if hasattr(reading, "location") and reading.location:
                props["latitude"] = reading.location.latitude
                props["longitude"] = reading.location.longitude
            node_dicts.append(props)

        result = await self._client.bulk_create_nodes(
            NodeType.OBSERVATION.value, node_dicts
        )
        nodes_created = result.get("nodes_created", 0)

        # Link to regions
        link_cypher = """
        MATCH (obs:Observation)
        WHERE obs.domain = 'health' AND obs.aqi IS NOT NULL AND obs.latitude IS NOT NULL
        MATCH (r:Region)
        WHERE r.min_lat <= obs.latitude AND obs.latitude <= r.max_lat
          AND r.min_lon <= obs.longitude AND obs.longitude <= r.max_lon
        MERGE (obs)-[:LOCATED_IN]->(r)
        RETURN count(*) AS linked
        """
        link_result = await self._client.execute_query(link_cypher)
        rels = link_result[0].get("linked", 0) if link_result else 0

        # Link to pollutant nodes if they exist
        pollutant_cypher = """
        MATCH (obs:Observation)
        WHERE obs.domain = 'health' AND obs.aqi IS NOT NULL
        OPTIONAL MATCH (p:Pollutant {name: 'PM2.5'})
        WHERE obs.pm25 IS NOT NULL
        FOREACH (_ IN CASE WHEN p IS NOT NULL THEN [1] ELSE [] END |
            MERGE (obs)-[:MONITORS]->(p)
        )
        RETURN count(*) AS linked
        """
        try:
            await self._client.execute_query(pollutant_cypher)
        except Exception:
            logger.debug("pollutant_linking_skipped")

        logger.info("air_quality_ingested", nodes=nodes_created, relationships=rels)
        return {"nodes": nodes_created, "relationships": rels}

    # ── Ecosystem Graph ──────────────────────────────────────────────

    async def build_ecosystem_graph(
        self,
        regions: list[Any],
    ) -> dict[str, int]:
        """Build spatial relationships between regions.

        Creates ``Region`` nodes and ``ADJACENT_TO`` / ``PART_OF``
        relationships based on bounding-box overlap heuristics.

        Args:
            regions: List of ``GeoRegion`` model instances.

        Returns:
            Counts of nodes and relationships created.
        """
        if not regions:
            return {"nodes": 0, "relationships": 0}

        region_dicts: list[dict[str, Any]] = []
        for region in regions:
            props = _model_to_props(region)
            # Flatten geometry bbox if available
            if hasattr(region, "geometry") and isinstance(region.geometry, dict):
                coords = region.geometry.get("coordinates", [])
                if region.geometry.get("type") == "Polygon" and coords:
                    ring = coords[0] if coords else []
                    if ring:
                        lons = [p[0] for p in ring]
                        lats = [p[1] for p in ring]
                        props["min_lon"] = min(lons)
                        props["max_lon"] = max(lons)
                        props["min_lat"] = min(lats)
                        props["max_lat"] = max(lats)
            region_dicts.append(props)

        result = await self._client.bulk_create_nodes(
            NodeType.REGION.value, region_dicts
        )
        nodes_created = result.get("nodes_created", 0)

        # Create ADJACENT_TO relationships for overlapping bounding boxes
        adjacency_cypher = """
        MATCH (a:Region), (b:Region)
        WHERE a.id < b.id
          AND a.min_lon IS NOT NULL AND b.min_lon IS NOT NULL
          AND a.max_lon >= b.min_lon AND b.max_lon >= a.min_lon
          AND a.max_lat >= b.min_lat AND b.max_lat >= a.min_lat
        MERGE (a)-[:ADJACENT_TO]->(b)
        MERGE (b)-[:ADJACENT_TO]->(a)
        RETURN count(*) AS created
        """
        adj_result = await self._client.execute_query(adjacency_cypher)
        rels = adj_result[0].get("created", 0) if adj_result else 0

        logger.info(
            "ecosystem_graph_built",
            regions=nodes_created,
            adjacency_relations=rels,
        )
        return {"nodes": nodes_created, "relationships": rels}

    # ── Causal Links ─────────────────────────────────────────────────

    async def build_causal_links(
        self,
        cause_domain: str,
        effect_domain: str,
        evidence: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Create causal relationship edges between domains.

        Args:
            cause_domain: Source domain (e.g. ``"climate"``).
            effect_domain: Target domain (e.g. ``"health"``).
            evidence: List of dicts, each with ``cause_id``, ``effect_id``,
                ``strength``, and optional ``confidence`` and ``mechanism``.

        Returns:
            Count of relationships created.
        """
        if not evidence:
            return {"relationships": 0}

        rels: list[dict[str, Any]] = []
        for ev in evidence:
            rels.append({
                "from_id": str(ev["cause_id"]),
                "to_id": str(ev["effect_id"]),
                "strength": ev.get("strength", 0.0),
                "confidence": ev.get("confidence", 0.0),
                "mechanism": ev.get("mechanism", ""),
                "cause_domain": cause_domain,
                "effect_domain": effect_domain,
            })

        cypher = """
        UNWIND $rels AS rel
        MATCH (a {id: rel.from_id})
        MATCH (b {id: rel.to_id})
        CREATE (a)-[r:CAUSES {
            strength: rel.strength,
            confidence: rel.confidence,
            mechanism: rel.mechanism,
            cause_domain: rel.cause_domain,
            effect_domain: rel.effect_domain
        }]->(b)
        RETURN count(r) AS created
        """
        result = await self._client.execute_write(cypher, {"rels": rels})
        created = result.get("relationships_created", 0)
        logger.info(
            "causal_links_created",
            cause_domain=cause_domain,
            effect_domain=effect_domain,
            count=created,
        )
        return {"relationships": created}

    # ── Graph Metrics ────────────────────────────────────────────────

    async def compute_graph_metrics(self) -> dict[str, Any]:
        """Compute and return graph-level metrics.

        Calculates node/relationship counts, label distribution, and
        degree statistics.

        Returns:
            Dictionary of graph metrics.
        """
        # Basic counts
        count_cypher = """
        MATCH (n)
        WITH count(n) AS node_count
        MATCH ()-[r]->()
        RETURN node_count, count(r) AS rel_count
        """
        counts = await self._client.execute_query(count_cypher)
        node_count = counts[0]["node_count"] if counts else 0
        rel_count = counts[0]["rel_count"] if counts else 0

        # Label distribution
        label_cypher = """
        MATCH (n)
        WITH labels(n) AS lbls
        UNWIND lbls AS label
        RETURN label, count(*) AS count
        ORDER BY count DESC
        """
        label_dist = await self._client.execute_query(label_cypher)

        # Degree distribution (top connected nodes)
        degree_cypher = """
        MATCH (n)
        WITH n, size([(n)-[]-() | 1]) AS degree
        RETURN avg(degree) AS avg_degree,
               max(degree) AS max_degree,
               min(degree) AS min_degree,
               percentileCont(degree, 0.5) AS median_degree
        """
        degree_stats = await self._client.execute_query(degree_cypher)

        # Relationship type distribution
        rel_type_cypher = """
        MATCH ()-[r]->()
        RETURN type(r) AS rel_type, count(r) AS count
        ORDER BY count DESC
        """
        rel_types = await self._client.execute_query(rel_type_cypher)

        metrics: dict[str, Any] = {
            "node_count": node_count,
            "relationship_count": rel_count,
            "label_distribution": {
                r["label"]: r["count"] for r in label_dist
            },
            "relationship_type_distribution": {
                r["rel_type"]: r["count"] for r in rel_types
            },
            "degree_statistics": degree_stats[0] if degree_stats else {},
            "density": (
                (2 * rel_count) / (node_count * (node_count - 1))
                if node_count > 1
                else 0.0
            ),
        }
        logger.info("graph_metrics_computed", **{k: v for k, v in metrics.items() if not isinstance(v, dict)})
        return metrics

    # ── Subgraph Export ──────────────────────────────────────────────

    async def export_subgraph(
        self,
        center_node_id: str,
        depth: int = 2,
    ) -> dict[str, Any]:
        """Export a subgraph in a NetworkX-compatible format.

        Args:
            center_node_id: ``id`` property of the center node.
            depth: Maximum traversal depth from the center.

        Returns:
            Dictionary with ``directed``, ``multigraph``, ``graph``,
            ``nodes``, and ``links`` keys (NetworkX JSON graph format).
        """
        cypher = f"""
        MATCH (center {{id: $center_id}})
        MATCH path = (center)-[*0..{depth}]-(connected)
        WITH DISTINCT connected, relationships(path) AS path_rels
        UNWIND path_rels AS r
        WITH collect(DISTINCT {{
            id: connected.id,
            name: connected.name,
            labels: labels(connected),
            domain: connected.domain
        }}) AS nodes_list,
        collect(DISTINCT {{
            source: startNode(r).id,
            target: endNode(r).id,
            type: type(r),
            strength: r.strength
        }}) AS edges_list
        RETURN nodes_list, edges_list
        """
        results = await self._client.execute_query(
            cypher, {"center_id": center_node_id}
        )

        nodes: list[dict[str, Any]] = []
        links: list[dict[str, Any]] = []
        if results:
            nodes = results[0].get("nodes_list", [])
            links = results[0].get("edges_list", [])

        return {
            "directed": True,
            "multigraph": False,
            "graph": {"center": center_node_id, "depth": depth},
            "nodes": nodes,
            "links": links,
        }


__all__ = ["KnowledgeGraphBuilder"]
