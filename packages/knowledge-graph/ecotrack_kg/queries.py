"""Cypher query templates for common EcoTrack knowledge graph operations.

All queries use parameterised inputs (``$param``) to prevent Cypher injection.
"""
from __future__ import annotations


class QueryTemplates:
    """Static methods returning parameterised Cypher query strings.

    Every method returns a Cypher template and accepts **no user data** —
    callers pass parameters separately via the client's
    :pymethod:`execute_query` method.
    """

    @staticmethod
    def find_ecosystem_threats(region_id: str) -> str:
        """Find threats to ecosystems within a given region.

        Parameters expected: ``$region_id``

        Args:
            region_id: Passed for documentation; the actual value is
                bound at execution time.

        Returns:
            Cypher query string.
        """
        return """
        MATCH (r:Region {id: $region_id})<-[:LOCATED_IN]-(e:Ecosystem)
        OPTIONAL MATCH (e)<-[:THREATENS]-(threat)
        RETURN e.id AS ecosystem_id,
               e.name AS ecosystem_name,
               collect({
                   id: threat.id,
                   name: threat.name,
                   labels: labels(threat),
                   severity: threat.severity
               }) AS threats,
               size(collect(threat)) AS threat_count
        ORDER BY threat_count DESC
        """

    @staticmethod
    def species_habitat_overlap(species_a: str, species_b: str) -> str:
        """Find habitats shared by two species.

        Parameters expected: ``$species_a``, ``$species_b``

        Args:
            species_a: First species id.
            species_b: Second species id.

        Returns:
            Cypher query string.
        """
        return """
        MATCH (sa:Species {id: $species_a})-[:INHABITS]->(h:Habitat)<-[:INHABITS]-(sb:Species {id: $species_b})
        RETURN h.id AS habitat_id,
               h.name AS habitat_name,
               h.area_km2 AS area_km2,
               sa.scientific_name AS species_a_name,
               sb.scientific_name AS species_b_name
        ORDER BY h.area_km2 DESC
        """

    @staticmethod
    def climate_impact_chain(variable: str, region_id: str) -> str:
        """Trace the causal chain from a climate variable to impacts in a region.

        Parameters expected: ``$variable``, ``$region_id``

        Args:
            variable: Climate variable name.
            region_id: Target region id.

        Returns:
            Cypher query string.
        """
        return """
        MATCH (r:Region {id: $region_id})
        MATCH path = (cv:Indicator {name: $variable})-[:CAUSES|INFLUENCES*1..6]->(impact)
        WHERE (impact)-[:LOCATED_IN|PART_OF*0..2]->(r)
        RETURN [n IN nodes(path) | {
                   id: n.id,
                   name: n.name,
                   labels: labels(n)
               }] AS chain,
               [rel IN relationships(path) | type(rel)] AS link_types,
               length(path) AS chain_length,
               impact.name AS final_impact,
               labels(impact)[0] AS impact_type
        ORDER BY chain_length
        LIMIT 20
        """

    @staticmethod
    def biodiversity_hotspots(min_species_count: int) -> str:
        """Find regions with highest species richness.

        Parameters expected: ``$min_species_count``

        Args:
            min_species_count: Minimum number of species required.

        Returns:
            Cypher query string.
        """
        return """
        MATCH (s:Species)-[:INHABITS]->(:Habitat)-[:LOCATED_IN]->(r:Region)
        WITH r, count(DISTINCT s) AS species_count
        WHERE species_count >= $min_species_count
        OPTIONAL MATCH (s_endangered:Species)-[:INHABITS]->(:Habitat)-[:LOCATED_IN]->(r)
        WHERE s_endangered.conservation_status IN ['CR', 'EN', 'VU']
        RETURN r.id AS region_id,
               r.name AS region_name,
               species_count,
               count(DISTINCT s_endangered) AS endangered_count,
               toFloat(count(DISTINCT s_endangered)) / species_count AS vulnerability_ratio
        ORDER BY species_count DESC
        """

    @staticmethod
    def pollution_pathways(pollutant_id: str, region_id: str) -> str:
        """Trace pollution flow paths from a source through a region.

        Parameters expected: ``$pollutant_id``, ``$region_id``

        Args:
            pollutant_id: Pollutant node id.
            region_id: Region to search within.

        Returns:
            Cypher query string.
        """
        return """
        MATCH (p:Pollutant {id: $pollutant_id})
        MATCH path = (p)-[:FLOWS_INTO|DRAINS_TO|CAUSES*1..8]->(target)
        WHERE EXISTS {
            MATCH (target)-[:LOCATED_IN*0..2]->(r:Region {id: $region_id})
        }
        RETURN [n IN nodes(path) | {
                   id: n.id,
                   name: n.name,
                   labels: labels(n)
               }] AS pathway,
               [rel IN relationships(path) | type(rel)] AS flow_types,
               length(path) AS path_length,
               target.name AS affected_entity,
               labels(target)[0] AS entity_type
        ORDER BY path_length
        LIMIT 30
        """

    @staticmethod
    def resource_dependency_graph(region_id: str) -> str:
        """Get the resource dependency network for a region.

        Parameters expected: ``$region_id``

        Args:
            region_id: Region id.

        Returns:
            Cypher query string.
        """
        return """
        MATCH (r:Region {id: $region_id})
        MATCH (entity)-[:LOCATED_IN*0..2]->(r)
        MATCH (entity)-[dep:DEPENDS_ON|CONSUMES|PRODUCES]->(resource)
        RETURN entity.id AS entity_id,
               entity.name AS entity_name,
               labels(entity)[0] AS entity_type,
               type(dep) AS dependency_type,
               resource.id AS resource_id,
               resource.name AS resource_name,
               labels(resource)[0] AS resource_type,
               dep.quantity AS quantity,
               dep.unit AS unit
        ORDER BY entity_name
        """

    @staticmethod
    def intervention_impact(policy_id: str) -> str:
        """Predict impact of a policy intervention.

        Parameters expected: ``$policy_id``

        Args:
            policy_id: Policy node id.

        Returns:
            Cypher query string.
        """
        return """
        MATCH (p:Policy {id: $policy_id})
        OPTIONAL MATCH (p)-[:MITIGATES]->(threat)
        OPTIONAL MATCH (p)-[:PROTECTS]->(protected)
        OPTIONAL MATCH (p)-[:INFLUENCES]->(influenced)
        OPTIONAL MATCH (threat)-[:THREATENS]->(at_risk)
        RETURN p.id AS policy_id,
               p.name AS policy_name,
               p.description AS policy_description,
               collect(DISTINCT {
                   id: threat.id,
                   name: threat.name,
                   type: labels(threat)[0]
               }) AS mitigated_threats,
               collect(DISTINCT {
                   id: protected.id,
                   name: protected.name,
                   type: labels(protected)[0]
               }) AS protected_entities,
               collect(DISTINCT {
                   id: influenced.id,
                   name: influenced.name,
                   type: labels(influenced)[0]
               }) AS influenced_entities,
               collect(DISTINCT {
                   id: at_risk.id,
                   name: at_risk.name,
                   type: labels(at_risk)[0]
               }) AS indirectly_protected
        """

    @staticmethod
    def cross_domain_correlations(
        domain_a: str, domain_b: str, region_id: str
    ) -> str:
        """Find cross-domain correlations within a region.

        Parameters expected: ``$domain_a``, ``$domain_b``, ``$region_id``

        Args:
            domain_a: First domain name (e.g. ``"climate"``).
            domain_b: Second domain name (e.g. ``"health"``).
            region_id: Region to scope the search.

        Returns:
            Cypher query string.
        """
        return """
        MATCH (r:Region {id: $region_id})
        MATCH (a)-[:LOCATED_IN*0..2]->(r)
        MATCH (b)-[:LOCATED_IN*0..2]->(r)
        WHERE a.domain = $domain_a AND b.domain = $domain_b
        MATCH (a)-[corr:CORRELATES_WITH|CAUSES|INFLUENCES]->(b)
        RETURN a.id AS source_id,
               a.name AS source_name,
               labels(a)[0] AS source_type,
               type(corr) AS correlation_type,
               corr.strength AS strength,
               corr.confidence AS confidence,
               corr.lag AS time_lag,
               b.id AS target_id,
               b.name AS target_name,
               labels(b)[0] AS target_type
        ORDER BY corr.strength DESC
        LIMIT 50
        """

    @staticmethod
    def temporal_evolution(node_id: str, start_date: str, end_date: str) -> str:
        """Track observation changes over time for a given node.

        Parameters expected: ``$node_id``, ``$start_date``, ``$end_date``

        Args:
            node_id: The node to track.
            start_date: ISO-8601 start date string.
            end_date: ISO-8601 end date string.

        Returns:
            Cypher query string.
        """
        return """
        MATCH (target {id: $node_id})
        MATCH (obs:Observation)-[:MONITORS]->(target)
        WHERE obs.timestamp >= datetime($start_date)
          AND obs.timestamp <= datetime($end_date)
        RETURN obs.timestamp AS timestamp,
               obs.variable AS variable,
               obs.value AS value,
               obs.unit AS unit,
               obs.quality_flag AS quality_flag
        ORDER BY obs.timestamp ASC
        """

    @staticmethod
    def recommendation_subgraph(region_id: str, domain: str) -> str:
        """Get the relevant subgraph for generating recommendations.

        Parameters expected: ``$region_id``, ``$domain``

        Args:
            region_id: Target region.
            domain: Domain to focus on.

        Returns:
            Cypher query string.
        """
        return """
        MATCH (r:Region {id: $region_id})
        // Gather domain-specific entities
        OPTIONAL MATCH (entity)-[:LOCATED_IN*0..2]->(r)
        WHERE entity.domain = $domain OR entity.domain IS NULL
        // Gather relationships between these entities
        OPTIONAL MATCH (entity)-[rel]->(connected)
        WHERE connected.domain = $domain OR connected.domain IS NULL
           OR labels(connected)[0] IN ['Region', 'Ecosystem', 'Habitat', 'Policy']
        // Gather active alerts
        OPTIONAL MATCH (alert:Alert)-[:LOCATED_IN*0..2]->(r)
        WHERE alert.resolved = false AND alert.domain = $domain
        // Gather relevant policies
        OPTIONAL MATCH (policy:Policy)-[:PROTECTS|MITIGATES]->(entity)
        RETURN collect(DISTINCT {
                   id: entity.id,
                   name: entity.name,
                   labels: labels(entity),
                   domain: entity.domain
               }) AS entities,
               collect(DISTINCT {
                   source: entity.id,
                   target: connected.id,
                   type: type(rel)
               }) AS relationships,
               collect(DISTINCT {
                   id: alert.id,
                   severity: alert.severity,
                   description: alert.description
               }) AS active_alerts,
               collect(DISTINCT {
                   id: policy.id,
                   name: policy.name
               }) AS relevant_policies
        """


__all__ = ["QueryTemplates"]
