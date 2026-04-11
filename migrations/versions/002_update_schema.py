"""Update schema — remove deprecated columns, rename grid_id to id.

Revision ID: 002
Revises: 001
Create Date: 2025-01-02
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Migration 001 has both `id TEXT` and `grid_id TEXT PRIMARY KEY`.
    # Drop the old non-PK `id` column first, then rename `grid_id` → `id`.
    op.execute("ALTER TABLE site_features DROP COLUMN IF EXISTS id;")
    op.execute("ALTER TABLE site_features RENAME COLUMN grid_id TO id;")

    # Drop removed columns
    op.execute("ALTER TABLE site_features DROP COLUMN IF EXISTS area_name;")
    op.execute("ALTER TABLE site_features DROP COLUMN IF EXISTS household_count;")
    op.execute("ALTER TABLE site_features DROP COLUMN IF EXISTS income_level;")

    # Drop old grid_id index, recreate as id index
    op.execute("DROP INDEX IF EXISTS idx_site_features_grid_id;")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_site_features_id
        ON site_features(id);
    """)

    # Add PostGIS spatial index if not already present
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_site_features_geom
        ON site_features USING GIST(geom);
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE site_features RENAME COLUMN id TO grid_id;")
    op.execute("ALTER TABLE site_features ADD COLUMN IF NOT EXISTS area_name TEXT;")
    op.execute("ALTER TABLE site_features ADD COLUMN IF NOT EXISTS household_count FLOAT;")
    op.execute("ALTER TABLE site_features ADD COLUMN IF NOT EXISTS income_level FLOAT;")
