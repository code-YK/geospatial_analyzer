"""
cli.py — Menu-based CLI using Typer + Rich.

Stateless per run: each execution generates a new thread_id (UUID4).
"""

import asyncio
import uuid
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, FloatPrompt, IntPrompt, Prompt
from rich.table import Table

from agents.graph import get_compiled_graph
from core.config import get_settings
from core.logger import setup_logging, get_logger
from models.site import SiteInput
from models.weights import WeightConfig
from scoring.weights import USE_CASE_WEIGHTS, VALID_USE_CASES
from tools.config_tools import get_default_weights

# Initialize logging early
settings = get_settings()
setup_logging(log_level=settings.log_level)
logger = get_logger(__name__)

app = typer.Typer(
    name="geo-cli",
    help="GeoSpatial Site Readiness Analyzer — CLI Interface",
    add_completion=False,
)
console = Console()

USE_CASE_LABELS = {
    "retail": "Retail store",
    "ev_charging": "EV charging station",
    "warehouse": "Warehouse / logistics",
    "telecom": "Telecom tower",
    "renewable": "Renewable energy",
}


# ── Helpers ───────────────────────────────────────────────────────────────

def _show_banner():
    """Display the application banner."""
    console.print(
        Panel.fit(
            "[bold bright_cyan]GeoSpatial Site Readiness Analyzer[/]",
            border_style="bright_cyan",
            padding=(1, 4),
        )
    )
    console.print()


def _select_use_case() -> str:
    """Prompt user to select a business use case."""
    console.print("[bold]Select use case:[/]")
    for i, (key, label) in enumerate(USE_CASE_LABELS.items(), 1):
        console.print(f"  {i}. {label}")
    console.print()

    choice = IntPrompt.ask("Enter choice", default=1)
    keys = list(USE_CASE_LABELS.keys())
    idx = max(0, min(choice - 1, len(keys) - 1))
    selected = keys[idx]
    console.print(f"  ✓ Selected: [bold green]{USE_CASE_LABELS[selected]}[/]\n")
    return selected


def _get_site_input() -> SiteInput:
    """Prompt user for site location."""
    console.print("[bold]Step 1/3 — Site Location[/]")
    lat = FloatPrompt.ask("  Enter latitude", default=23.0225)
    lng = FloatPrompt.ask("  Enter longitude", default=72.5714)
    console.print()
    return SiteInput(lat=lat, lng=lng)


def _get_weights(use_case: str) -> Optional[WeightConfig]:
    """Prompt user for scoring weights or use defaults."""
    console.print("[bold]Step 3/3 — Scoring Weights[/]")
    defaults = get_default_weights(use_case)
    use_defaults = Confirm.ask(
        f"  Use default weights for {USE_CASE_LABELS.get(use_case, use_case)}?",
        default=True,
    )

    if use_defaults:
        console.print("  ✓ Using default weights\n")
        return defaults

    console.print("\n  Enter weights (must sum to 1.0):")
    demand = FloatPrompt.ask(f"    Demand score weight       [default: {defaults.demand_score}]", default=defaults.demand_score)
    accessibility = FloatPrompt.ask(f"    Accessibility score weight [default: {defaults.accessibility_score}]", default=defaults.accessibility_score)
    competition = FloatPrompt.ask(f"    Competition score weight  [default: {defaults.competition_score}]", default=defaults.competition_score)
    suitability = FloatPrompt.ask(f"    Suitability score weight  [default: {defaults.suitability_score}]", default=defaults.suitability_score)
    risk = FloatPrompt.ask(f"    Risk score weight         [default: {defaults.risk_score}]", default=defaults.risk_score)
    infrastructure = FloatPrompt.ask(f"    Infrastructure score weight [default: {defaults.infrastructure_score}]", default=defaults.infrastructure_score)

    total = demand + accessibility + competition + suitability + risk + infrastructure
    console.print(f"\n  Weights sum: [bold]{total:.2f}[/]")

    if not (0.99 <= total <= 1.01):
        console.print("[red]  ✗ Weights do not sum to 1.0. Using defaults instead.[/]\n")
        return defaults

    console.print("[green]  ✓ Weights valid[/]\n")
    return WeightConfig(
        demand_score=demand,
        accessibility_score=accessibility,
        competition_score=competition,
        suitability_score=suitability,
        risk_score=risk,
        infrastructure_score=infrastructure,
    )


def _render_score_result(result: dict):
    """Render a single-site scoring result."""
    final_score = result.get("final_score", 0)
    breakdown = result.get("score_breakdown")
    insight = result.get("insight_text", "")
    advisory = result.get("advisory_text")

    # Score panel
    bar_filled = int(final_score / 100 * 20)
    bar = "▓" * bar_filled + "░" * (20 - bar_filled)
    console.print(
        Panel(
            f"[bold white]Site Readiness Score: {final_score:.1f} / 100   {bar}[/]",
            border_style="bright_green" if final_score >= 60 else "yellow",
            padding=(1, 2),
        )
    )

    # Score breakdown table
    if breakdown:
        table = Table(title="Score Breakdown", show_header=True, header_style="bold cyan")
        table.add_column("Dimension", style="white", min_width=20)
        table.add_column("Raw", justify="right")
        table.add_column("Weight", justify="right")
        table.add_column("Contribution", justify="right")
        table.add_column("Visual", min_width=10)

        for dim, contrib in breakdown.contributions.items():
            bar_len = int(contrib.contribution / 25 * 10)
            visual = "█" * max(1, bar_len)
            dim_label = dim.replace("_", " ").title()
            table.add_row(
                dim_label,
                f"{contrib.raw:.0f}",
                f"{contrib.weight:.2f}",
                f"{contrib.contribution:.1f}",
                f"[green]{visual}[/]",
            )

        console.print(table)
        console.print()

        # Strengths / Weaknesses
        console.print(f"  [bold green]Strengths:[/] {', '.join(breakdown.strengths)}")
        console.print(f"  [bold red]Weaknesses:[/] {', '.join(breakdown.weaknesses)}")
        console.print()

    # Advisory text
    if advisory:
        console.print(
            Panel(advisory, title="Advisory", border_style="bright_blue", padding=(0, 1))
        )

    # Insight text
    if insight:
        console.print(
            Panel(insight, title="Insight", border_style="bright_magenta", padding=(0, 1))
        )


def _render_comparison(result: dict):
    """Render a multi-site comparison table."""
    ranked = result.get("comparison_results", [])
    insight = result.get("insight_text", "")

    table = Table(title="Site Comparison (Ranked)", show_header=True, header_style="bold cyan")
    table.add_column("Rank", justify="center", width=5)
    table.add_column("Site ID", min_width=18)
    table.add_column("Lat", justify="right")
    table.add_column("Lng", justify="right")
    table.add_column("Score", justify="right", style="bold")

    for i, site in enumerate(ranked, 1):
        style = "bold green" if i == 1 else "white"
        table.add_row(
            f"#{i}",
            site.id,
            f"{site.lat:.4f}",
            f"{site.lng:.4f}",
            f"{site.site_readiness_score:.1f}",
            style=style,
        )

    console.print(table)
    console.print()

    if insight:
        console.print(
            Panel(insight, title="Insight", border_style="bright_magenta", padding=(0, 1))
        )


def _render_hotspots(result: dict):
    """Render hotspot detection results."""
    hotspots = result.get("hotspot_results", [])
    insight = result.get("insight_text", "")

    table = Table(title="Top Hotspot Locations", show_header=True, header_style="bold cyan")
    table.add_column("Rank", justify="center", width=5)
    table.add_column("District", min_width=15)
    table.add_column("State", min_width=12)
    table.add_column("Site ID", min_width=18)
    table.add_column("Score", justify="right", style="bold")

    for i, hs in enumerate(hotspots, 1):
        style = "bold green" if i == 1 else "white"
        table.add_row(
            f"#{i}",
            hs.district,
            hs.state,
            hs.id,
            f"{hs.site_readiness_score:.1f}",
            style=style,
        )

    console.print(table)
    console.print()

    if insight:
        console.print(
            Panel(insight, title="Insight", border_style="bright_magenta", padding=(0, 1))
        )


# ── Graph Runner ──────────────────────────────────────────────────────────

async def _run_graph(initial_state: dict, checkpointer=None) -> dict:
    """Run the LangGraph graph and return the final state."""
    compiled = get_compiled_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": initial_state.get("thread_id", "cli")}}
    return await compiled.ainvoke(initial_state, config=config)


# ── CLI Flows (async) ────────────────────────────────────────────────────

async def _flow_score_site(checkpointer=None):
    """Flow 1: Score a single site."""
    site_input = _get_site_input()

    console.print("[bold]Step 2/3 — Use Case[/]")
    use_case = _select_use_case()

    weights = _get_weights(use_case)

    thread_id = str(uuid.uuid4())

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Running analysis...", total=None)

        initial_state = {
            "thread_id": thread_id,
            "use_case": use_case,
            "site_input": site_input,
            "user_weights": weights,
        }

        try:
            result = await _run_graph(initial_state, checkpointer=checkpointer)
        except Exception as exc:
            console.print(Panel(f"[red]{exc}[/]", title="Error", border_style="red"))
            return

    error = result.get("error")
    if error:
        console.print(Panel(f"[red]{error}[/]", title="Error", border_style="red"))
        return

    _render_score_result(result)


async def _flow_compare_sites(checkpointer=None):
    """Flow 2: Compare multiple sites."""
    console.print("[bold]Compare Multiple Sites[/]\n")
    num_sites = IntPrompt.ask("  How many sites to compare? (2–5)", default=2)
    num_sites = max(2, min(5, num_sites))

    sites = []
    for i in range(num_sites):
        console.print(f"\n  [bold]Site {i + 1}:[/]")
        lat = FloatPrompt.ask("    Latitude", default=23.0225)
        lng = FloatPrompt.ask("    Longitude", default=72.5714)
        sites.append(SiteInput(lat=lat, lng=lng))

    console.print()
    use_case = _select_use_case()
    weights = _get_weights(use_case)

    thread_id = str(uuid.uuid4())

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Comparing sites...", total=None)

        initial_state = {
            "thread_id": thread_id,
            "use_case": use_case,
            "site_input": sites[0],
            "user_weights": weights,
            "comparison_sites": sites[1:],
        }

        try:
            result = await _run_graph(initial_state, checkpointer=checkpointer)
        except Exception as exc:
            console.print(Panel(f"[red]{exc}[/]", title="Error", border_style="red"))
            return

    error = result.get("error")
    if error:
        console.print(Panel(f"[red]{error}[/]", title="Error", border_style="red"))
        return

    _render_comparison(result)


async def _flow_find_hotspots(checkpointer=None):
    """Flow 3: Find hotspots in a state."""
    console.print("[bold]Find Hotspots[/]\n")
    state_name = Prompt.ask("  Enter state name", default="Gujarat")

    use_case = _select_use_case()
    weights = _get_weights(use_case)

    thread_id = str(uuid.uuid4())

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Detecting hotspots...", total=None)

        # For hotspots we pass a dummy site_input
        initial_state = {
            "thread_id": thread_id,
            "use_case": use_case,
            "site_input": None,
            "user_weights": weights,
            "state_name": state_name,
        }

        try:
            result = await _run_graph(initial_state, checkpointer=checkpointer)
        except Exception as exc:
            console.print(Panel(f"[red]{exc}[/]", title="Error", border_style="red"))
            return

    error = result.get("error")
    if error:
        console.print(Panel(f"[red]{error}[/]", title="Error", border_style="red"))
        return

    _render_hotspots(result)


async def _flow_explain_result(checkpointer=None):
    """Flow 4: Re-explain a site score in detail."""
    console.print("[bold]Explain Site Score[/]\n")
    site_input = _get_site_input()
    console.print("[bold]Step 2/3 — Use Case[/]")
    use_case = _select_use_case()
    weights = _get_weights(use_case)
    thread_id = str(uuid.uuid4())

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating explanation...", total=None)

        initial_state = {
            "thread_id": thread_id,
            "use_case": use_case,
            "site_input": site_input,
            "user_weights": weights,
            "request_explanation": True,
        }

        try:
            result = await _run_graph(initial_state, checkpointer=checkpointer)
        except Exception as exc:
            console.print(Panel(f"[red]{exc}[/]", title="Error", border_style="red"))
            return

    error = result.get("error")
    if error:
        console.print(Panel(f"[red]{error}[/]", title="Error", border_style="red"))
        return

    _render_score_result(result)


# ── Async Main Loop ──────────────────────────────────────────────────────

async def _create_checkpointer_safe():
    """Create checkpointer with graceful fallback."""
    from agents.graph import create_checkpointer
    return await create_checkpointer()


async def _async_main():
    """Async entry point — single event loop for the entire CLI session."""
    # Initialize checkpointer once
    checkpointer = None
    try:
        checkpointer = await _create_checkpointer_safe()
    except Exception as exc:
        logger.warning("Checkpointer unavailable, running without persistence: %s", exc)
        checkpointer = None

    while True:
        console.print("[bold]Main Menu[/]")
        console.print("  1. Score a site")
        console.print("  2. Compare multiple sites")
        console.print("  3. Find hotspots in a state")
        console.print("  4. Explain a site score in detail")
        console.print("  5. Exit")
        console.print()

        choice = IntPrompt.ask("Enter choice", default=1)

        console.print()

        if choice == 1:
            try:
                await _flow_score_site(checkpointer=checkpointer)
            except Exception as exc:
                console.print(Panel(f"[red]{exc}[/]", title="Error", border_style="red"))

        elif choice == 2:
            try:
                await _flow_compare_sites(checkpointer=checkpointer)
            except Exception as exc:
                console.print(Panel(f"[red]{exc}[/]", title="Error", border_style="red"))

        elif choice == 3:
            try:
                await _flow_find_hotspots(checkpointer=checkpointer)
            except Exception as exc:
                console.print(Panel(f"[red]{exc}[/]", title="Error", border_style="red"))

        elif choice == 4:
            try:
                await _flow_explain_result(checkpointer=checkpointer)
            except Exception as exc:
                console.print(Panel(f"[red]{exc}[/]", title="Error", border_style="red"))

        elif choice == 5:
            console.print("[bold bright_cyan]Goodbye! 👋[/]")
            raise typer.Exit()

        else:
            console.print("[yellow]Invalid choice. Please try again.[/]")

        console.print()


# ── Main Menu ─────────────────────────────────────────────────────────────

@app.command()
def main():
    """GeoSpatial Site Readiness Analyzer — Interactive CLI."""
    _show_banner()
    asyncio.run(_async_main())


if __name__ == "__main__":
    app()
