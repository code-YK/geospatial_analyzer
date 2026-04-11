"""
sync_job.py — Load site data from CSV into PostgreSQL.

Usage:
    python sync_job.py                          # uses default path
    python sync_job.py --file data/custom.csv   # custom path
    python sync_job.py --truncate               # clear table before loading
    python sync_job.py --batch-size 500         # custom batch size

CSV path default: data/  (auto-detects first .csv file in the folder)
"""

import re
import sys
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import psycopg2
import psycopg2.extras
import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from core.config import get_settings
from core.logger import setup_logging, get_logger

# Initialize logging
settings = get_settings()
setup_logging(log_level=settings.log_level)
logger = get_logger(__name__)

console = Console()
app = typer.Typer(help="Load site CSV data into PostgreSQL.")

# Columns that must exist in the CSV
REQUIRED_COLUMNS = {"id", "latitude", "longitude", "state", "district"}

# All columns in the site_features table (excluding geom and last_updated)
TABLE_COLUMNS = [
    "id", "latitude", "longitude", "state", "district",
    # Layer 1: Demographics
    "population_density", "population_1km", "population_5km",
    "male_population", "female_population", "sex_ratio",
    "child_population", "working_age_population", "elderly_population",
    "child_ratio", "working_age_ratio", "dependency_ratio",
    "literacy_rate",
    # Layer 2: Transportation
    "road_density", "distance_to_highway", "intersection_density",
    "connectivity_score", "avg_travel_time_10min", "avg_travel_time_20min",
    # Layer 3: POI / Economic Activity
    "poi_count_500m", "poi_count_1km", "poi_count_2km",
    "competitor_count", "complementary_business_count",
    "restaurant_count", "shop_count", "hospital_count",
    "school_count", "bank_count", "poi_diversity_score", "footfall_proxy_score",
    # Layer 4: Land Use + Buildings
    "commercial_ratio", "residential_ratio", "industrial_ratio",
    "mixed_use_ratio", "building_count", "building_density",
    "avg_building_levels", "built_up_area_ratio",
    # Layer 5: Environment / Risk
    "aqi", "pm25", "pm10",
    "flood_risk_score", "earthquake_risk_score",
    "green_space_ratio", "temperature",
    # Layer 6: Infrastructure
    "distance_to_power_substation", "power_line_density",
    "electricity_access_score", "distance_to_water_source",
    "water_body_proximity", "water_availability_score",
    "distance_to_bus_stop", "distance_to_railway_station",
    "public_transport_score",
    # Layer 7: Precomputed Derived Scores
    "demand_score", "accessibility_score", "competition_score",
    "suitability_score", "risk_score", "infrastructure_score",
]

ID_PATTERN = re.compile(r"^IND_\d{7}$")


def _get_sync_db_url() -> str:
    """Convert asyncpg DATABASE_URL to psycopg2 format."""
    url = settings.database_url
    return url.replace("postgresql+asyncpg://", "postgresql://")


def _auto_detect_csv(data_dir: str = "data") -> Optional[Path]:
    """Find the first .csv file in the data directory."""
    data_path = Path(data_dir)
    if not data_path.exists():
        return None
    csv_files = list(data_path.glob("*.csv"))
    if len(csv_files) == 0:
        return None
    if len(csv_files) > 1:
        console.print(
            f"[yellow]Multiple CSV files found in {data_dir}/:[/]"
        )
        for f in csv_files:
            console.print(f"  - {f.name}")
        console.print("[yellow]Use --file to specify which one.[/]")
        return None
    return csv_files[0]


def _validate_csv(df: pd.DataFrame) -> bool:
    """Validate that required columns exist."""
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        console.print(
            f"[red]Missing required columns: {', '.join(sorted(missing))}[/]"
        )
        return False
    return True


def _check_id_format(df: pd.DataFrame) -> int:
    """Warn about IDs that don't match IND_XXXXXXX pattern."""
    invalid = df["id"].apply(lambda x: not bool(ID_PATTERN.match(str(x))))
    count = invalid.sum()
    if count > 0:
        logger.warning(
            "%d rows have non-standard ID format (expected IND_XXXXXXX)", count
        )
        console.print(
            f"[yellow]⚠ {count:,} rows have non-standard ID format "
            f"(expected IND_XXXXXXX)[/]"
        )
    return count


def _build_upsert_query() -> str:
    """Build the INSERT ... ON CONFLICT DO UPDATE query."""
    cols = TABLE_COLUMNS + ["geom"]
    placeholders = ", ".join(f"%({c})s" for c in cols)
    col_names = ", ".join(cols)

    update_set = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in cols if c != "id"
    )

    return f"""
        INSERT INTO site_features ({col_names})
        VALUES ({placeholders})
        ON CONFLICT (id) DO UPDATE SET
            {update_set}
    """


@app.command()
def load(
    file: Optional[str] = typer.Option(
        None, "--file", "-f", help="Path to CSV file"
    ),
    truncate: bool = typer.Option(
        False, "--truncate", help="Clear table before loading"
    ),
    batch_size: int = typer.Option(
        1000, "--batch-size", "-b", help="Rows per batch commit"
    ),
    data_dir: str = typer.Option(
        "data", "--data-dir", "-d", help="Directory to scan for CSV files"
    ),
):
    """Load site data from CSV into the site_features table."""
    # Resolve CSV path
    if file:
        csv_path = Path(file)
    else:
        csv_path = _auto_detect_csv(data_dir)

    if csv_path is None or not csv_path.exists():
        console.print(
            Panel(
                f"[red]CSV file not found. "
                f"Use --file to specify the path.[/]",
                title="Error",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)

    console.print(f"Loading [bold]{csv_path}[/] → geospatial_db\n")

    # Read CSV
    logger.info("Reading CSV: %s", csv_path)
    df = pd.read_csv(csv_path)
    total_rows = len(df)
    logger.info("CSV loaded: %d rows, %d columns", total_rows, len(df.columns))

    # Validate
    if not _validate_csv(df):
        raise typer.Exit(code=1)

    _check_id_format(df)

    # Filter to only known columns
    available_cols = [c for c in TABLE_COLUMNS if c in df.columns]
    df = df[available_cols].copy()

    # Replace NaN with None for PostgreSQL
    df = df.where(pd.notna(df), None)

    # Generate geom WKT from lat/lng
    df["geom"] = df.apply(
        lambda row: (
            f"SRID=4326;POINT({row['longitude']} {row['latitude']})"
            if row["latitude"] is not None and row["longitude"] is not None
            else None
        ),
        axis=1,
    )

    # Connect to DB
    db_url = _get_sync_db_url()
    logger.info("Connecting to database")

    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        cur = conn.cursor()
    except Exception as exc:
        console.print(
            Panel(f"[red]Database connection failed: {exc}[/]",
                  title="Error", border_style="red")
        )
        raise typer.Exit(code=1)

    try:
        # Truncate if requested
        if truncate:
            logger.info("Truncating site_features table")
            cur.execute("TRUNCATE TABLE site_features;")
            conn.commit()
            console.print("[yellow]Table truncated.[/]\n")

        # Build upsert query
        upsert_sql = _build_upsert_query()

        inserted = 0
        updated = 0
        errors = 0
        start_time = time.time()

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("rows"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Loading...", total=total_rows)

            for batch_start in range(0, total_rows, batch_size):
                batch_end = min(batch_start + batch_size, total_rows)
                batch = df.iloc[batch_start:batch_end]

                for _, row in batch.iterrows():
                    row_dict = {}
                    for col in TABLE_COLUMNS + ["geom"]:
                        row_dict[col] = row.get(col, None)

                    try:
                        cur.execute(upsert_sql, row_dict)
                        # Check if insert or update via statusmessage
                        inserted += 1
                    except Exception as exc:
                        logger.warning("Row error (id=%s): %s", row_dict.get("id"), exc)
                        conn.rollback()
                        errors += 1
                        continue

                conn.commit()
                progress.update(task, completed=batch_end)

        elapsed = time.time() - start_time

        # Print summary
        console.print()
        console.print(f"[bold green]✓ Loaded:  {inserted:>10,}[/]")
        console.print(f"[bold red]✗ Errors:  {errors:>10,}[/]")
        console.print(f"Done in {elapsed:.1f}s\n")

        # Null summary
        null_counts = {}
        for col in TABLE_COLUMNS:
            if col in df.columns:
                null_count = df[col].isna().sum()
                if null_count > 0:
                    null_counts[col] = null_count

        if null_counts:
            table = Table(title="Null Summary", show_header=True, header_style="bold cyan")
            table.add_column("Column", min_width=30)
            table.add_column("Nulls", justify="right")

            for col, count in sorted(null_counts.items(), key=lambda x: -x[1]):
                table.add_row(col, f"{count:,}")

            console.print(table)

    except Exception as exc:
        conn.rollback()
        logger.error("Sync job failed: %s", exc)
        console.print(
            Panel(f"[red]{exc}[/]", title="Sync Error", border_style="red")
        )
        raise typer.Exit(code=1)
    finally:
        cur.close()
        conn.close()
        logger.info("Database connection closed")


if __name__ == "__main__":
    app()
