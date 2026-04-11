# Derived Column Formulas

This document explains how the 6 precomputed Layer 7 scores are derived
from raw features (Layers 1–6). All scores are normalized to 0–100.

## Normalization Method

All raw features are min-max normalized before use:

```
normalized = (value - min) / (max - min) × 100
```

For risk/competition dimensions, scores are inverted:

```
inverted = 100 - normalized  (higher raw risk = lower score)
```

---

## demand_score

Measures market demand and economic activity potential.

**Inputs:**

| Feature | Weight |
|---|---|
| `population_density` | 0.30 |
| `population_1km` | 0.20 |
| `working_age_population` | 0.15 |
| `footfall_proxy_score` | 0.20 |
| `poi_count_1km` | 0.15 |

**Formula:**

```
demand_score = (
    norm(population_density)     × 0.30 +
    norm(population_1km)         × 0.20 +
    norm(working_age_population) × 0.15 +
    norm(footfall_proxy_score)   × 0.20 +
    norm(poi_count_1km)          × 0.15
)
```

---

## accessibility_score

Measures how easily the site can be reached.

**Inputs:**

| Feature | Weight | Notes |
|---|---|---|
| `road_density` | 0.25 | |
| `connectivity_score` | 0.25 | |
| `distance_to_highway` | 0.20 | inverted |
| `avg_travel_time_10min` | 0.15 | inverted |
| `public_transport_score` | 0.15 | |

**Formula:**

```
accessibility_score = (
    norm(road_density)                    × 0.25 +
    norm(connectivity_score)              × 0.25 +
    invert(norm(distance_to_highway))     × 0.20 +
    invert(norm(avg_travel_time_10min))   × 0.15 +
    norm(public_transport_score)          × 0.15
)
```

---

## competition_score

Measures competitive pressure at the site. Lower competition = higher score.

**Inputs:**

| Feature | Weight | Notes |
|---|---|---|
| `competitor_count` | 0.50 | inverted |
| `poi_diversity_score` | 0.30 | |
| `complementary_business_count` | 0.20 | |

**Formula:**

```
competition_score = (
    invert(norm(competitor_count))        × 0.50 +
    norm(poi_diversity_score)             × 0.30 +
    norm(complementary_business_count)    × 0.20
)
```

> **Note:** `competitor_count` is use-case specific and may be overridden
> at query time by the scoring engine based on the selected use case.

---

## suitability_score

Measures land use and physical suitability for development.

**Inputs:**

| Feature | Weight |
|---|---|
| `commercial_ratio` | 0.30 |
| `mixed_use_ratio` | 0.20 |
| `building_density` | 0.20 |
| `built_up_area_ratio` | 0.15 |
| `avg_building_levels` | 0.15 |

**Formula:**

```
suitability_score = (
    norm(commercial_ratio)    × 0.30 +
    norm(mixed_use_ratio)     × 0.20 +
    norm(building_density)    × 0.20 +
    norm(built_up_area_ratio) × 0.15 +
    norm(avg_building_levels) × 0.15
)
```

---

## risk_score

Measures environmental and natural hazard risk. Lower risk = higher score.

**Inputs:**

| Feature | Weight | Notes |
|---|---|---|
| `flood_risk_score` | 0.35 | inverted |
| `earthquake_risk_score` | 0.30 | inverted |
| `aqi` | 0.20 | inverted |
| `pm25` | 0.15 | inverted |

**Formula:**

```
risk_score = (
    invert(norm(flood_risk_score))      × 0.35 +
    invert(norm(earthquake_risk_score)) × 0.30 +
    invert(norm(aqi))                   × 0.20 +
    invert(norm(pm25))                  × 0.15
)
```

---

## infrastructure_score

Measures availability and quality of essential infrastructure.

**Inputs:**

| Feature | Weight | Notes |
|---|---|---|
| `electricity_access_score` | 0.30 | |
| `water_availability_score` | 0.25 | |
| `distance_to_power_substation` | 0.20 | inverted |
| `public_transport_score` | 0.15 | |
| `distance_to_bus_stop` | 0.10 | inverted |

**Formula:**

```
infrastructure_score = (
    norm(electricity_access_score)              × 0.30 +
    norm(water_availability_score)              × 0.25 +
    invert(norm(distance_to_power_substation))  × 0.20 +
    norm(public_transport_score)                × 0.15 +
    invert(norm(distance_to_bus_stop))          × 0.10
)
```
