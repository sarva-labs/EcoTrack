"""Neo4j graph database client for EcoTrack knowledge graph."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import structlog
from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession

logger = structlog.get_logger(__name__)


@dataclass
class Neo4jConfig:
    """Neo4j connection configuration.

    Attributes:
        uri: Neo4j bolt connection URI.
        username: Database username.
        password: Database password.
        database: Target database name.
        max_connection_pool_size: Maximum connections in the pool.
    """

    uri: str = "bolt://localhost:7687"
    username: str = "neo4j"
    password: str = "ecotrack"
    database: str = "ecotrack"
    max_connection_pool_size: int = 50


class KnowledgeGraphClient:
    """Async client for the EcoTrack knowledge graph.

    Provides CRUD operations, graph traversal, and bulk ingestion
    for the Neo4j-backed environmental knowledge graph.

    Usage::

        config = Neo4jConfig(uri="bolt://localhost:7687")
        async with KnowledgeGraphClient(config) as client:
            nodes = await client.find_nodes("Species", {"conservation_status": "EN"})
    """

    def __init__(self, config: Neo4jConfig) -> None:
        self.config = config
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """Establish connection to Neo4j."""
        logger.info(
            "connecting_to_neo4j",
            uri=self.config.uri,
            database=self.config.database,
        )
        self._driver = AsyncGraphDatabase.driver(
            self.config.uri,
            auth=(self.config.username, self.config.password),
            max_connection_pool_size=self.config.max_connection_pool_size,
        )

    async def close(self) -> None:
        """Close the Neo4j connection and release resources."""
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("neo4j_connection_closed")

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Get a database session as an async context manager.

        Yields:
            An ``AsyncSession`` bound to the configured database.

        Raises:
            AssertionError: If the client has not been connected yet.
        """
        assert self._driver is not None, "Client not connected. Call connect() first."
        async with self._driver.session(database=self.config.database) as session:
            yield session

    # ── Query Execution ──────────────────────────────────────────────

    async def execute_query(
        self,
        cypher: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cypher read query and return result records.

        Args:
            cypher: A parameterised Cypher query string.
            parameters: Parameter map for the query.

        Returns:
            A list of dictionaries, one per result record.
        """
        async with self.session() as session:
            result = await session.run(cypher, parameters or {})
            records = await result.data()
            logger.debug(
                "query_executed",
                cypher=cypher[:120],
                record_count=len(records),
            )
            return records

    async def execute_write(
        self,
        cypher: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a Cypher write query and return mutation counters.

        Args:
            cypher: A parameterised Cypher mutation query.
            parameters: Parameter map for the query.

        Returns:
            Dictionary with ``nodes_created``, ``relationships_created``,
            and ``properties_set`` counters.
        """
        async with self.session() as session:
            result = await session.run(cypher, parameters or {})
            summary = await result.consume()
            counters = {
                "nodes_created": summary.counters.nodes_created,
                "relationships_created": summary.counters.relationships_created,
                "properties_set": summary.counters.properties_set,
            }
            logger.debug("write_executed", cypher=cypher[:120], **counters)
            return counters

    # ── Node Operations ──────────────────────────────────────────────

    async def create_node(
        self,
        label: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a single node with the given label and properties.

        Args:
            label: The Neo4j node label (e.g. ``"Species"``).
            properties: Property key/value pairs.

        Returns:
            The created node as a dictionary, or ``{}`` on failure.
        """
        if not properties:
            logger.warning("create_node_empty_properties", label=label)
            return {}
        props_str = ", ".join(f"{k}: ${k}" for k in properties)
        cypher = f"CREATE (n:{label} {{{props_str}}}) RETURN n"
        results = await self.execute_query(cypher, properties)
        return results[0] if results else {}

    async def find_nodes(
        self,
        label: str,
        filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Find nodes by label and optional property filters.

        Args:
            label: Node label to match.
            filters: Optional property equality filters.
            limit: Maximum number of nodes to return.

        Returns:
            List of matching node dictionaries.
        """
        where_clause = ""
        params: dict[str, Any] = {}
        if filters:
            conditions = [f"n.{k} = ${k}" for k in filters]
            where_clause = "WHERE " + " AND ".join(conditions)
            params = dict(filters)
        cypher = f"MATCH (n:{label}) {where_clause} RETURN n LIMIT $__limit"
        params["__limit"] = limit
        return await self.execute_query(cypher, params)

    async def get_node_by_id(
        self,
        label: str,
        node_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve a single node by its ``id`` property.

        Args:
            label: Node label.
            node_id: The value of the ``id`` property.

        Returns:
            The node dictionary or ``None`` if not found.
        """
        cypher = f"MATCH (n:{label} {{id: $node_id}}) RETURN n"
        results = await self.execute_query(cypher, {"node_id": node_id})
        return results[0] if results else None

    async def update_node(
        self,
        label: str,
        node_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        """Update properties on an existing node.

        Args:
            label: Node label.
            node_id: The ``id`` property of the node.
            properties: Properties to set/update.

        Returns:
            Mutation counters from the write operation.
        """
        set_clauses = ", ".join(f"n.{k} = ${k}" for k in properties)
        cypher = f"MATCH (n:{label} {{id: $node_id}}) SET {set_clauses}"
        params: dict[str, Any] = {"node_id": node_id, **properties}
        return await self.execute_write(cypher, params)

    async def delete_node(
        self,
        label: str,
        node_id: str,
        detach: bool = True,
    ) -> dict[str, Any]:
        """Delete a node by id, optionally detaching relationships.

        Args:
            label: Node label.
            node_id: The ``id`` property of the node.
            detach: If ``True``, delete all attached relationships first.

        Returns:
            Mutation counters.
        """
        prefix = "DETACH " if detach else ""
        cypher = f"MATCH (n:{label} {{id: $node_id}}) {prefix}DELETE n"
        return await self.execute_write(cypher, {"node_id": node_id})

    # ── Relationship Operations ──────────────────────────────────────

    async def create_relationship(
        self,
        from_label: str,
        from_id: str,
        rel_type: str,
        to_label: str,
        to_id: str,
        properties: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a directed relationship between two nodes.

        Args:
            from_label: Source node label.
            from_id: Source node ``id``.
            rel_type: Relationship type string (e.g. ``"INHABITS"``).
            to_label: Target node label.
            to_id: Target node ``id``.
            properties: Optional relationship properties.

        Returns:
            Mutation counters.
        """
        props_str = ""
        params: dict[str, Any] = {"from_id": from_id, "to_id": to_id}
        if properties:
            props_str = " {" + ", ".join(f"{k}: $rel_{k}" for k in properties) + "}"
            params.update({f"rel_{k}": v for k, v in properties.items()})
        cypher = f"""
        MATCH (a:{from_label} {{id: $from_id}})
        MATCH (b:{to_label} {{id: $to_id}})
        CREATE (a)-[r:{rel_type}{props_str}]->(b)
        RETURN type(r) AS rel_type
        """
        return await self.execute_write(cypher, params)

    async def find_relationships(
        self,
        from_label: str,
        from_id: str,
        rel_type: str | None = None,
        to_label: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Find relationships originating from a node.

        Args:
            from_label: Source node label.
            from_id: Source node ``id``.
            rel_type: Optional relationship type filter.
            to_label: Optional target label filter.
            limit: Maximum relationships to return.

        Returns:
            List of relationship dictionaries with source, target, and type.
        """
        rel_filter = f":{rel_type}" if rel_type else ""
        to_filter = f":{to_label}" if to_label else ""
        cypher = f"""
        MATCH (a:{from_label} {{id: $from_id}})-[r{rel_filter}]->(b{to_filter})
        RETURN a AS source, type(r) AS relationship, properties(r) AS rel_props,
               b AS target, labels(b) AS target_labels
        LIMIT $__limit
        """
        return await self.execute_query(
            cypher, {"from_id": from_id, "__limit": limit}
        )

    # ── Graph Traversal ──────────────────────────────────────────────

    async def find_path(
        self,
        from_label: str,
        from_id: str,
        to_label: str,
        to_id: str,
        max_depth: int = 5,
    ) -> list[dict[str, Any]]:
        """Find the shortest path between two nodes.

        Args:
            from_label: Source node label.
            from_id: Source node ``id``.
            to_label: Target node label.
            to_id: Target node ``id``.
            max_depth: Maximum relationship hops.

        Returns:
            Path description with node labels, relationship types, and depth.
        """
        cypher = f"""
        MATCH p = shortestPath(
            (a:{from_label} {{id: $from_id}})-[*..{max_depth}]-(b:{to_label} {{id: $to_id}})
        )
        RETURN [n IN nodes(p) | labels(n)[0] + ': ' + coalesce(n.name, n.id)] AS path,
               [r IN relationships(p) | type(r)] AS relationships,
               length(p) AS depth
        """
        return await self.execute_query(
            cypher, {"from_id": from_id, "to_id": to_id}
        )

    async def get_neighbors(
        self,
        label: str,
        node_id: str,
        rel_type: str | None = None,
        direction: str = "both",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get neighboring nodes with optional direction and type filtering.

        Args:
            label: Center node label.
            node_id: Center node ``id``.
            rel_type: Optional relationship type filter.
            direction: ``"outgoing"``, ``"incoming"``, or ``"both"``.
            limit: Maximum neighbours to return.

        Returns:
            List of neighbour dictionaries with relationship info.
        """
        rel_filter = f":{rel_type}" if rel_type else ""
        if direction == "outgoing":
            pattern = f"(n:{label} {{id: $node_id}})-[r{rel_filter}]->(m)"
        elif direction == "incoming":
            pattern = f"(n:{label} {{id: $node_id}})<-[r{rel_filter}]-(m)"
        else:
            pattern = f"(n:{label} {{id: $node_id}})-[r{rel_filter}]-(m)"
        cypher = f"""
        MATCH {pattern}
        RETURN m AS neighbor, type(r) AS relationship, labels(m) AS labels
        LIMIT $__limit
        """
        return await self.execute_query(cypher, {"node_id": node_id, "__limit": limit})

    async def get_subgraph(
        self,
        center_label: str,
        center_id: str,
        depth: int = 2,
        limit: int = 200,
    ) -> dict[str, Any]:
        """Extract a subgraph around a center node.

        Args:
            center_label: Center node label.
            center_id: Center node ``id``.
            depth: Maximum traversal depth.
            limit: Maximum nodes in the subgraph.

        Returns:
            Dictionary with ``nodes`` and ``edges`` lists.
        """
        cypher = f"""
        MATCH (center:{center_label} {{id: $center_id}})
        CALL apoc.path.subgraphAll(center, {{maxLevel: {depth}}})
        YIELD nodes, relationships
        RETURN
            [n IN nodes | {{id: n.id, labels: labels(n), props: properties(n)}}][..{limit}] AS nodes,
            [r IN relationships | {{
                source: startNode(r).id,
                target: endNode(r).id,
                type: type(r),
                props: properties(r)
            }}] AS edges
        """
        # Fallback for environments without APOC
        fallback_cypher = f"""
        MATCH path = (center:{center_label} {{id: $center_id}})-[*0..{depth}]-(connected)
        WITH DISTINCT connected, path
        LIMIT {limit}
        RETURN collect(DISTINCT {{
            id: connected.id,
            labels: labels(connected),
            name: connected.name
        }}) AS nodes
        """
        try:
            results = await self.execute_query(cypher, {"center_id": center_id})
            if results:
                return results[0]
        except Exception:
            logger.debug("apoc_unavailable_using_fallback")
            results = await self.execute_query(fallback_cypher, {"center_id": center_id})
            if results:
                return {"nodes": results[0].get("nodes", []), "edges": []}
        return {"nodes": [], "edges": []}

    # ── Bulk Operations ──────────────────────────────────────────────

    async def bulk_create_nodes(
        self,
        label: str,
        nodes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Create multiple nodes in a single transaction using UNWIND.

        Args:
            label: Node label for all created nodes.
            nodes: List of property dictionaries, one per node.

        Returns:
            Mutation counters.
        """
        if not nodes:
            logger.warning("bulk_create_nodes_empty_list", label=label)
            return {"nodes_created": 0, "relationships_created": 0, "properties_set": 0}
        cypher = f"""
        UNWIND $nodes AS props
        CREATE (n:{label})
        SET n = props
        RETURN count(n) AS created
        """
        return await self.execute_write(cypher, {"nodes": nodes})

    async def bulk_create_relationships(
        self,
        from_label: str,
        to_label: str,
        rel_type: str,
        relationships: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Bulk-create relationships. Each dict must have ``from_id`` and ``to_id``.

        Additional keys are stored as relationship properties.

        Args:
            from_label: Source node label.
            to_label: Target node label.
            rel_type: Relationship type for all edges.
            relationships: Relationship descriptors.

        Returns:
            Mutation counters.
        """
        if not relationships:
            return {"nodes_created": 0, "relationships_created": 0, "properties_set": 0}
        rels = [
            {
                "from_id": r["from_id"],
                "to_id": r["to_id"],
                "properties": {
                    k: v for k, v in r.items() if k not in ("from_id", "to_id")
                },
            }
            for r in relationships
        ]
        cypher = f"""
        UNWIND $rels AS rel
        MATCH (a:{from_label} {{id: rel.from_id}})
        MATCH (b:{to_label} {{id: rel.to_id}})
        CREATE (a)-[r:{rel_type}]->(b)
        SET r = rel.properties
        RETURN count(r) AS created
        """
        return await self.execute_write(cypher, {"rels": rels})

    # ── Async Context Manager ────────────────────────────────────────

    async def __aenter__(self) -> KnowledgeGraphClient:
        """Connect on async-with entry."""
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Close on async-with exit."""
        await self.close()


__all__ = ["Neo4jConfig", "KnowledgeGraphClient"]
