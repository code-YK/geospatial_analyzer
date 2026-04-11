"""
cli.py — Conversational CLI using Rich.

All logic is in the chat_node — the CLI is just a simple REPL.
"""

import asyncio
import uuid

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

from agents.graph import get_compiled_graph
from core.config import get_settings
from core.logger import setup_logging, get_logger

# Initialize logging early
settings = get_settings()
setup_logging(log_level=settings.log_level)
logger = get_logger(__name__)

app = typer.Typer(
    name="geo-cli",
    help="GeoSpatial Site Readiness Analyzer — Conversational CLI",
    add_completion=False,
)
console = Console()


# ── Helpers ───────────────────────────────────────────────────────────────

def _show_banner():
    """Display the application banner."""
    console.print(
        Panel.fit(
            "[bold bright_cyan]GeoSpatial Site Readiness Analyzer[/]\n"
            "[dim]Ask me anything — 'Score a retail site at 23.02, 72.57' "
            "or 'Find EV hotspots in Gujarat'[/]",
            border_style="bright_cyan",
            padding=(1, 4),
        )
    )
    console.print()


def _render_score_result(state: dict):
    """Render a single-site scoring result."""
    final_score = state.get("final_score", 0)
    breakdown = state.get("score_breakdown")
    advisory = state.get("advisory_text")

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

    # Validation warnings
    warnings = state.get("validation_warnings", [])
    if warnings:
        console.print("[bold yellow]⚠ Regulatory Warnings:[/]")
        for w in warnings:
            console.print(f"  [yellow]• {w}[/]")
        console.print()

    # Advisory text
    if advisory:
        console.print(
            Panel(advisory, title="Advisory", border_style="bright_blue", padding=(0, 1))
        )


def _render_comparison(state: dict):
    """Render a multi-site comparison table."""
    ranked = state.get("comparison_results", [])
    insight = state.get("insight_text", "")

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


def _render_hotspots(state: dict):
    """Render hotspot detection results."""
    hotspots = state.get("hotspot_results", [])

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


# ── Graph Runner ──────────────────────────────────────────────────────────

async def _run_graph(state: dict, checkpointer=None) -> dict:
    """Run the LangGraph graph and return the final state."""
    compiled = get_compiled_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": state.get("thread_id", "cli")}}
    return await compiled.ainvoke(state, config=config)


# ── Chat Loop ─────────────────────────────────────────────────────────────

async def _create_checkpointer_safe():
    """Create checkpointer with graceful fallback."""
    from agents.graph import create_checkpointer
    return await create_checkpointer()


async def _async_main():
    """Async entry point — conversational chat REPL."""
    # Initialize checkpointer once
    checkpointer = None
    try:
        checkpointer = await _create_checkpointer_safe()
    except Exception as exc:
        logger.warning("Checkpointer unavailable, running without persistence: %s", exc)
        checkpointer = None

    thread_id = str(uuid.uuid4())

    # Persistent state across the conversation
    state = {
        "conversation_history": [],
        "retry_count": 0,
        "analysis_complete": False,
        "thread_id": thread_id,
    }

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye! 👋[/]")
            break

        if user_input.strip().lower() in ("exit", "quit", "bye"):
            console.print("[bold bright_cyan]Goodbye! 👋[/]")
            break

        if not user_input.strip():
            continue

        state["raw_user_message"] = user_input

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task("Thinking...", total=None)
                result = await _run_graph(state, checkpointer=checkpointer)
        except Exception as exc:
            console.print(Panel(f"[red]{exc}[/]", title="Error", border_style="red"))
            continue

        # Update persistent state for next turn
        state["conversation_history"] = result.get("conversation_history", [])
        state["retry_count"] = result.get("retry_count", 0)
        state["analysis_complete"] = result.get("analysis_complete", False)

        # Carry forward analysis data for follow-up questions
        for key in ("site_features", "precomputed_scores", "final_score",
                     "score_breakdown", "site_input", "use_case", "state_name",
                     "comparison_results", "hotspot_results", "user_weights",
                     "validation_warnings"):
            if key in result:
                state[key] = result[key]

        # Display response
        response = (
            result.get("chat_response")
            or result.get("insight_text")
            or result.get("error")
            or "I didn't generate a response. Please try again."
        )
        console.print(f"\n[bold magenta]Analyzer[/]  {response}")

        # If analysis complete with score, show rich output
        if result.get("final_score") and result.get("score_breakdown"):
            _render_score_result(result)
        elif result.get("comparison_results"):
            _render_comparison(result)
        elif result.get("hotspot_results"):
            _render_hotspots(result)

        # Check session end
        error = result.get("error", "")
        if error and "Session ended" in error:
            break


# ── Main Entry Point ─────────────────────────────────────────────────────

@app.command()
def main():
    """GeoSpatial Site Readiness Analyzer — Conversational CLI."""
    _show_banner()
    asyncio.run(_async_main())


if __name__ == "__main__":
    app()
