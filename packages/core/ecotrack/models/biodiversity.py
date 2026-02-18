"""Biodiversity domain models."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import Field

from .base import Domain, EcoTrackModel, Severity
from .geospatial import BoundingBox, GeoPoint


class TaxonomicRank(str, Enum):
    """Biological taxonomic ranks."""

    KINGDOM = "kingdom"
    PHYLUM = "phylum"
    CLASS = "class"
    ORDER = "order"
    FAMILY = "family"
    GENUS = "genus"
    SPECIES = "species"


class ConservationStatus(str, Enum):
    """IUCN Red List categories."""

    NOT_EVALUATED = "NE"
    DATA_DEFICIENT = "DD"
    LEAST_CONCERN = "LC"
    NEAR_THREATENED = "NT"
    VULNERABLE = "VU"
    ENDANGERED = "EN"
    CRITICALLY_ENDANGERED = "CR"
    EXTINCT_IN_WILD = "EW"
    EXTINCT = "EX"


class Species(EcoTrackModel):
    """Species record."""

    domain: Domain = Domain.BIODIVERSITY
    scientific_name: str
    common_name: str | None = None
    taxonomic_rank: TaxonomicRank = TaxonomicRank.SPECIES
    conservation_status: ConservationStatus = ConservationStatus.NOT_EVALUATED
    taxonomy: dict[str, str] = Field(default_factory=dict)


class SpeciesObservation(EcoTrackModel):
    """Observation of a species at a location."""

    domain: Domain = Domain.BIODIVERSITY
    species_name: str
    location: GeoPoint
    observed_at: datetime
    observer: str | None = None
    count: int = 1
    evidence_type: str = "human_observation"
    confidence: float = Field(ge=0, le=1, default=1.0)
    source_dataset: str = ""


class EcosystemHealthIndex(EcoTrackModel):
    """Composite ecosystem health score for a region."""

    domain: Domain = Domain.BIODIVERSITY
    bbox: BoundingBox
    timestamp: datetime
    species_richness_score: float = Field(ge=0, le=1)
    habitat_integrity_score: float = Field(ge=0, le=1)
    connectivity_score: float = Field(ge=0, le=1)
    threat_level_score: float = Field(ge=0, le=1)
    overall_score: float = Field(ge=0, le=1)
    trend: str = "stable"  # improving, stable, declining


__all__ = [
    "TaxonomicRank",
    "ConservationStatus",
    "Species",
    "SpeciesObservation",
    "EcosystemHealthIndex",
]
