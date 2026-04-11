"""
scoring/weights.py — Full use-case catalog with default weight configurations.

Single source of truth for all supported business types, categories,
and their default scoring weights.  Advisory agent may override these.
"""

from dataclasses import dataclass
from typing import Dict, List

from models.weights import WeightConfig


# ── Use-Case Config ──────────────────────────────────────────────────────

@dataclass
class UseCaseConfig:
    """One business type with its display name, category, and default weights."""

    key: str            # machine key, e.g. "ev_charging"
    name: str           # display name, e.g. "EV Charging Station"
    category: str       # category key, e.g. "energy"
    weights: WeightConfig


# ── Categories ───────────────────────────────────────────────────────────

USE_CASE_CATEGORIES: Dict[str, str] = {
    "necessity":    "Necessity & Civic",
    "health":       "Healthcare",
    "education":    "Education",
    "food":         "Food & Beverage",
    "retail":       "Retail & Commerce",
    "energy":       "Energy & Fuel",
    "finance":      "Finance & Banking",
    "funzone":      "Fun & Leisure",
    "hospitality":  "Hospitality",
    "industrial":   "Industrial / GIDC",
    "chemical":     "Chemical & Process",
    "logistics":    "Logistics & Supply Chain",
    "services":     "Professional Services",
    "religious":    "Religious & Civic",
    "agri":         "Agriculture",
}


# ── Helper to build WeightConfig concisely ───────────────────────────────

def _w(demand: float, access: float, comp: float,
       suit: float, risk: float, infra: float) -> WeightConfig:
    """Shorthand factory — avoids repeating long field names everywhere."""
    return WeightConfig(
        demand_score=demand,
        accessibility_score=access,
        competition_score=comp,
        suitability_score=suit,
        risk_score=risk,
        infrastructure_score=infra,
    )


# ── Full Catalog ─────────────────────────────────────────────────────────

USE_CASE_CATALOG: Dict[str, UseCaseConfig] = {

    # ── NECESSITY & CIVIC ────────────────────────────────────────────────
    "public_toilet": UseCaseConfig(
        "public_toilet", "Public Toilet / Sanitation", "necessity",
        _w(0.35, 0.25, 0.05, 0.15, 0.10, 0.10)),
    "water_supply": UseCaseConfig(
        "water_supply", "Water Supply Point", "necessity",
        _w(0.30, 0.20, 0.05, 0.15, 0.15, 0.15)),
    "post_office": UseCaseConfig(
        "post_office", "Post Office", "necessity",
        _w(0.30, 0.25, 0.10, 0.15, 0.10, 0.10)),
    "police_station": UseCaseConfig(
        "police_station", "Police Station", "necessity",
        _w(0.30, 0.25, 0.05, 0.15, 0.15, 0.10)),
    "fire_station": UseCaseConfig(
        "fire_station", "Fire Station", "necessity",
        _w(0.25, 0.30, 0.05, 0.15, 0.15, 0.10)),
    "govt_office": UseCaseConfig(
        "govt_office", "Government Office", "necessity",
        _w(0.25, 0.25, 0.05, 0.20, 0.15, 0.10)),
    "crematorium": UseCaseConfig(
        "crematorium", "Crematorium", "necessity",
        _w(0.20, 0.20, 0.05, 0.25, 0.20, 0.10)),
    "community_hall": UseCaseConfig(
        "community_hall", "Community Hall", "necessity",
        _w(0.30, 0.25, 0.05, 0.20, 0.10, 0.10)),

    # ── HEALTHCARE ───────────────────────────────────────────────────────
    "hospital": UseCaseConfig(
        "hospital", "Hospital", "health",
        _w(0.30, 0.25, 0.10, 0.10, 0.15, 0.10)),
    "clinic": UseCaseConfig(
        "clinic", "Clinic", "health",
        _w(0.30, 0.25, 0.10, 0.10, 0.15, 0.10)),
    "diagnostic_lab": UseCaseConfig(
        "diagnostic_lab", "Diagnostic Lab", "health",
        _w(0.25, 0.25, 0.15, 0.10, 0.10, 0.15)),
    "pharmacy": UseCaseConfig(
        "pharmacy", "Pharmacy", "health",
        _w(0.30, 0.20, 0.20, 0.10, 0.10, 0.10)),
    "pharmacy_chain": UseCaseConfig(
        "pharmacy_chain", "Pharmacy Chain Outlet", "health",
        _w(0.28, 0.22, 0.20, 0.10, 0.10, 0.10)),
    "mental_health": UseCaseConfig(
        "mental_health", "Mental Health Centre", "health",
        _w(0.25, 0.25, 0.10, 0.15, 0.15, 0.10)),
    "blood_bank": UseCaseConfig(
        "blood_bank", "Blood Bank", "health",
        _w(0.25, 0.30, 0.05, 0.10, 0.15, 0.15)),
    "ayurvedic_center": UseCaseConfig(
        "ayurvedic_center", "Ayurvedic / Wellness Centre", "health",
        _w(0.25, 0.20, 0.15, 0.15, 0.10, 0.15)),
    "dialysis_center": UseCaseConfig(
        "dialysis_center", "Dialysis Centre", "health",
        _w(0.25, 0.30, 0.05, 0.10, 0.15, 0.15)),
    "vet_clinic": UseCaseConfig(
        "vet_clinic", "Veterinary Clinic", "health",
        _w(0.25, 0.25, 0.10, 0.15, 0.15, 0.10)),

    # ── EDUCATION ────────────────────────────────────────────────────────
    "school": UseCaseConfig(
        "school", "School", "education",
        _w(0.30, 0.20, 0.10, 0.15, 0.15, 0.10)),
    "college": UseCaseConfig(
        "college", "College / University", "education",
        _w(0.25, 0.25, 0.10, 0.15, 0.15, 0.10)),
    "skill_center": UseCaseConfig(
        "skill_center", "Skill Development Centre", "education",
        _w(0.25, 0.25, 0.10, 0.15, 0.10, 0.15)),
    "anganwadi": UseCaseConfig(
        "anganwadi", "Anganwadi / Child Care", "education",
        _w(0.35, 0.25, 0.05, 0.15, 0.10, 0.10)),
    "library": UseCaseConfig(
        "library", "Public Library", "education",
        _w(0.30, 0.25, 0.05, 0.20, 0.10, 0.10)),
    "vocational_training": UseCaseConfig(
        "vocational_training", "Vocational Training Centre", "education",
        _w(0.25, 0.25, 0.10, 0.15, 0.10, 0.15)),

    # ── FOOD & BEVERAGE ──────────────────────────────────────────────────
    "restaurant": UseCaseConfig(
        "restaurant", "Restaurant", "food",
        _w(0.25, 0.20, 0.20, 0.15, 0.10, 0.10)),
    "cafe": UseCaseConfig(
        "cafe", "Café", "food",
        _w(0.25, 0.20, 0.20, 0.15, 0.10, 0.10)),
    "bakery": UseCaseConfig(
        "bakery", "Bakery", "food",
        _w(0.25, 0.20, 0.20, 0.15, 0.10, 0.10)),
    "cloud_kitchen": UseCaseConfig(
        "cloud_kitchen", "Cloud Kitchen", "food",
        _w(0.25, 0.15, 0.15, 0.15, 0.10, 0.20)),
    "food_processing": UseCaseConfig(
        "food_processing", "Food Processing Unit", "food",
        _w(0.20, 0.20, 0.10, 0.15, 0.15, 0.20)),
    "dhaba": UseCaseConfig(
        "dhaba", "Dhaba / Highway Restaurant", "food",
        _w(0.20, 0.30, 0.10, 0.15, 0.10, 0.15)),
    "juice_bar": UseCaseConfig(
        "juice_bar", "Juice Bar", "food",
        _w(0.25, 0.20, 0.20, 0.15, 0.10, 0.10)),
    "sweet_shop": UseCaseConfig(
        "sweet_shop", "Sweet Shop / Mithai", "food",
        _w(0.25, 0.20, 0.20, 0.15, 0.10, 0.10)),
    "tiffin_service": UseCaseConfig(
        "tiffin_service", "Tiffin / Dabba Service", "food",
        _w(0.30, 0.15, 0.15, 0.15, 0.10, 0.15)),
    "liquor_store": UseCaseConfig(
        "liquor_store", "Liquor Store / Wine Shop", "food",
        _w(0.25, 0.20, 0.15, 0.15, 0.15, 0.10)),
    "bar": UseCaseConfig(
        "bar", "Bar / Pub", "food",
        _w(0.25, 0.20, 0.15, 0.15, 0.15, 0.10)),

    # ── RETAIL & COMMERCE ────────────────────────────────────────────────
    "retail": UseCaseConfig(
        "retail", "Retail Store", "retail",
        _w(0.30, 0.20, 0.20, 0.10, 0.10, 0.10)),
    "supermarket": UseCaseConfig(
        "supermarket", "Supermarket", "retail",
        _w(0.28, 0.22, 0.20, 0.10, 0.10, 0.10)),
    "showroom": UseCaseConfig(
        "showroom", "Auto / Electronics Showroom", "retail",
        _w(0.22, 0.25, 0.18, 0.15, 0.10, 0.10)),
    "auto_service": UseCaseConfig(
        "auto_service", "Auto Service / Garage", "retail",
        _w(0.22, 0.25, 0.15, 0.15, 0.10, 0.13)),
    "tobacco_shop": UseCaseConfig(
        "tobacco_shop", "Tobacco / Pan Shop", "retail",
        _w(0.25, 0.20, 0.20, 0.15, 0.10, 0.10)),

    # ── ENERGY & FUEL ────────────────────────────────────────────────────
    "petrol_pump": UseCaseConfig(
        "petrol_pump", "Petrol Pump", "energy",
        _w(0.20, 0.35, 0.10, 0.15, 0.10, 0.10)),
    "cng_station": UseCaseConfig(
        "cng_station", "CNG Station", "energy",
        _w(0.22, 0.33, 0.08, 0.15, 0.10, 0.12)),
    "ev_charging": UseCaseConfig(
        "ev_charging", "EV Charging Station", "energy",
        _w(0.25, 0.30, 0.05, 0.10, 0.10, 0.20)),
    "ev_swap": UseCaseConfig(
        "ev_swap", "EV Battery Swap Station", "energy",
        _w(0.25, 0.28, 0.07, 0.10, 0.10, 0.20)),
    "solar_plant": UseCaseConfig(
        "solar_plant", "Solar Power Plant", "energy",
        _w(0.10, 0.15, 0.05, 0.30, 0.20, 0.20)),
    "wind_farm": UseCaseConfig(
        "wind_farm", "Wind Farm", "energy",
        _w(0.10, 0.15, 0.05, 0.30, 0.20, 0.20)),
    "renewable_energy": UseCaseConfig(
        "renewable_energy", "Renewable Energy Installation", "energy",
        _w(0.10, 0.20, 0.05, 0.25, 0.20, 0.20)),
    "gas_bottling": UseCaseConfig(
        "gas_bottling", "LPG / Gas Bottling Plant", "energy",
        _w(0.18, 0.25, 0.07, 0.15, 0.20, 0.15)),

    # ── FINANCE & BANKING ────────────────────────────────────────────────
    "bank_branch": UseCaseConfig(
        "bank_branch", "Bank Branch", "finance",
        _w(0.30, 0.22, 0.18, 0.12, 0.08, 0.10)),
    "atm": UseCaseConfig(
        "atm", "ATM Installation", "finance",
        _w(0.30, 0.28, 0.12, 0.12, 0.08, 0.10)),
    "microfinance": UseCaseConfig(
        "microfinance", "Microfinance Office", "finance",
        _w(0.30, 0.20, 0.15, 0.15, 0.10, 0.10)),
    "insurance_office": UseCaseConfig(
        "insurance_office", "Insurance Office", "finance",
        _w(0.25, 0.22, 0.18, 0.15, 0.10, 0.10)),

    # ── FUN & LEISURE ────────────────────────────────────────────────────
    "multiplex": UseCaseConfig(
        "multiplex", "Multiplex / Cinema", "funzone",
        _w(0.25, 0.25, 0.15, 0.15, 0.10, 0.10)),
    "amusement_park": UseCaseConfig(
        "amusement_park", "Amusement Park", "funzone",
        _w(0.20, 0.25, 0.10, 0.20, 0.15, 0.10)),
    "gaming_zone": UseCaseConfig(
        "gaming_zone", "Gaming Zone / Arcade", "funzone",
        _w(0.25, 0.22, 0.18, 0.15, 0.10, 0.10)),
    "sports_complex": UseCaseConfig(
        "sports_complex", "Sports Complex", "funzone",
        _w(0.25, 0.25, 0.10, 0.20, 0.10, 0.10)),
    "swimming_pool": UseCaseConfig(
        "swimming_pool", "Swimming Pool", "funzone",
        _w(0.25, 0.22, 0.12, 0.16, 0.10, 0.15)),
    "resort": UseCaseConfig(
        "resort", "Resort", "funzone",
        _w(0.20, 0.20, 0.10, 0.25, 0.15, 0.10)),
    "bowling_alley": UseCaseConfig(
        "bowling_alley", "Bowling Alley", "funzone",
        _w(0.25, 0.22, 0.15, 0.18, 0.10, 0.10)),
    "spa": UseCaseConfig(
        "spa", "Spa / Wellness Centre", "funzone",
        _w(0.22, 0.20, 0.18, 0.20, 0.10, 0.10)),
    "art_gallery": UseCaseConfig(
        "art_gallery", "Art Gallery / Museum", "funzone",
        _w(0.20, 0.25, 0.10, 0.25, 0.10, 0.10)),

    # ── HOSPITALITY ──────────────────────────────────────────────────────
    "hotel": UseCaseConfig(
        "hotel", "Hotel", "hospitality",
        _w(0.22, 0.25, 0.15, 0.18, 0.10, 0.10)),
    "dharamshala": UseCaseConfig(
        "dharamshala", "Dharamshala / Guest House", "hospitality",
        _w(0.25, 0.25, 0.10, 0.20, 0.10, 0.10)),

    # ── INDUSTRIAL / GIDC ────────────────────────────────────────────────
    "warehouse": UseCaseConfig(
        "warehouse", "Warehouse / Logistics Hub", "industrial",
        _w(0.15, 0.35, 0.05, 0.15, 0.15, 0.15)),
    "gidc_plot": UseCaseConfig(
        "gidc_plot", "GIDC / Industrial Plot", "industrial",
        _w(0.15, 0.25, 0.05, 0.20, 0.15, 0.20)),
    "light_manufacturing": UseCaseConfig(
        "light_manufacturing", "Light Manufacturing Unit", "industrial",
        _w(0.15, 0.25, 0.10, 0.20, 0.15, 0.15)),
    "auto_ancillary": UseCaseConfig(
        "auto_ancillary", "Auto Ancillary Unit", "industrial",
        _w(0.18, 0.25, 0.12, 0.15, 0.15, 0.15)),
    "textile_factory": UseCaseConfig(
        "textile_factory", "Textile Factory", "industrial",
        _w(0.18, 0.22, 0.10, 0.18, 0.15, 0.17)),
    "plastic_factory": UseCaseConfig(
        "plastic_factory", "Plastic Manufacturing Unit", "industrial",
        _w(0.15, 0.22, 0.08, 0.20, 0.18, 0.17)),
    "printing_unit": UseCaseConfig(
        "printing_unit", "Printing / Packaging Unit", "industrial",
        _w(0.18, 0.22, 0.10, 0.20, 0.12, 0.18)),
    "manufacturing": UseCaseConfig(
        "manufacturing", "General Manufacturing", "industrial",
        _w(0.15, 0.25, 0.10, 0.20, 0.15, 0.15)),

    # ── CHEMICAL & PROCESS ───────────────────────────────────────────────
    "chemical_factory": UseCaseConfig(
        "chemical_factory", "Chemical Factory", "chemical",
        _w(0.10, 0.20, 0.05, 0.20, 0.25, 0.20)),
    "pharma_manufacturing": UseCaseConfig(
        "pharma_manufacturing", "Pharma Manufacturing", "chemical",
        _w(0.15, 0.20, 0.08, 0.20, 0.20, 0.17)),
    "paint_factory": UseCaseConfig(
        "paint_factory", "Paint Factory", "chemical",
        _w(0.12, 0.20, 0.08, 0.20, 0.22, 0.18)),
    "fertiliser_plant": UseCaseConfig(
        "fertiliser_plant", "Fertiliser Plant", "chemical",
        _w(0.15, 0.20, 0.05, 0.20, 0.22, 0.18)),
    "etp": UseCaseConfig(
        "etp", "Effluent Treatment Plant", "chemical",
        _w(0.10, 0.20, 0.05, 0.20, 0.25, 0.20)),

    # ── LOGISTICS & SUPPLY CHAIN ─────────────────────────────────────────
    "cold_storage": UseCaseConfig(
        "cold_storage", "Cold Storage Facility", "logistics",
        _w(0.20, 0.25, 0.05, 0.15, 0.15, 0.20)),
    "delivery_hub": UseCaseConfig(
        "delivery_hub", "Last-Mile Delivery Hub", "logistics",
        _w(0.25, 0.30, 0.10, 0.10, 0.10, 0.15)),
    "truck_terminal": UseCaseConfig(
        "truck_terminal", "Truck Terminal / Transport Nagar", "logistics",
        _w(0.15, 0.35, 0.05, 0.15, 0.15, 0.15)),
    "agri_cold_chain": UseCaseConfig(
        "agri_cold_chain", "Agri Cold Chain Facility", "logistics",
        _w(0.22, 0.25, 0.05, 0.15, 0.13, 0.20)),

    # ── PROFESSIONAL SERVICES ────────────────────────────────────────────
    "coworking": UseCaseConfig(
        "coworking", "Co-working Space", "services",
        _w(0.22, 0.28, 0.18, 0.18, 0.07, 0.07)),
    "real_estate": UseCaseConfig(
        "real_estate", "Real Estate Office", "services",
        _w(0.25, 0.22, 0.18, 0.15, 0.10, 0.10)),
    "gym": UseCaseConfig(
        "gym", "Gym / Fitness Centre", "services",
        _w(0.25, 0.20, 0.20, 0.15, 0.10, 0.10)),
    "salon": UseCaseConfig(
        "salon", "Salon / Beauty Parlour", "services",
        _w(0.25, 0.20, 0.20, 0.15, 0.10, 0.10)),
    "laundry": UseCaseConfig(
        "laundry", "Laundry / Dry Cleaning", "services",
        _w(0.25, 0.22, 0.18, 0.15, 0.10, 0.10)),
    "ngo_office": UseCaseConfig(
        "ngo_office", "NGO / Non-Profit Office", "services",
        _w(0.25, 0.25, 0.05, 0.20, 0.15, 0.10)),
    "telecom_tower": UseCaseConfig(
        "telecom_tower", "Telecom Tower", "services",
        _w(0.10, 0.25, 0.10, 0.15, 0.15, 0.25)),
    "data_center": UseCaseConfig(
        "data_center", "Data Centre", "services",
        _w(0.10, 0.20, 0.05, 0.15, 0.20, 0.30)),

    # ── RELIGIOUS & CIVIC ────────────────────────────────────────────────
    "place_of_worship": UseCaseConfig(
        "place_of_worship", "Place of Worship", "religious",
        _w(0.30, 0.25, 0.05, 0.20, 0.10, 0.10)),

    # ── AGRICULTURE ──────────────────────────────────────────────────────
    "agri_input_store": UseCaseConfig(
        "agri_input_store", "Agri Input Store", "agri",
        _w(0.30, 0.22, 0.12, 0.15, 0.10, 0.11)),
    "agri_mandi": UseCaseConfig(
        "agri_mandi", "Agricultural Mandi / Market", "agri",
        _w(0.25, 0.30, 0.05, 0.15, 0.10, 0.15)),
    "greenhouse": UseCaseConfig(
        "greenhouse", "Greenhouse / Polyhouse", "agri",
        _w(0.20, 0.15, 0.05, 0.25, 0.15, 0.20)),
    "aquaculture": UseCaseConfig(
        "aquaculture", "Aquaculture / Fish Farm", "agri",
        _w(0.20, 0.15, 0.05, 0.25, 0.15, 0.20)),

    # ── ALIASES (backward compat with old 5-key system) ──────────────────
    "telecom": UseCaseConfig(
        "telecom", "Telecom Tower", "services",
        _w(0.10, 0.25, 0.10, 0.15, 0.15, 0.25)),
    "renewable": UseCaseConfig(
        "renewable", "Renewable Energy Installation", "energy",
        _w(0.10, 0.20, 0.05, 0.25, 0.20, 0.20)),
}


# ── Derived constants ────────────────────────────────────────────────────

VALID_USE_CASES = set(USE_CASE_CATALOG.keys())

# Agricultural use-cases exempt from NA land conversion rules
AGRI_USE_CASES = {"greenhouse", "aquaculture", "agri_mandi",
                  "agri_input_store", "agri_cold_chain"}

# Backward-compatible dict for code that still references USE_CASE_WEIGHTS
USE_CASE_WEIGHTS: Dict[str, WeightConfig] = {
    key: cfg.weights for key, cfg in USE_CASE_CATALOG.items()
}


# ── Lookup helpers ───────────────────────────────────────────────────────

def get_default_weights(use_case: str) -> WeightConfig:
    """Return the default WeightConfig for a given use case key."""
    if use_case not in USE_CASE_CATALOG:
        raise ValueError(
            f"Unknown use case '{use_case}'. "
            f"Valid options: {sorted(VALID_USE_CASES)}"
        )
    return USE_CASE_CATALOG[use_case].weights


def get_use_case_by_category(category: str) -> List[UseCaseConfig]:
    """Return all use-case configs belonging to a category."""
    return [v for v in USE_CASE_CATALOG.values() if v.category == category]
