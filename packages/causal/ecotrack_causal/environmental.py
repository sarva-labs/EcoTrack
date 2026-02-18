"""Pre-built causal models for environmental domains.

Provides domain-specific causal structures and estimation methods for:

- **Climate impact** — CO₂ → Temperature → Sea Level, etc.
- **Deforestation impact** — Forest loss → Biodiversity, CO₂, Erosion
- **Pollution–health burden** — Pollutants → Respiratory/Waterborne disease
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import structlog

from .discovery import CausalEdge, CausalGraph, DiscoveryAlgorithm

logger = structlog.get_logger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────


def _build_graph(
    edges: list[tuple[str, str, float, str]],
    variables: list[str],
) -> CausalGraph:
    """Build a :class:`CausalGraph` from a compact edge list.

    Args:
        edges: Tuples of ``(cause, effect, strength, mechanism)``.
        variables: All variable names.

    Returns:
        A :class:`CausalGraph` with the given structure.
    """
    return CausalGraph(
        edges=[
            CausalEdge(
                cause=cause,
                effect=effect,
                strength=strength,
                confidence=0.95,
                mechanism=mechanism,
            )
            for cause, effect, strength, mechanism in edges
        ],
        variables=variables,
        algorithm=DiscoveryAlgorithm.CORRELATION,
        metadata={"source": "domain_expert"},
    )


# ── Climate Impact Model ─────────────────────────────────────────────


class ClimateImpactModel:
    """Pre-defined causal model for climate-change impact chains.

    Encodes well-established relationships such as:

    - CO₂ → Global Temperature → Sea Level Rise
    - Temperature → Heat Waves → Mortality
    - Precipitation → Soil Moisture → Crop Yield
    - Temperature → Glacial Melt → River Flow

    Usage::

        model = ClimateImpactModel()
        impact = model.estimate_warming_impact(1.5, "tropical")
    """

    VARIABLES: list[str] = [
        "co2_concentration",
        "global_temperature",
        "sea_level",
        "precipitation",
        "soil_moisture",
        "crop_yield",
        "heat_wave_frequency",
        "mortality_rate",
        "glacial_mass",
        "river_flow",
        "ocean_ph",
        "coral_coverage",
    ]

    EDGES: list[tuple[str, str, float, str]] = [
        ("co2_concentration", "global_temperature", 0.85, "greenhouse effect"),
        ("global_temperature", "sea_level", 0.72, "thermal expansion + ice melt"),
        ("global_temperature", "heat_wave_frequency", 0.80, "extreme event intensification"),
        ("heat_wave_frequency", "mortality_rate", 0.65, "heat-related illness"),
        ("global_temperature", "glacial_mass", -0.78, "ice melt acceleration"),
        ("glacial_mass", "river_flow", -0.60, "meltwater contribution"),
        ("precipitation", "soil_moisture", 0.75, "infiltration and retention"),
        ("soil_moisture", "crop_yield", 0.70, "plant water availability"),
        ("global_temperature", "precipitation", 0.45, "Clausius-Clapeyron relation"),
        ("co2_concentration", "ocean_ph", -0.80, "ocean acidification"),
        ("ocean_ph", "coral_coverage", 0.70, "calcification stress"),
        ("global_temperature", "coral_coverage", -0.60, "thermal bleaching"),
    ]

    def __init__(self) -> None:
        self.graph = _build_graph(self.EDGES, self.VARIABLES)

    def estimate_warming_impact(
        self,
        temperature_increase: float,
        region: str = "global",
    ) -> dict[str, Any]:
        """Estimate cascading impacts of a temperature increase.

        Propagates the temperature delta through the causal graph
        using linear scaling of edge strengths.

        Args:
            temperature_increase: Temperature change in °C.
            region: Region label (used for regional adjustment factors).

        Returns:
            Dictionary mapping each downstream variable to its estimated
            change.
        """
        # Regional adjustment factors
        regional_factors: dict[str, float] = {
            "tropical": 1.2,
            "temperate": 1.0,
            "arctic": 1.8,
            "arid": 0.9,
            "global": 1.0,
        }
        factor = regional_factors.get(region.lower(), 1.0)

        impacts: dict[str, float] = {"global_temperature": temperature_increase}

        # BFS propagation
        queue: list[str] = ["global_temperature"]
        visited: set[str] = {"global_temperature"}

        while queue:
            current = queue.pop(0)
            for edge in self.graph.get_effects(current):
                if edge.effect in visited:
                    continue
                parent_change = impacts.get(edge.cause, 0.0)
                child_change = parent_change * edge.strength * factor
                impacts[edge.effect] = round(child_change, 4)
                visited.add(edge.effect)
                queue.append(edge.effect)

        logger.info(
            "warming_impact_estimated",
            temperature_increase=temperature_increase,
            region=region,
            n_impacts=len(impacts),
        )
        return {
            "temperature_increase_c": temperature_increase,
            "region": region,
            "regional_factor": factor,
            "impacts": impacts,
            "causal_chain": [
                {
                    "cause": e.cause,
                    "effect": e.effect,
                    "strength": e.strength,
                    "mechanism": e.mechanism,
                }
                for e in self.graph.edges
            ],
        }

    def attribute_extreme_event(
        self,
        event_data: pd.DataFrame,
        baseline_data: pd.DataFrame,
    ) -> dict[str, Any]:
        """Extreme-event attribution analysis.

        Compares event statistics with a baseline period to estimate
        the fraction of risk attributable to climate change, using
        the *Fraction of Attributable Risk* (FAR) framework.

        FAR = 1 − P(event | baseline) / P(event | current)

        Args:
            event_data: Data during/around the extreme event.
            baseline_data: Historical baseline data.

        Returns:
            Attribution results with FAR estimate and confidence.
        """
        if event_data.empty or baseline_data.empty:
            return {"error": "Both event_data and baseline_data must be non-empty."}

        results: dict[str, Any] = {"variables": {}}
        common_cols = [
            c for c in event_data.columns if c in baseline_data.columns
        ]

        for col in common_cols:
            event_vals = event_data[col].dropna().values
            baseline_vals = baseline_data[col].dropna().values
            if len(event_vals) == 0 or len(baseline_vals) == 0:
                continue

            event_mean = float(np.mean(event_vals))
            baseline_mean = float(np.mean(baseline_vals))
            baseline_std = float(np.std(baseline_vals, ddof=1)) if len(baseline_vals) > 1 else 1.0

            if baseline_std == 0:
                continue

            # Threshold: event mean
            threshold = event_mean
            # P(exceeding threshold | baseline)
            p_baseline = float(np.mean(baseline_vals >= threshold))
            # P(exceeding threshold | current)
            p_current = float(np.mean(event_vals >= threshold))

            if p_current > 0:
                far = 1 - (p_baseline / p_current)
            else:
                far = 0.0

            # Z-score of event relative to baseline
            z_score = (event_mean - baseline_mean) / baseline_std

            results["variables"][col] = {
                "event_mean": round(event_mean, 4),
                "baseline_mean": round(baseline_mean, 4),
                "z_score": round(z_score, 4),
                "fraction_attributable_risk": round(max(0.0, min(1.0, far)), 4),
                "p_baseline": round(p_baseline, 4),
                "p_current": round(p_current, 4),
            }

        # Overall attribution: average FAR across variables
        fars = [
            v["fraction_attributable_risk"]
            for v in results["variables"].values()
        ]
        results["overall_far"] = round(float(np.mean(fars)), 4) if fars else 0.0
        results["interpretation"] = (
            f"On average, {results['overall_far'] * 100:.1f}% of the extreme event "
            f"risk is attributable to conditions beyond the historical baseline."
        )
        return results


# ── Deforestation Impact Model ───────────────────────────────────────


class DeforestationImpactModel:
    """Causal model for deforestation impacts.

    Encodes:
    - Deforestation → Biodiversity Loss
    - Deforestation → CO₂ Emissions
    - Deforestation → Soil Erosion → Water Quality degradation
    - Deforestation → Habitat Fragmentation → Species Isolation
    """

    VARIABLES: list[str] = [
        "deforestation_rate",
        "biodiversity_index",
        "co2_emissions",
        "soil_erosion_rate",
        "water_quality",
        "habitat_fragmentation",
        "species_richness",
        "carbon_stock",
        "precipitation_local",
        "soil_fertility",
    ]

    EDGES: list[tuple[str, str, float, str]] = [
        ("deforestation_rate", "biodiversity_index", -0.75, "habitat destruction"),
        ("deforestation_rate", "co2_emissions", 0.82, "biomass carbon release"),
        ("deforestation_rate", "soil_erosion_rate", 0.70, "root system loss"),
        ("soil_erosion_rate", "water_quality", -0.65, "sediment runoff"),
        ("soil_erosion_rate", "soil_fertility", -0.72, "topsoil loss"),
        ("deforestation_rate", "habitat_fragmentation", 0.80, "patch isolation"),
        ("habitat_fragmentation", "species_richness", -0.68, "edge effects and isolation"),
        ("deforestation_rate", "carbon_stock", -0.85, "standing biomass reduction"),
        ("deforestation_rate", "precipitation_local", -0.40, "reduced evapotranspiration"),
        ("precipitation_local", "soil_fertility", 0.50, "nutrient cycling"),
    ]

    def __init__(self) -> None:
        self.graph = _build_graph(self.EDGES, self.VARIABLES)

    def estimate_biodiversity_impact(
        self,
        area_deforested_km2: float,
        forest_type: str = "tropical",
    ) -> dict[str, Any]:
        """Estimate biodiversity impact from deforestation.

        Uses the species-area relationship (SAR): S = cA^z, where a
        reduction in area leads to a predictable species loss.

        Args:
            area_deforested_km2: Area of forest cleared (km²).
            forest_type: Type of forest (``"tropical"``, ``"temperate"``,
                ``"boreal"``).

        Returns:
            Impact estimates including species loss fraction,
            carbon released, and soil erosion risk.
        """
        # Species-area relationship parameters by forest type
        sar_params: dict[str, dict[str, float]] = {
            "tropical": {"z": 0.25, "species_density": 200.0, "carbon_density_tC_km2": 15000.0},
            "temperate": {"z": 0.20, "species_density": 80.0, "carbon_density_tC_km2": 8000.0},
            "boreal": {"z": 0.15, "species_density": 40.0, "carbon_density_tC_km2": 6000.0},
        }
        params = sar_params.get(forest_type.lower(), sar_params["tropical"])

        z = params["z"]
        base_area = 10000.0  # Reference area (km²)
        remaining_fraction = max(0.0, 1.0 - area_deforested_km2 / base_area)

        # Species-area: fraction of species remaining
        if remaining_fraction > 0:
            species_remaining_fraction = remaining_fraction ** z
        else:
            species_remaining_fraction = 0.0
        species_loss_fraction = 1.0 - species_remaining_fraction

        # Carbon emissions
        carbon_released_tC = area_deforested_km2 * params["carbon_density_tC_km2"]
        co2_released_t = carbon_released_tC * 3.667  # C → CO₂ conversion

        # Soil erosion risk increase
        erosion_risk_increase = min(1.0, area_deforested_km2 / base_area * 3.0)

        # Water quality impact
        water_quality_reduction = erosion_risk_increase * 0.65

        return {
            "area_deforested_km2": area_deforested_km2,
            "forest_type": forest_type,
            "species_loss_fraction": round(species_loss_fraction, 4),
            "estimated_species_at_risk": round(
                species_loss_fraction * params["species_density"] * (base_area / 100), 0
            ),
            "carbon_released_tonnes_co2": round(co2_released_t, 0),
            "carbon_released_tonnes_c": round(carbon_released_tC, 0),
            "erosion_risk_increase": round(erosion_risk_increase, 4),
            "water_quality_reduction": round(water_quality_reduction, 4),
            "causal_chains": [
                f"Deforestation ({area_deforested_km2} km²) → "
                f"Species loss ({species_loss_fraction:.1%})",
                f"Deforestation → CO₂ ({co2_released_t:,.0f} t)",
                f"Deforestation → Soil erosion ↑{erosion_risk_increase:.0%} → "
                f"Water quality ↓{water_quality_reduction:.0%}",
            ],
        }


# ── Pollution-Health Model ───────────────────────────────────────────


class PollutionHealthModel:
    """Causal model linking pollution to health outcomes.

    Encodes:
    - Industrial Activity → Air Pollutants → Respiratory Disease
    - Water Pollution → Waterborne Disease
    - PM2.5 → Cardiovascular Disease
    - Ozone → Asthma Exacerbation
    """

    VARIABLES: list[str] = [
        "industrial_activity",
        "pm25_concentration",
        "ozone_concentration",
        "no2_concentration",
        "respiratory_disease_rate",
        "cardiovascular_disease_rate",
        "asthma_rate",
        "water_pollution_index",
        "waterborne_disease_rate",
        "overall_health_burden",
        "premature_mortality",
    ]

    EDGES: list[tuple[str, str, float, str]] = [
        ("industrial_activity", "pm25_concentration", 0.78, "combustion emissions"),
        ("industrial_activity", "no2_concentration", 0.72, "NOx emissions"),
        ("industrial_activity", "water_pollution_index", 0.55, "effluent discharge"),
        ("pm25_concentration", "respiratory_disease_rate", 0.68, "particulate inhalation"),
        ("pm25_concentration", "cardiovascular_disease_rate", 0.62, "systemic inflammation"),
        ("pm25_concentration", "premature_mortality", 0.58, "chronic exposure"),
        ("ozone_concentration", "asthma_rate", 0.70, "airway irritation"),
        ("ozone_concentration", "respiratory_disease_rate", 0.55, "oxidative damage"),
        ("no2_concentration", "respiratory_disease_rate", 0.50, "airway inflammation"),
        ("water_pollution_index", "waterborne_disease_rate", 0.75, "pathogen/toxin exposure"),
        ("respiratory_disease_rate", "overall_health_burden", 0.60, "morbidity contribution"),
        ("cardiovascular_disease_rate", "overall_health_burden", 0.70, "leading cause of death"),
        ("waterborne_disease_rate", "overall_health_burden", 0.45, "GI morbidity"),
    ]

    # WHO concentration-response functions (CRFs)
    # Relative Risk per 10 µg/m³ increase in PM2.5
    _PM25_RR_PER_10: float = 1.062  # WHO 2021 estimate for all-cause mortality
    _OZONE_RR_PER_10PPB: float = 1.01  # Per 10 ppb 8-hr max

    def __init__(self) -> None:
        self.graph = _build_graph(self.EDGES, self.VARIABLES)

    def estimate_health_burden(
        self,
        pollutant_levels: dict[str, float],
        population: int,
    ) -> dict[str, Any]:
        """Estimate health burden from pollutant exposure.

        Uses WHO-style concentration-response functions to estimate
        attributable cases of disease and premature mortality.

        Args:
            pollutant_levels: Mapping of pollutant name → concentration.
                Supported keys: ``"pm25"`` (µg/m³), ``"ozone"`` (ppb),
                ``"no2"`` (ppb), ``"water_pollution_index"`` (0–1).
            population: Exposed population size.

        Returns:
            Health burden estimates including attributable cases
            and premature deaths.
        """
        if population <= 0:
            return {"error": "Population must be positive."}

        results: dict[str, Any] = {
            "population": population,
            "pollutant_levels": pollutant_levels,
            "attributable_cases": {},
            "total_premature_deaths": 0,
            "total_attributable_cases": 0,
        }

        total_deaths = 0
        total_cases = 0

        # PM2.5 impacts
        pm25 = pollutant_levels.get("pm25", 0.0)
        if pm25 > 0:
            # Baseline: WHO guideline = 5 µg/m³
            excess = max(0.0, pm25 - 5.0)
            rr = self._PM25_RR_PER_10 ** (excess / 10.0)
            paf = (rr - 1) / rr  # Population Attributable Fraction

            # Baseline mortality rate ≈ 8 per 1000 per year
            baseline_deaths = population * 0.008
            attributable_deaths = int(paf * baseline_deaths)

            # Respiratory cases: ~10% of population affected per 100 µg/m³
            resp_rate = min(0.15, excess / 100 * 0.10)
            resp_cases = int(resp_rate * population)

            # Cardiovascular: ~5% per 100 µg/m³
            cvd_rate = min(0.10, excess / 100 * 0.05)
            cvd_cases = int(cvd_rate * population)

            results["attributable_cases"]["pm25_premature_deaths"] = attributable_deaths
            results["attributable_cases"]["pm25_respiratory"] = resp_cases
            results["attributable_cases"]["pm25_cardiovascular"] = cvd_cases
            total_deaths += attributable_deaths
            total_cases += resp_cases + cvd_cases

        # Ozone impacts
        ozone = pollutant_levels.get("ozone", 0.0)
        if ozone > 0:
            # Baseline: 70 ppb (WHO 8-hr guideline ~100 µg/m³ ≈ 50 ppb)
            excess = max(0.0, ozone - 50.0)
            rr = self._OZONE_RR_PER_10PPB ** (excess / 10.0)
            paf = (rr - 1) / rr if rr > 1 else 0.0

            asthma_rate = min(0.05, excess / 100 * 0.02)
            asthma_cases = int(asthma_rate * population)

            results["attributable_cases"]["ozone_asthma"] = asthma_cases
            total_cases += asthma_cases

        # Water pollution
        wpi = pollutant_levels.get("water_pollution_index", 0.0)
        if wpi > 0:
            # Simple linear model: 5% disease rate at WPI = 1.0
            waterborne_rate = min(0.05, wpi * 0.05)
            waterborne_cases = int(waterborne_rate * population)

            results["attributable_cases"]["waterborne_disease"] = waterborne_cases
            total_cases += waterborne_cases

        results["total_premature_deaths"] = total_deaths
        results["total_attributable_cases"] = total_cases
        results["disability_adjusted_life_years"] = round(
            total_deaths * 12.0 + total_cases * 0.5, 0
        )  # Rough DALY estimate

        results["interpretation"] = (
            f"Given the pollutant levels for a population of {population:,}, "
            f"an estimated {total_deaths:,} premature deaths and "
            f"{total_cases:,} attributable disease cases are predicted annually."
        )

        logger.info(
            "health_burden_estimated",
            population=population,
            deaths=total_deaths,
            cases=total_cases,
        )
        return results


__all__ = [
    "ClimateImpactModel",
    "DeforestationImpactModel",
    "PollutionHealthModel",
]
