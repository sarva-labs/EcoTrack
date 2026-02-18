"""Environmental ontology definitions for the EcoTrack knowledge graph.

Defines node types, relationship types, and ontology terms based on:
- ENVO (Environment Ontology)
- SWEET (Semantic Web for Earth and Environmental Terminology)
- Darwin Core (biodiversity data standard)
- CF Conventions (climate and forecast metadata)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from .client import KnowledgeGraphClient

logger = structlog.get_logger(__name__)


# ── Node Types ───────────────────────────────────────────────────────


class NodeType(str, Enum):
    """Knowledge graph node types representing environmental entities."""

    REGION = "Region"
    ECOSYSTEM = "Ecosystem"
    BIOME = "Biome"
    SPECIES = "Species"
    HABITAT = "Habitat"
    CLIMATE_ZONE = "ClimateZone"
    WATER_BODY = "WaterBody"
    SENSOR = "Sensor"
    OBSERVATION = "Observation"
    DATASET = "Dataset"
    MODEL = "Model"
    PREDICTION = "Prediction"
    ALERT = "Alert"
    POLICY = "Policy"
    INDICATOR = "Indicator"
    POLLUTANT = "Pollutant"
    CROP = "Crop"
    DISEASE_VECTOR = "DiseaseVector"
    URBAN_AREA = "UrbanArea"
    PROTECTED_AREA = "ProtectedArea"


# ── Relationship Types ───────────────────────────────────────────────


class RelationshipType(str, Enum):
    """Knowledge graph relationship types for environmental connections."""

    # Spatial relationships
    LOCATED_IN = "LOCATED_IN"
    PART_OF = "PART_OF"
    ADJACENT_TO = "ADJACENT_TO"

    # Ecological relationships
    DEPENDS_ON = "DEPENDS_ON"
    THREATENS = "THREATENS"
    PROTECTS = "PROTECTS"
    INHABITS = "INHABITS"
    FEEDS_ON = "FEEDS_ON"
    POLLINATES = "POLLINATES"
    COMPETES_WITH = "COMPETES_WITH"

    # Monitoring & prediction
    MONITORS = "MONITORS"
    PREDICTS = "PREDICTS"

    # Causal & correlation
    CAUSES = "CAUSES"
    MITIGATES = "MITIGATES"
    INFLUENCES = "INFLUENCES"
    CORRELATES_WITH = "CORRELATES_WITH"

    # Resource flow
    PRODUCES = "PRODUCES"
    CONSUMES = "CONSUMES"
    FLOWS_INTO = "FLOWS_INTO"
    DRAINS_TO = "DRAINS_TO"

    # Data provenance
    TRAINED_ON = "TRAINED_ON"
    GENERATED_BY = "GENERATED_BY"


# ── Ontology Term ────────────────────────────────────────────────────


@dataclass
class OntologyTerm:
    """A single term from an environmental ontology.

    Attributes:
        uri: Canonical URI (e.g. ``"http://purl.obolibrary.org/obo/ENVO_00000015"``).
        label: Human-readable label.
        description: Prose description of the term.
        domain: Source ontology (``"ENVO"``, ``"SWEET"``, ``"DarwinCore"``).
        parent_uri: URI of the parent term, if any.
        synonyms: Alternate names.
        properties: Additional key/value metadata.
    """

    uri: str
    label: str
    description: str
    domain: str
    parent_uri: str | None = None
    synonyms: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)


# ── Environmental Ontology Registry ──────────────────────────────────


class EnvironmentalOntology:
    """Registry of environmental ontology terms from ENVO and SWEET.

    Provides lookup, search, and hierarchy traversal for standard
    ontology terms used in the EcoTrack knowledge graph.
    """

    # ENVO — Environment Ontology terms
    # http://www.environmentontology.org/
    ENVO_TERMS: dict[str, OntologyTerm] = {
        "ENVO:00000015": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_00000015",
            label="ocean",
            description="A large body of saline water that composes a principal part of the hydrosphere.",
            domain="ENVO",
            parent_uri="http://purl.obolibrary.org/obo/ENVO_00000063",
            synonyms=["sea"],
        ),
        "ENVO:00000063": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_00000063",
            label="water body",
            description="An accumulation of water of varying size.",
            domain="ENVO",
            synonyms=["body of water"],
        ),
        "ENVO:00000446": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_00000446",
            label="terrestrial biome",
            description="A biome that applies to the terrestrial realm.",
            domain="ENVO",
            synonyms=["land biome"],
        ),
        "ENVO:01000174": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_01000174",
            label="forest biome",
            description="A terrestrial biome which includes any land area dominated by trees.",
            domain="ENVO",
            parent_uri="http://purl.obolibrary.org/obo/ENVO_00000446",
            synonyms=["forest", "woodland"],
        ),
        "ENVO:01000179": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_01000179",
            label="desert biome",
            description="A biome characterised by very low precipitation.",
            domain="ENVO",
            parent_uri="http://purl.obolibrary.org/obo/ENVO_00000446",
            synonyms=["desert"],
        ),
        "ENVO:01000175": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_01000175",
            label="grassland biome",
            description="A terrestrial biome dominated by grass and herbaceous plants.",
            domain="ENVO",
            parent_uri="http://purl.obolibrary.org/obo/ENVO_00000446",
            synonyms=["grassland", "prairie", "steppe", "savanna"],
        ),
        "ENVO:01000176": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_01000176",
            label="shrubland biome",
            description="A terrestrial biome dominated by shrubs.",
            domain="ENVO",
            parent_uri="http://purl.obolibrary.org/obo/ENVO_00000446",
            synonyms=["shrubland", "scrubland"],
        ),
        "ENVO:01000177": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_01000177",
            label="tundra biome",
            description="A terrestrial biome where growth is limited by low temperatures and short growing seasons.",
            domain="ENVO",
            parent_uri="http://purl.obolibrary.org/obo/ENVO_00000446",
            synonyms=["tundra"],
        ),
        "ENVO:00000233": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_00000233",
            label="wetland",
            description="An area of land saturated with water, either permanently or seasonally.",
            domain="ENVO",
            synonyms=["marsh", "bog", "swamp"],
        ),
        "ENVO:00000021": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_00000021",
            label="freshwater lake",
            description="A body of standing freshwater occupying a basin.",
            domain="ENVO",
            parent_uri="http://purl.obolibrary.org/obo/ENVO_00000063",
            synonyms=["lake"],
        ),
        "ENVO:00000022": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_00000022",
            label="river",
            description="A natural flowing watercourse.",
            domain="ENVO",
            parent_uri="http://purl.obolibrary.org/obo/ENVO_00000063",
            synonyms=["stream", "creek"],
        ),
        "ENVO:00002030": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_00002030",
            label="aquatic biome",
            description="A biome that applies to the aquatic realm.",
            domain="ENVO",
            synonyms=["water biome"],
        ),
        "ENVO:00000109": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_00000109",
            label="woodland",
            description="An area of land covered with trees less dense than a forest.",
            domain="ENVO",
            parent_uri="http://purl.obolibrary.org/obo/ENVO_01000174",
        ),
        "ENVO:00000428": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_00000428",
            label="biome",
            description="A large naturally occurring community of flora and fauna occupying a major habitat.",
            domain="ENVO",
        ),
        "ENVO:00001998": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_00001998",
            label="soil",
            description="The upper layer of earth in which plants grow.",
            domain="ENVO",
            synonyms=["earth", "topsoil"],
        ),
        "ENVO:00002005": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_00002005",
            label="air",
            description="The invisible gaseous substance surrounding the earth.",
            domain="ENVO",
            synonyms=["atmosphere"],
        ),
        "ENVO:01000180": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_01000180",
            label="tropical forest biome",
            description="A forest biome occurring in the tropics with high rainfall and biodiversity.",
            domain="ENVO",
            parent_uri="http://purl.obolibrary.org/obo/ENVO_01000174",
            synonyms=["tropical forest", "rainforest"],
        ),
        "ENVO:01000181": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_01000181",
            label="mangrove biome",
            description="A coastal biome characterized by salt-tolerant trees and shrubs.",
            domain="ENVO",
            parent_uri="http://purl.obolibrary.org/obo/ENVO_01000174",
            synonyms=["mangrove"],
        ),
        "ENVO:01000219": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_01000219",
            label="coral reef",
            description="An underwater ecosystem built by reef-building corals.",
            domain="ENVO",
            parent_uri="http://purl.obolibrary.org/obo/ENVO_00002030",
            synonyms=["reef"],
        ),
        "ENVO:00000077": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_00000077",
            label="agricultural field",
            description="A piece of land used for agricultural purposes.",
            domain="ENVO",
            synonyms=["farmland", "cropland"],
        ),
        "ENVO:01000248": OntologyTerm(
            uri="http://purl.obolibrary.org/obo/ENVO_01000248",
            label="urban area",
            description="An area characterised by high population density and human-built features.",
            domain="ENVO",
            synonyms=["city", "urban environment"],
        ),
    }

    # SWEET — Semantic Web for Earth and Environmental Terminology
    # https://sweetontology.net/
    SWEET_TERMS: dict[str, OntologyTerm] = {
        "sweet:Precipitation": OntologyTerm(
            uri="http://sweetontology.net/phenAtmoPrecipitation/Precipitation",
            label="precipitation",
            description="Water falling from clouds as rain, snow, hail, or sleet.",
            domain="SWEET",
            synonyms=["rainfall", "rain"],
        ),
        "sweet:Temperature": OntologyTerm(
            uri="http://sweetontology.net/propTemperature/Temperature",
            label="temperature",
            description="A measure of the average kinetic energy of particles.",
            domain="SWEET",
        ),
        "sweet:Humidity": OntologyTerm(
            uri="http://sweetontology.net/propFraction/Humidity",
            label="humidity",
            description="The amount of water vapour present in the air.",
            domain="SWEET",
            synonyms=["relative humidity", "moisture"],
        ),
        "sweet:SolarRadiation": OntologyTerm(
            uri="http://sweetontology.net/propEnergyFlux/SolarRadiation",
            label="solar radiation",
            description="Electromagnetic radiation emitted by the sun.",
            domain="SWEET",
            synonyms=["insolation", "shortwave radiation"],
        ),
        "sweet:AtmosphericPressure": OntologyTerm(
            uri="http://sweetontology.net/propPressure/AtmosphericPressure",
            label="atmospheric pressure",
            description="The pressure exerted by the weight of the atmosphere.",
            domain="SWEET",
            synonyms=["barometric pressure", "air pressure"],
        ),
        "sweet:WindSpeed": OntologyTerm(
            uri="http://sweetontology.net/propSpeed/WindSpeed",
            label="wind speed",
            description="The rate of movement of air relative to the Earth's surface.",
            domain="SWEET",
        ),
        "sweet:Evapotranspiration": OntologyTerm(
            uri="http://sweetontology.net/phenHydro/Evapotranspiration",
            label="evapotranspiration",
            description="The sum of evaporation and plant transpiration.",
            domain="SWEET",
            synonyms=["ET"],
        ),
        "sweet:SoilMoisture": OntologyTerm(
            uri="http://sweetontology.net/propFraction/SoilMoisture",
            label="soil moisture",
            description="The water content held in the soil.",
            domain="SWEET",
        ),
        "sweet:SeaSurfaceTemperature": OntologyTerm(
            uri="http://sweetontology.net/propTemperature/SeaSurfaceTemperature",
            label="sea surface temperature",
            description="Temperature of the water at the ocean surface.",
            domain="SWEET",
            synonyms=["SST"],
        ),
        "sweet:CarbonDioxide": OntologyTerm(
            uri="http://sweetontology.net/matrCompound/CarbonDioxide",
            label="carbon dioxide",
            description="A greenhouse gas with the formula CO₂.",
            domain="SWEET",
            synonyms=["CO2", "CO₂"],
        ),
        "sweet:Methane": OntologyTerm(
            uri="http://sweetontology.net/matrCompound/Methane",
            label="methane",
            description="A greenhouse gas with the formula CH₄.",
            domain="SWEET",
            synonyms=["CH4", "CH₄"],
        ),
        "sweet:Ozone": OntologyTerm(
            uri="http://sweetontology.net/matrCompound/Ozone",
            label="ozone",
            description="A triatomic allotrope of oxygen (O₃).",
            domain="SWEET",
            synonyms=["O3", "O₃"],
        ),
        "sweet:NDVI": OntologyTerm(
            uri="http://sweetontology.net/propIndex/NDVI",
            label="NDVI",
            description="Normalized Difference Vegetation Index — a measure of live green vegetation.",
            domain="SWEET",
            synonyms=["vegetation index"],
        ),
        "sweet:SeaLevel": OntologyTerm(
            uri="http://sweetontology.net/propDistance/SeaLevel",
            label="sea level",
            description="The average level of the sea surface.",
            domain="SWEET",
            synonyms=["mean sea level"],
        ),
        "sweet:Albedo": OntologyTerm(
            uri="http://sweetontology.net/propDimensionlessRatio/Albedo",
            label="albedo",
            description="The proportion of incident light reflected by a surface.",
            domain="SWEET",
        ),
    }

    # Combined term index for fast lookup
    _all_terms: dict[str, OntologyTerm] = {}

    def __init__(self) -> None:
        """Build the unified term index."""
        self._all_terms = {}
        for term_id, term in self.ENVO_TERMS.items():
            self._all_terms[term_id] = term
            self._all_terms[term.uri] = term
        for term_id, term in self.SWEET_TERMS.items():
            self._all_terms[term_id] = term
            self._all_terms[term.uri] = term

    def get_term(self, uri: str) -> OntologyTerm | None:
        """Look up an ontology term by short ID or full URI.

        Args:
            uri: Short ID (e.g. ``"ENVO:00000015"``) or full URI.

        Returns:
            The matching :class:`OntologyTerm` or ``None``.
        """
        return self._all_terms.get(uri)

    def get_children(self, uri: str) -> list[OntologyTerm]:
        """Find direct child terms of the given parent URI.

        Args:
            uri: Parent term URI (short ID or full).

        Returns:
            List of child :class:`OntologyTerm` instances.
        """
        parent = self._all_terms.get(uri)
        if parent is None:
            return []
        parent_uri = parent.uri
        return [
            t for t in self._all_terms.values()
            if t.parent_uri == parent_uri and t.uri != parent_uri
        ]

    def get_related(self, uri: str) -> list[OntologyTerm]:
        """Find terms related by shared parent or domain.

        Args:
            uri: Term URI (short ID or full).

        Returns:
            List of related :class:`OntologyTerm` instances.
        """
        term = self._all_terms.get(uri)
        if term is None:
            return []
        related: list[OntologyTerm] = []
        seen_uris: set[str] = {term.uri}
        # Siblings via shared parent
        if term.parent_uri:
            for t in self._all_terms.values():
                if t.parent_uri == term.parent_uri and t.uri not in seen_uris:
                    related.append(t)
                    seen_uris.add(t.uri)
        # Same domain
        for t in self._all_terms.values():
            if t.domain == term.domain and t.uri not in seen_uris:
                related.append(t)
                seen_uris.add(t.uri)
        return related

    def search(self, query: str) -> list[OntologyTerm]:
        """Search for ontology terms by keyword.

        Matches against label, description, and synonyms (case-insensitive).

        Args:
            query: Search keyword or phrase.

        Returns:
            List of matching :class:`OntologyTerm` instances.
        """
        query_lower = query.lower()
        results: list[OntologyTerm] = []
        seen_uris: set[str] = set()
        for term in self._all_terms.values():
            if term.uri in seen_uris:
                continue
            if (
                query_lower in term.label.lower()
                or query_lower in term.description.lower()
                or any(query_lower in syn.lower() for syn in term.synonyms)
            ):
                results.append(term)
                seen_uris.add(term.uri)
        return results


# ── Schema Definition ────────────────────────────────────────────────


class SchemaDefinition:
    """Neo4j schema management — constraints and indexes for the ontology.

    Generates and applies Cypher DDL statements that enforce uniqueness
    constraints and create lookup indexes for every :class:`NodeType`.
    """

    @staticmethod
    def get_constraints() -> list[str]:
        """Generate CREATE CONSTRAINT statements for all node types.

        Returns:
            List of Cypher ``CREATE CONSTRAINT`` statements ensuring
            ``id`` uniqueness on every :class:`NodeType`.
        """
        constraints: list[str] = []
        for nt in NodeType:
            alias = nt.value[0].lower()
            constraints.append(
                f"CREATE CONSTRAINT IF NOT EXISTS "
                f"FOR ({alias}:{nt.value}) REQUIRE {alias}.id IS UNIQUE"
            )
        return constraints

    @staticmethod
    def get_indexes() -> list[str]:
        """Generate CREATE INDEX statements for common lookup patterns.

        Returns:
            List of Cypher ``CREATE INDEX`` statements for name, domain,
            and temporal lookups.
        """
        indexes: list[str] = []
        # Name index on every node type
        for nt in NodeType:
            idx_name = f"idx_{nt.value.lower()}_name"
            indexes.append(
                f"CREATE INDEX {idx_name} IF NOT EXISTS "
                f"FOR (n:{nt.value}) ON (n.name)"
            )
        # Domain index on Observation and Dataset
        for label in ("Observation", "Dataset", "Prediction", "Alert"):
            idx_name = f"idx_{label.lower()}_domain"
            indexes.append(
                f"CREATE INDEX {idx_name} IF NOT EXISTS "
                f"FOR (n:{label}) ON (n.domain)"
            )
        # Temporal indexes
        for label in ("Observation", "Prediction", "Alert"):
            idx_name = f"idx_{label.lower()}_timestamp"
            indexes.append(
                f"CREATE INDEX {idx_name} IF NOT EXISTS "
                f"FOR (n:{label}) ON (n.timestamp)"
            )
        # Species scientific name
        indexes.append(
            "CREATE INDEX idx_species_scientific_name IF NOT EXISTS "
            "FOR (s:Species) ON (s.scientific_name)"
        )
        # Region bounding box
        indexes.append(
            "CREATE INDEX idx_region_bbox IF NOT EXISTS "
            "FOR (r:Region) ON (r.min_lon, r.min_lat, r.max_lon, r.max_lat)"
        )
        return indexes

    @staticmethod
    async def initialize_schema(client: KnowledgeGraphClient) -> dict[str, int]:
        """Apply all constraints and indexes to the Neo4j database.

        Args:
            client: A connected :class:`KnowledgeGraphClient`.

        Returns:
            Dictionary with counts of applied constraints and indexes.
        """
        constraints = SchemaDefinition.get_constraints()
        indexes = SchemaDefinition.get_indexes()
        applied_constraints = 0
        applied_indexes = 0

        for stmt in constraints:
            try:
                await client.execute_write(stmt)
                applied_constraints += 1
            except Exception as exc:
                logger.warning("constraint_failed", statement=stmt, error=str(exc))

        for stmt in indexes:
            try:
                await client.execute_write(stmt)
                applied_indexes += 1
            except Exception as exc:
                logger.warning("index_failed", statement=stmt, error=str(exc))

        logger.info(
            "schema_initialized",
            constraints=applied_constraints,
            indexes=applied_indexes,
        )
        return {"constraints": applied_constraints, "indexes": applied_indexes}


__all__ = [
    "NodeType",
    "RelationshipType",
    "OntologyTerm",
    "EnvironmentalOntology",
    "SchemaDefinition",
]
