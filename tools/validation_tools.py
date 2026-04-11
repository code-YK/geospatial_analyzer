"""
tools/validation_tools.py — Location-aware validation framework.

Runs legal, proximity, environmental, land-use, and viability checks
BEFORE scoring.  Returns block / warn / pass results with optional
score penalties and regulation references.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from core.logger import get_logger
from scoring.weights import AGRI_USE_CASES

logger = get_logger(__name__)


# ── Result Model ─────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    """Outcome of a single validation check."""

    status: str                               # "block" | "warn" | "pass"
    reason: Optional[str] = None              # shown to user if block or warn
    penalty_dimension: Optional[str] = None   # e.g. "risk_score"
    penalty_points: float = 0.0               # how many points to subtract
    regulation_ref: Optional[str] = None      # e.g. "COTPA 2003"


# ── 1.  Legal Validation ─────────────────────────────────────────────────

LEGAL_PROHIBITIONS = {
    "liquor_store": {
        "blocked_states": [
            "Gujarat", "Bihar", "Nagaland", "Mizoram", "Lakshadweep",
        ],
        "reason": "Alcohol is prohibited in {state} under state excise law.",
        "regulation": "State Prohibition Act",
    },
    "bar": {
        "blocked_states": [
            "Gujarat", "Bihar", "Nagaland", "Mizoram", "Lakshadweep",
        ],
        "reason": "Alcohol sale is prohibited in {state}.",
        "regulation": "State Prohibition Act",
    },
    "slaughterhouse": {
        "blocked_states": [
            "Uttar Pradesh", "Madhya Pradesh", "Rajasthan", "Gujarat",
            "Maharashtra", "Haryana", "Jammu and Kashmir",
            "Himachal Pradesh", "Chhattisgarh", "Jharkhand",
            "Uttarakhand", "Delhi",
        ],
        "reason": "Cow slaughter is banned in {state}.",
        "regulation": "Prevention of Cow Slaughter Act",
    },
    "plastic_factory": {
        "blocked_states": ["__all__"],
        "reason": "Single-use plastic manufacturing is banned nationwide.",
        "regulation": "Plastic Waste Management Rules 2021",
    },
}


def validate_legal(use_case: str, state_name: str) -> ValidationResult:
    """Check state-level legal prohibitions for the use case."""
    rule = LEGAL_PROHIBITIONS.get(use_case)
    if rule is None:
        return ValidationResult(status="pass")

    blocked = rule["blocked_states"]
    if "__all__" in blocked or state_name in blocked:
        return ValidationResult(
            status="block",
            reason=rule["reason"].format(state=state_name),
            regulation_ref=rule["regulation"],
        )

    return ValidationResult(status="pass")


# ── 2.  Proximity Validation ─────────────────────────────────────────────

PROXIMITY_RULES = [
    {
        "use_cases": ["liquor_store", "bar"],
        "field_check": lambda f: (
            getattr(f, "school_count", 0) or 0) > 0
            or (getattr(f, "hospital_count", 0) or 0) > 0,
        "status": "block",
        "reason": "Liquor shops cannot be within 500 m of schools or hospitals.",
        "regulation": "State Excise Act — proximity restrictions",
        "penalty_dimension": None,
        "penalty_points": 0,
    },
    {
        "use_cases": [
            "chemical_factory", "etp", "gas_bottling",
            "pharma_manufacturing", "paint_factory", "fertiliser_plant",
        ],
        "field_check": lambda f: (getattr(f, "residential_ratio", 0) or 0) > 0.30,
        "status": "block",
        "reason": (
            "Hazardous industrial units cannot be sited in residential "
            "zones (>30 % residential)."
        ),
        "regulation": "Factories Act 1948 — siting regulations",
        "penalty_dimension": None,
        "penalty_points": 0,
    },
    {
        "use_cases": ["hospital", "clinic", "diagnostic_lab", "mental_health"],
        "field_check": lambda f: (getattr(f, "industrial_ratio", 0) or 0) > 0.25,
        "status": "warn",
        "reason": (
            "Healthcare facilities near heavy industrial zones face "
            "AQI and noise compliance issues."
        ),
        "regulation": "MoH siting guidelines",
        "penalty_dimension": "risk_score",
        "penalty_points": 15,
    },
    {
        "use_cases": [
            "school", "college", "anganwadi", "vocational_training",
        ],
        "field_check": lambda f: (
            (getattr(f, "aqi", 0) or 0) > 150
            or (getattr(f, "industrial_ratio", 0) or 0) > 0.30
        ),
        "status": "warn",
        "reason": (
            "Educational institutions near high-AQI or industrial zones "
            "may face regulatory issues."
        ),
        "regulation": "COTPA 2003 / CBSE siting norms",
        "penalty_dimension": "risk_score",
        "penalty_points": 10,
    },
    {
        "use_cases": [
            "restaurant", "bakery", "food_processing", "cloud_kitchen",
            "sweet_shop", "juice_bar", "tiffin_service",
        ],
        "field_check": lambda f: (getattr(f, "aqi", 0) or 0) > 200,
        "status": "warn",
        "reason": (
            "Food businesses in severe AQI zones may fail FSSAI "
            "environment inspection."
        ),
        "regulation": "FSSAI Licensing Regulations",
        "penalty_dimension": "suitability_score",
        "penalty_points": 10,
    },
    {
        "use_cases": ["petrol_pump", "gas_bottling"],
        "field_check": lambda f: (getattr(f, "residential_ratio", 0) or 0) > 0.50,
        "status": "warn",
        "reason": (
            "Fuel / gas stations in dense residential areas require "
            "special PESO clearance."
        ),
        "regulation": "PESO Regulations",
        "penalty_dimension": "risk_score",
        "penalty_points": 8,
    },
    {
        "use_cases": ["crematorium"],
        "field_check": lambda f: (
            (getattr(f, "water_body_proximity", None) or 999) < 300
        ),
        "status": "warn",
        "reason": (
            "Crematoriums within 300 m of a water body risk "
            "contamination and PCB violations."
        ),
        "regulation": "PCB Environmental Norms",
        "penalty_dimension": "risk_score",
        "penalty_points": 12,
    },
    {
        "use_cases": ["tobacco_shop"],
        "field_check": lambda f: (getattr(f, "school_count", 0) or 0) > 0,
        "status": "block",
        "reason": (
            "Tobacco shops cannot operate within 100 m of any "
            "educational institution."
        ),
        "regulation": "COTPA 2003 Section 6(b)",
        "penalty_dimension": None,
        "penalty_points": 0,
    },
]


def validate_proximity(use_case: str, site_features) -> ValidationResult:
    """Check distance / proximity rules against site feature data."""
    for rule in PROXIMITY_RULES:
        if use_case not in rule["use_cases"]:
            continue
        if rule["field_check"](site_features):
            return ValidationResult(
                status=rule["status"],
                reason=rule["reason"],
                regulation_ref=rule.get("regulation"),
                penalty_dimension=rule.get("penalty_dimension"),
                penalty_points=rule.get("penalty_points", 0),
            )
    return ValidationResult(status="pass")


# ── 3.  Environmental Validation ─────────────────────────────────────────

ENVIRONMENTAL_RULES = [
    {
        "use_cases": [
            "hospital", "school", "data_center", "chemical_factory",
            "cold_storage", "warehouse",
        ],
        "field_check": lambda f: (getattr(f, "flood_risk_score", 0) or 0) > 80,
        "status": "block",
        "reason": (
            "Critical infrastructure cannot be sited in high flood "
            "risk zones (score > 80)."
        ),
        "regulation": "NDMA Flood Zone Regulations",
        "penalty_dimension": None,
        "penalty_points": 0,
    },
    {
        "use_cases": ["hospital", "data_center", "school"],
        "field_check": lambda f: (getattr(f, "earthquake_risk_score", 0) or 0) > 70,
        "status": "warn",
        "reason": (
            "High seismic risk zone. Building must comply with "
            "IS 1893 earthquake-resistant design."
        ),
        "regulation": "National Building Code — Seismic Zone IV/V",
        "penalty_dimension": "risk_score",
        "penalty_points": 12,
    },
    {
        "use_cases": [
            "restaurant", "bakery", "food_processing", "cloud_kitchen",
        ],
        "field_check": lambda f: (getattr(f, "aqi", 0) or 0) > 300,
        "status": "warn",
        "reason": (
            "Severe AQI (>300) is incompatible with food production "
            "standards."
        ),
        "regulation": "FSSAI Guidelines",
        "penalty_dimension": "suitability_score",
        "penalty_points": 15,
    },
]


def validate_environmental(use_case: str, site_features) -> ValidationResult:
    """Check environmental / natural-hazard rules."""
    for rule in ENVIRONMENTAL_RULES:
        if use_case not in rule["use_cases"]:
            continue
        if rule["field_check"](site_features):
            return ValidationResult(
                status=rule["status"],
                reason=rule["reason"],
                regulation_ref=rule.get("regulation"),
                penalty_dimension=rule.get("penalty_dimension"),
                penalty_points=rule.get("penalty_points", 0),
            )
    return ValidationResult(status="pass")


# ── 4.  Land-Use Validation ──────────────────────────────────────────────

def validate_land_use(use_case: str, site_features) -> ValidationResult:
    """Check land-use zoning compatibility."""

    commercial = getattr(site_features, "commercial_ratio", 0) or 0
    residential = getattr(site_features, "residential_ratio", 0) or 0
    industrial = getattr(site_features, "industrial_ratio", 0) or 0
    mixed_use = getattr(site_features, "mixed_use_ratio", 0) or 0

    # Pure agricultural land — no commercial conversion allowed
    if use_case not in AGRI_USE_CASES:
        if commercial < 0.05 and residential < 0.05 and industrial < 0.05:
            return ValidationResult(
                status="block",
                reason=(
                    "This appears to be agricultural land. "
                    "Non-Agricultural (NA) land conversion is required "
                    "before any commercial or industrial development."
                ),
                regulation_ref="Land Revenue Code — NA Conversion",
            )

    # Heavy industry in mixed-use zones
    heavy_industrial = {
        "chemical_factory", "gidc_plot", "light_manufacturing",
        "plastic_factory", "etp", "gas_bottling",
    }
    if use_case in heavy_industrial and mixed_use > 0.40:
        return ValidationResult(
            status="warn",
            reason=(
                "Heavy industry in mixed-use zones requires special "
                "zoning clearance from DIPP / state authority."
            ),
            regulation_ref="Industrial Zoning Regulations",
            penalty_dimension="suitability_score",
            penalty_points=10,
        )

    return ValidationResult(status="pass")


# ── 5.  Viability Validation ─────────────────────────────────────────────

VIABILITY_RULES = [
    {
        "use_cases": [
            "salon", "gym", "restaurant", "cafe", "juice_bar",
            "sweet_shop", "bakery", "laundry",
        ],
        "field_check": lambda f: (getattr(f, "population_density", 0) or 0) < 50,
        "status": "warn",
        "reason": (
            "Very low population density (<50/km²). Walk-in footfall "
            "may be insufficient for viability."
        ),
        "penalty_dimension": "demand_score",
        "penalty_points": 20,
    },
    {
        "use_cases": [
            "retail", "pharmacy", "supermarket", "restaurant",
            "cafe", "salon", "gym",
        ],
        "field_check": lambda f: (getattr(f, "competitor_count", 0) or 0) > 15,
        "status": "warn",
        "reason": (
            "High market saturation — 15+ competitors within 500 m. "
            "Differentiation will be critical."
        ),
        "penalty_dimension": "competition_score",
        "penalty_points": 15,
    },
    {
        "use_cases": ["data_center", "pharma_manufacturing", "cold_storage"],
        "field_check": lambda f: (
            (getattr(f, "electricity_access_score", 100) or 100) < 60
        ),
        "status": "warn",
        "reason": (
            "Unreliable power supply (score < 60). DG backup and "
            "UPS systems will be mandatory."
        ),
        "penalty_dimension": "infrastructure_score",
        "penalty_points": 12,
    },
    {
        "use_cases": ["hospital", "fire_station", "clinic"],
        "field_check": lambda f: (
            (getattr(f, "accessibility_score", 100) or 100) < 30
        ),
        "status": "warn",
        "reason": (
            "Very poor road accessibility (score < 30). Emergency "
            "response times may be critically affected."
        ),
        "penalty_dimension": "accessibility_score",
        "penalty_points": 10,
    },
    {
        "use_cases": ["solar_plant", "wind_farm"],
        "field_check": lambda f: (
            (getattr(f, "built_up_area_ratio", 0) or 0) > 0.60
        ),
        "status": "warn",
        "reason": (
            "High built-up area ratio (>60%). Insufficient open land "
            "for renewable energy installation."
        ),
        "penalty_dimension": "suitability_score",
        "penalty_points": 20,
    },
]


def validate_viability(use_case: str, site_features) -> List[ValidationResult]:
    """
    Check business viability concerns — may return multiple warnings.

    Unlike the other validators, viability checks are independent
    and more than one may fire for the same site.
    """
    results: List[ValidationResult] = []
    for rule in VIABILITY_RULES:
        if use_case not in rule["use_cases"]:
            continue
        if rule["field_check"](site_features):
            results.append(ValidationResult(
                status=rule["status"],
                reason=rule["reason"],
                penalty_dimension=rule.get("penalty_dimension"),
                penalty_points=rule.get("penalty_points", 0),
            ))
    return results


# ── Master Runner ────────────────────────────────────────────────────────

def run_all_validations(
    use_case: str,
    state_name: str,
    site_features,
) -> List[ValidationResult]:
    """
    Run all 5 validators in order.

    Returns a list of non-pass results sorted: blocks first, then warns.
    If any result is ``"block"``, the caller should stop processing
    immediately.
    """
    results: List[ValidationResult] = []

    results.append(validate_legal(use_case, state_name))
    results.append(validate_proximity(use_case, site_features))
    results.append(validate_environmental(use_case, site_features))
    results.append(validate_land_use(use_case, site_features))
    results.extend(validate_viability(use_case, site_features))

    # Keep only non-pass, blocks first
    active = [r for r in results if r.status != "pass"]
    active.sort(key=lambda r: (0 if r.status == "block" else 1))

    for r in active:
        logger.info(
            "Validation [%s] %s — %s (penalty: %s −%.0f)",
            use_case, r.status.upper(), r.reason,
            r.penalty_dimension or "—", r.penalty_points,
        )

    return active
