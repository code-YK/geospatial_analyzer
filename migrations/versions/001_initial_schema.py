"""Initial schema — create site_features table with PostGIS extension.

Revision ID: 001
Revises:
Create Date: 2025-01-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable PostGIS (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS site_features (
            -- Layer 0: Identifiers
            id TEXT,
            grid_id TEXT PRIMARY KEY,
            latitude FLOAT,
            longitude FLOAT,
            state TEXT,
            district TEXT,
            area_name TEXT,
            geom GEOMETRY(Point, 4326),

            -- Layer 1: Demographics (WorldPop · Census 2011 · VIIRS)
            population_1km FLOAT,
            population_5km FLOAT,
            population_density FLOAT,
            male_population FLOAT,
            female_population FLOAT,
            sex_ratio FLOAT,
            child_population FLOAT,
            working_age_population FLOAT,
            elderly_population FLOAT,
            child_ratio FLOAT,
            working_age_ratio FLOAT,
            dependency_ratio FLOAT,
            household_count FLOAT,
            literacy_rate FLOAT,
            income_level FLOAT,

            -- Layer 2: Transportation (OSM · OSRM)
            road_density FLOAT,
            distance_to_highway FLOAT,
            intersection_density FLOAT,
            connectivity_score FLOAT,
            avg_travel_time_10min FLOAT,
            avg_travel_time_20min FLOAT,

            -- Layer 3: POI / Economic Activity (OSM)
            poi_count_500m FLOAT,
            poi_count_1km FLOAT,
            poi_count_2km FLOAT,
            competitor_count FLOAT,
            complementary_business_count FLOAT,
            restaurant_count FLOAT,
            shop_count FLOAT,
            hospital_count FLOAT,
            school_count FLOAT,
            bank_count FLOAT,
            poi_diversity_score FLOAT,
            footfall_proxy_score FLOAT,

            -- Layer 4: Land Use + Buildings (OSM)
            commercial_ratio FLOAT,
            residential_ratio FLOAT,
            industrial_ratio FLOAT,
            mixed_use_ratio FLOAT,
            building_count FLOAT,
            building_density FLOAT,
            avg_building_levels FLOAT,
            built_up_area_ratio FLOAT,

            -- Layer 5: Environment / Risk (OpenAQ · GDACS · OSM · NASA POWER)
            aqi FLOAT,
            pm25 FLOAT,
            pm10 FLOAT,
            flood_risk_score FLOAT,
            earthquake_risk_score FLOAT,
            green_space_ratio FLOAT,
            temperature FLOAT,

            -- Layer 6: Infrastructure (OSM)
            distance_to_power_substation FLOAT,
            power_line_density FLOAT,
            electricity_access_score FLOAT,
            distance_to_water_source FLOAT,
            water_body_proximity FLOAT,
            water_availability_score FLOAT,
            distance_to_bus_stop FLOAT,
            distance_to_railway_station FLOAT,
            public_transport_score FLOAT,

            -- Layer 7: Precomputed Derived Scores (0–100, computed by ETL pipeline)
            demand_score FLOAT,
            accessibility_score FLOAT,
            competition_score FLOAT,
            suitability_score FLOAT,
            risk_score FLOAT,
            infrastructure_score FLOAT,

            -- Metadata
            last_updated TIMESTAMP DEFAULT NOW()
        );
    """)

    # Performance indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_site_features_geom
        ON site_features USING GIST(geom);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_site_features_state
        ON site_features(state);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_site_features_grid_id
        ON site_features(grid_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS site_features;")
    op.execute("DROP EXTENSION IF EXISTS postgis;")
