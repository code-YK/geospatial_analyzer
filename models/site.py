"""
models/site.py — SiteInput, SiteFeatures, PrecomputedScores, SiteScore, HotspotResult,
                  CatchmentResult, ScoreBreakdown, and WhatIfResult Pydantic models.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from models.weights import WeightConfig


# ── Input Models ──────────────────────────────────────────────────────────

class SiteInput(BaseModel):
    """User-provided site location."""

    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")
    h3_id: Optional[str] = Field(None, description="H3 grid ID (auto-computed if omitted)")


# ── Feature / Score Models ────────────────────────────────────────────────

class SiteFeatures(BaseModel):
    """All columns for an H3 cell row from the site_features table (72 columns)."""

    model_config = ConfigDict(extra="ignore")

    # Layer 0 — Identifiers
    id: Optional[str] = None
    grid_id: str
    latitude: float
    longitude: float
    state: str = ""
    district: str = ""
    area_name: str = ""
    geom: Optional[str] = None  # WKB hex string returned by asyncpg for GEOMETRY columns

    # Layer 1 — Demographics (WorldPop · Census 2011 · VIIRS)
    population_1km: Optional[float] = None
    population_5km: Optional[float] = None
    population_density: Optional[float] = None
    male_population: Optional[float] = None
    female_population: Optional[float] = None
    sex_ratio: Optional[float] = None
    child_population: Optional[float] = None
    working_age_population: Optional[float] = None
    elderly_population: Optional[float] = None
    child_ratio: Optional[float] = None
    working_age_ratio: Optional[float] = None
    dependency_ratio: Optional[float] = None
    household_count: Optional[float] = None
    literacy_rate: Optional[float] = None
    income_level: Optional[float] = None

    # Layer 2 — Transportation (OSM · OSRM)
    road_density: Optional[float] = None
    distance_to_highway: Optional[float] = None
    intersection_density: Optional[float] = None
    connectivity_score: Optional[float] = None
    avg_travel_time_10min: Optional[float] = None
    avg_travel_time_20min: Optional[float] = None

    # Layer 3 — POI / Economic Activity (OSM)
    poi_count_500m: Optional[float] = None
    poi_count_1km: Optional[float] = None
    poi_count_2km: Optional[float] = None
    competitor_count: Optional[float] = None
    complementary_business_count: Optional[float] = None
    restaurant_count: Optional[float] = None
    shop_count: Optional[float] = None
    hospital_count: Optional[float] = None
    school_count: Optional[float] = None
    bank_count: Optional[float] = None
    poi_diversity_score: Optional[float] = None
    footfall_proxy_score: Optional[float] = None

    # Layer 4 — Land Use + Buildings (OSM)
    commercial_ratio: Optional[float] = None
    residential_ratio: Optional[float] = None
    industrial_ratio: Optional[float] = None
    mixed_use_ratio: Optional[float] = None
    building_count: Optional[float] = None
    building_density: Optional[float] = None
    avg_building_levels: Optional[float] = None
    built_up_area_ratio: Optional[float] = None

    # Layer 5 — Environment / Risk (OpenAQ · GDACS · OSM · NASA POWER)
    aqi: Optional[float] = None
    pm25: Optional[float] = None
    pm10: Optional[float] = None
    flood_risk_score: Optional[float] = None
    earthquake_risk_score: Optional[float] = None
    green_space_ratio: Optional[float] = None
    temperature: Optional[float] = None

    # Layer 6 — Infrastructure (OSM)
    distance_to_power_substation: Optional[float] = None
    power_line_density: Optional[float] = None
    electricity_access_score: Optional[float] = None
    distance_to_water_source: Optional[float] = None
    water_body_proximity: Optional[float] = None
    water_availability_score: Optional[float] = None
    distance_to_bus_stop: Optional[float] = None
    distance_to_railway_station: Optional[float] = None
    public_transport_score: Optional[float] = None

    # Layer 7 — Precomputed Derived Scores (0–100, computed by ETL pipeline)
    demand_score: Optional[float] = None
    accessibility_score: Optional[float] = None
    competition_score: Optional[float] = None
    suitability_score: Optional[float] = None
    risk_score: Optional[float] = None
    infrastructure_score: Optional[float] = None

    # Metadata
    last_updated: Optional[datetime] = None


class PrecomputedScores(BaseModel):
    """Layer 7 precomputed dimension scores (0–100 each)."""

    grid_id: str
    demand_score: float = Field(..., ge=0.0, le=100.0)
    accessibility_score: float = Field(..., ge=0.0, le=100.0)
    competition_score: float = Field(..., ge=0.0, le=100.0)
    suitability_score: float = Field(..., ge=0.0, le=100.0)
    risk_score: float = Field(..., ge=0.0, le=100.0)
    infrastructure_score: float = Field(..., ge=0.0, le=100.0)


class ScoreContribution(BaseModel):
    """Breakdown for a single scoring dimension."""

    raw: float
    weight: float
    contribution: float
    rank: int


class ScoreBreakdown(BaseModel):
    """Full explainability breakdown of a site score."""

    site_readiness_score: float
    contributions: Dict[str, ScoreContribution]
    strengths: List[str]
    weaknesses: List[str]


class SiteScore(BaseModel):
    """Final weighted site readiness score with full provenance."""

    grid_id: str
    lat: float
    lng: float
    site_readiness_score: float = Field(..., ge=0.0, le=100.0)
    contributions: Dict[str, float]
    precomputed_scores: PrecomputedScores
    weights_used: WeightConfig


class HotspotResult(BaseModel):
    """A single hotspot entry from spatial analysis."""

    grid_id: str
    lat: float
    lng: float
    state: str
    district: str
    area_name: str = ""
    site_readiness_score: float
    precomputed_scores: PrecomputedScores


class CatchmentResult(BaseModel):
    """Result of a catchment (radius) query."""

    center_h3_id: str
    radius_km: float
    cell_count: int
    cells: List[SiteFeatures]
    avg_score: Optional[float] = None


class WhatIfResult(BaseModel):
    """Result of a what-if weight comparison."""

    original_score: float
    modified_score: float
    delta: float
    dimension_deltas: Dict[str, float]
