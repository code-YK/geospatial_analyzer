# 🌍 GeoSpatial Site Readiness Analyzer

An AI-powered location intelligence platform that evaluates and scores geographic sites for business use cases using precomputed geospatial features, a deterministic scoring engine, and LangGraph multi-agent orchestration.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Agent Graph](#agent-graph)
- [Scoring Engine](#scoring-engine)
- [Data Layer](#data-layer)
- [API Reference](#api-reference)
- [CLI Interface](#cli-interface)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Configuration](#configuration)
- [Getting Started](#getting-started)
- [Design Decisions](#design-decisions)

---

## Overview

The system answers a simple question: **"How suitable is this location for my business?"**

Given a latitude/longitude and a business use case (retail, EV charging, warehouse, telecom, renewable energy), it:

1. Resolves the location to an **H3 hexagonal grid cell** (resolution 8)
2. Fetches **71 precomputed geospatial features** from PostgreSQL
3. Applies a **weighted scoring formula** across 6 dimensions
4. Generates an **explainable score breakdown** (strengths, weaknesses, contributions)
5. Produces a **natural language insight** via LLM

All intelligence flows through a **LangGraph state graph** — API routes never call tools directly.

---

## Architecture

```mermaid
graph TB
    subgraph Entry Points
        A["FastAPI<br/>(main.py)"]
        B["Rich CLI<br/>(cli.py)"]
        C["LangGraph Studio<br/>(langgraph.json)"]
    end

    subgraph LangGraph StateGraph
        D["orchestrator"]
        E["advisory"]
        F["fetch_features"]
        G["fetch_scores"]
        H["compute_score"]
        I["geospatial"]
        J["explainability"]
        K["insight"]
        L["error_handler"]
    end

    subgraph Backend
        M["Tools Layer"]
        N["Scoring Engine"]
        O["LLM - Groq"]
        P[("PostgreSQL + PostGIS")]
    end

    A --> D
    B --> D
    C --> D
    D --> E
    D --> F
    D --> I
    D --> L
    E --> F
    F --> G
    F -.->|err| L
    G --> H
    G -.->|err| L
    H --> J
    H -.->|err| L
    I --> K
    J --> K
    J -.->|err| L
    L --> END["__end__"]
    K --> END

    F -.-> M
    G -.-> M
    H -.-> N
    E -.-> O
    K -.-> O
    M -.-> P
```

### Key Principles

| Principle | Implementation |
|---|---|
| **Graph-first** | All routes call the LangGraph graph — never tools or scoring directly |
| **LLM isolation** | LLM is called in only 2 nodes: `advisory` and `insight` |
| **Deterministic scoring** | The scoring engine has zero randomness, zero LLM calls |
| **Explainability** | Every score includes per-dimension contribution breakdown |
| **Swappable LLM** | Change `LLM_PROVIDER` in `.env` — no code changes needed |

---

## Agent Graph

The system uses a **LangGraph StateGraph** with 9 nodes and conditional routing. Every pipeline node checks for errors and routes to `error_handler` on failure.

```mermaid
flowchart TD
    START(["__start__"]) --> orchestrator

    orchestrator --> advisory
    orchestrator --> fetch_features
    orchestrator --> geospatial
    orchestrator --> error_handler

    advisory --> fetch_features

    fetch_features -->|ok| fetch_scores
    fetch_features -.->|err| error_handler

    fetch_scores -->|ok| compute_score
    fetch_scores -.->|err| error_handler

    compute_score -->|ok| explainability
    compute_score -.->|err| error_handler

    explainability -->|ok| insight
    explainability -.->|err| error_handler

    geospatial --> insight

    insight --> END(["__end__"])
    error_handler --> END

    style START fill:#1a1a2e,stroke:#e94560,color:#fff
    style END fill:#1a1a2e,stroke:#e94560,color:#fff
    style orchestrator fill:#16213e,stroke:#0f3460,color:#e0e0e0
    style advisory fill:#2d2d0f,stroke:#b8860b,color:#ffd700
    style fetch_features fill:#0d3320,stroke:#2e8b57,color:#90ee90
    style fetch_scores fill:#0d3320,stroke:#2e8b57,color:#90ee90
    style compute_score fill:#0d3320,stroke:#2e8b57,color:#90ee90
    style geospatial fill:#1a1a3e,stroke:#6a5acd,color:#b8b8ff
    style explainability fill:#2d1a1a,stroke:#cd5c5c,color:#ffb6b6
    style insight fill:#1a1a3e,stroke:#6a5acd,color:#b8b8ff
    style error_handler fill:#2d1a1a,stroke:#8b0000,color:#ff6b6b
```

### Nodes

| Node | File | LLM? | Purpose |
|---|---|---|---|
| `orchestrator` | `agents/orchestrator.py` | ❌ | Validate input, detect intent, route |
| `advisory` | `agents/advisory.py` | ✅ | Recommend scoring weights for use case |
| `fetch_features` | `agents/graph.py` | ❌ | Fetch 71-column row from PostgreSQL |
| `fetch_scores` | `agents/graph.py` | ❌ | Fetch Layer 7 precomputed scores |
| `compute_score` | `agents/graph.py` | ❌ | Weighted-sum final score calculation |
| `geospatial` | `agents/geospatial.py` | ❌ | Hotspot detection, catchment analysis |
| `explainability` | `agents/graph.py` | ❌ | Score breakdown with strengths/weaknesses |
| `insight` | `agents/insight.py` | ✅ | Natural language insight from structured data |
| `error_handler` | `agents/graph.py` | ❌ | Graceful error formatting |

### Intent Routing

The orchestrator detects intent **deterministically** (no LLM) based on the request shape:

```mermaid
flowchart LR
    O["orchestrator"] --> |advise_weights| A["advisory → fetch_features → fetch_scores → compute_score → explainability → insight"]
    O --> |score_site| B["fetch_features → fetch_scores → compute_score → explainability → insight"]
    O --> |compare_sites| C["fetch_features → fetch_scores → compute_score → explainability → insight"]
    O --> |find_hotspots| D["geospatial → insight"]
    O --> |explain_result| E["fetch_features → fetch_scores → explainability → insight"]
    O --> |error| F["error_handler"]
```

### State Schema

```python
class AgentState(TypedDict, total=False):
    # Input
    thread_id: str
    use_case: str                            # "retail" | "ev_charging" | "warehouse" | "telecom" | "renewable"
    site_input: SiteInput                    # lat, lng, optional h3_id
    user_weights: Optional[WeightConfig]     # 6 weights (0.0–1.0, sum=1.0)

    # Routing
    intent: str                              # detected by orchestrator
    current_node: str
    error: Optional[str]

    # Data (populated progressively)
    site_features: Optional[SiteFeatures]
    precomputed_scores: Optional[PrecomputedScores]
    final_score: Optional[float]
    score_breakdown: Optional[ScoreBreakdown]
    comparison_results: Optional[List[SiteScore]]
    hotspot_results: Optional[List[HotspotResult]]

    # Output
    insight_text: str
    advisory_text: Optional[str]
    recommended_weights: Optional[WeightConfig]
```

---

## Scoring Engine

Located in `scoring/engine.py`. **Purely deterministic** — no LLM, no randomness, no external calls.

### Formula

```
site_readiness_score = Σ (dimension_score_i × weight_i)
```

Where `i` ∈ `{demand, accessibility, competition, suitability, risk, infrastructure}`

- Each dimension score is **0–100** (precomputed by ETL pipeline)
- Each weight is **0.0–1.0** (sum = 1.0)
- Output: **0–100**

### Default Weights by Use Case

| Use Case | Demand | Accessibility | Competition | Suitability | Risk | Infrastructure |
|---|---|---|---|---|---|---|
| Retail | 0.30 | 0.20 | 0.20 | 0.10 | 0.10 | 0.10 |
| EV Charging | 0.25 | 0.30 | 0.05 | 0.10 | 0.10 | 0.20 |
| Warehouse | 0.15 | 0.35 | 0.05 | 0.15 | 0.15 | 0.15 |
| Telecom | 0.10 | 0.25 | 0.10 | 0.15 | 0.15 | 0.25 |
| Renewable | 0.10 | 0.20 | 0.05 | 0.25 | 0.20 | 0.20 |

### Explainability Output

Every score returns a breakdown:
```json
{
  "site_readiness_score": 72.4,
  "contributions": {
    "demand_score":         {"raw": 74, "weight": 0.25, "contribution": 18.5, "rank": 1},
    "accessibility_score":  {"raw": 71, "weight": 0.20, "contribution": 14.2, "rank": 2},
    "infrastructure_score": {"raw": 66, "weight": 0.15, "contribution": 9.9,  "rank": 3},
    "suitability_score":    {"raw": 68, "weight": 0.15, "contribution": 10.2, "rank": 4},
    "competition_score":    {"raw": 55, "weight": 0.15, "contribution": 8.25, "rank": 5},
    "risk_score":           {"raw": 60, "weight": 0.10, "contribution": 6.0,  "rank": 6}
  },
  "strengths": ["demand_score", "accessibility_score"],
  "weaknesses": ["risk_score", "competition_score"]
}
```

### Supporting Modules

| Module | Purpose |
|---|---|
| `scoring/normalizer.py` | Min-max, clipped, and inverted normalization |
| `scoring/formulas.py` | Distance decay functions (inverse-square, exponential, linear) |
| `scoring/weights.py` | Hardcoded default weight configs per use case |

---

## Data Layer

### Database: PostgreSQL 15+ with PostGIS

Single table: `site_features` with **71 data columns** across 7 layers:

| Layer | Category | Columns | Source |
|---|---|---|---|
| 0 | Identifiers | `id`, `grid_id`, `latitude`, `longitude`, `state`, `district`, `area_name` | H3 grid |
| 1 | Demographics | `population_*`, `sex_ratio`, `dependency_ratio`, `household_count`, etc. | WorldPop, Census 2011, VIIRS |
| 2 | Transportation | `road_density`, `distance_to_highway`, `connectivity_score`, etc. | OSM, OSRM |
| 3 | POI / Economic | `poi_count_*`, `competitor_count`, `restaurant_count`, `shop_count`, etc. | OSM |
| 4 | Land Use | `commercial_ratio`, `residential_ratio`, `building_density`, etc. | OSM |
| 5 | Environment / Risk | `aqi`, `pm25`, `flood_risk_score`, `earthquake_risk_score`, etc. | OpenAQ, GDACS, NASA |
| 6 | Infrastructure | `distance_to_power_substation`, `public_transport_score`, etc. | OSM |
| 7 | Derived Scores | `demand_score`, `accessibility_score`, ... (6 scores, 0–100) | ETL pipeline |

### H3 Spatial Indexing

- All locations are resolved to **H3 resolution 8** hexagons (~0.74 km² per cell)
- Lookup is **O(1)** by `grid_id` — no `ST_NearestNeighbor` needed
- H3 Python library handles `lat/lng → grid_id` conversion
- PostGIS is used only for spatial queries (`ST_DWithin` for catchment analysis)

### Important Notes

- **`competitor_count`** is stored as-is from the pipeline. At query time, the scoring engine can override it dynamically based on `use_case` → relevant POI category columns
- All **Layer 7 scores are precomputed** by the ETL pipeline — the backend reads them directly, does not recompute them

---

## API Reference

All routes are **async** and call the LangGraph graph (never tools directly).

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `GET` | `/sites/{h3_id}` | Fetch all features for an H3 cell |
| `GET` | `/sites/nearest/?lat=&lng=` | Find nearest H3 cell by coordinates |
| `POST` | `/score` | Score a single site (full graph run) |
| `POST` | `/score/what-if` | Compare two weight configurations |
| `POST` | `/compare` | Compare and rank 2–5 sites |
| `POST` | `/hotspots` | Find top hotspot locations in a state |

### Example: Score a Site

```bash
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "site_input": {"lat": 23.0225, "lng": 72.5714},
    "use_case": "ev_charging"
  }'
```

Response includes `site_score`, `score_breakdown`, `insight_text`, and optional `advisory_text`.

### Example: Compare Sites

```bash
curl -X POST http://localhost:8000/compare \
  -H "Content-Type: application/json" \
  -d '{
    "sites": [
      {"lat": 23.0225, "lng": 72.5714},
      {"lat": 23.0300, "lng": 72.5800},
      {"lat": 22.9900, "lng": 72.5500}
    ],
    "use_case": "retail"
  }'
```

### Example: Find Hotspots

```bash
curl -X POST http://localhost:8000/hotspots \
  -H "Content-Type: application/json" \
  -d '{
    "state": "Gujarat",
    "use_case": "ev_charging",
    "top_n": 10
  }'
```

---

## CLI Interface

Interactive menu-based CLI built with **Rich** + **Typer**.

```
╔══════════════════════════════════════╗
║   GeoSpatial Site Readiness Analyzer ║
╚══════════════════════════════════════╝

  1. Score a site
  2. Compare multiple sites
  3. Find hotspots in a state
  4. Exit
```

### Features

- **Guided input** — step-by-step prompts for location, use case, and weights
- **Visual score bar** — `▓▓▓▓▓▓░░░░` progress indicator for the readiness score
- **Rich tables** — comparison and hotspot results in formatted tables
- **Score breakdown** — per-dimension contribution with `████` visual bars
- **Spinner progress** — animated "Running analysis..." during graph execution
- **Error panels** — friendly red panels for errors (no raw stack traces)

Each CLI run generates a fresh `thread_id` (UUID4) — stateless per run.

---

## Project Structure

```
geo_site_v2/
├── main.py                       # FastAPI app entry point
├── cli.py                        # Menu-based CLI (Typer + Rich)
├── pyproject.toml                # Dependencies & project config
├── requirements.txt              # pip-compatible dependency list
├── alembic.ini                   # Alembic migration config
├── langgraph.json                # LangGraph Studio configuration
├── .env.example                  # Environment variable template
├── SETUP.md                      # Database setup & install guide
├── README.md                     # This file
│
├── migrations/                   # Alembic database migrations
│   ├── env.py                    # Migration environment (reads .env)
│   ├── script.py.mako            # Migration file template
│   └── versions/
│       └── 001_initial_schema.py # First migration: site_features table
│
├── logs/                         # Application logs (gitignored)
│   └── agent_app.log             # Rotating log file (5MB × 3 backups)
│
├── core/                         # Configuration & infrastructure
│   ├── config.py                 # pydantic-settings (.env loader)
│   ├── database.py               # Async SQLAlchemy engine + session factory
│   ├── logger.py                 # Centralized logging (setup_logging + get_logger)
│   └── exceptions.py             # 7 custom exception classes
│
├── llm/                          # LLM abstraction layer
│   ├── llm_config.py             # Provider-agnostic factory (Groq/OpenAI/Anthropic/Ollama)
│   └── prompts.py                # All system/user prompt templates
│
├── agents/                       # LangGraph multi-agent system
│   ├── state.py                  # AgentState TypedDict
│   ├── graph.py                  # StateGraph definition (9 nodes, conditional edges)
│   ├── orchestrator.py           # Deterministic intent routing (no LLM)
│   ├── advisory.py               # LLM weight advisor node
│   ├── geospatial.py             # Spatial operations node (no LLM)
│   └── insight.py                # LLM insight generator node
│
├── scoring/                      # Deterministic scoring engine
│   ├── engine.py                 # Weighted-sum computation + contributions
│   ├── normalizer.py             # Min-max, clipped, inverted normalization
│   ├── weights.py                # Default weight configs (5 use cases)
│   └── formulas.py               # Distance decay functions
│
├── tools/                        # Tool functions (called by agent nodes)
│   ├── site_tools.py             # DB fetch: features + precomputed scores
│   ├── scoring_tools.py          # Score computation + ranking wrappers
│   ├── spatial_tools.py          # H3 utils, hotspot detection, catchment analysis
│   ├── explainability_tools.py   # Score breakdown + what-if analysis
│   └── config_tools.py           # Weight validation + normalization
│
├── models/                       # Pydantic v2 data models
│   ├── site.py                   # SiteFeatures (71 cols), SiteScore, ScoreBreakdown, etc.
│   ├── weights.py                # WeightConfig (sum-to-1.0 validator)
│   ├── request.py                # API request/response schemas
│   └── agent.py                  # Agent I/O models
│
└── api/                          # FastAPI route layer
    ├── dependencies.py           # DB session injection, auth placeholder
    └── routes/
        ├── sites.py              # GET /sites/{h3_id}, GET /sites/nearest
        ├── scoring.py            # POST /score, POST /score/what-if
        ├── comparison.py         # POST /compare
        └── hotspots.py           # POST /hotspots
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| API Framework | FastAPI + Uvicorn |
| Agent Framework | LangGraph 0.2+ |
| LLM Provider | Groq (`llama-3.3-70b-versatile`) — swappable |
| Database | PostgreSQL 15+ with PostGIS |
| ORM / Queries | SQLAlchemy 2.0 (async) + raw SQL for spatial ops |
| Schema Validation | Pydantic v2 |
| Spatial Indexing | H3 Python library (resolution 8) |
| CLI | Rich + Typer |
| Config | pydantic-settings + `.env` |
| Observability | LangSmith tracing (via LangGraph Studio) |

---

## Configuration

All configuration is managed through **environment variables** loaded via `pydantic-settings`.

### Required Variables

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/geospatial_db

# LLM (default: Groq)
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY=your_key_here

# LangSmith (for LangGraph Studio)
LANGSMITH_API_KEY=your_key_here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=geospatial-analyzer
```

### Swapping LLM Providers

Only `llm/llm_config.py` and `.env` need to change:

| Provider | `LLM_PROVIDER` | Required Key |
|---|---|---|
| Groq (default) | `groq` | `GROQ_API_KEY` |
| OpenAI | `openai` | `OPENAI_API_KEY` |
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` |
| Ollama (local) | `ollama` | — |

---

## Getting Started

```bash
# 1. Clone and navigate
cd geo_site_v2

# 2. Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1    # Windows PowerShell

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your DB credentials and GROQ_API_KEY

# 5. Set up PostgreSQL (see SETUP.md for full schema)

# 6. Start API server
uvicorn main:app --reload --port 8000

# 7. Or run CLI
python -m cli

# 8. Or run in LangGraph Studio
pip install "langgraph-cli[inmem]"
langgraph dev
```

For detailed database setup and SQL schema, see **[SETUP.md](./SETUP.md)**.

---

## Design Decisions

### Why LangGraph over plain function chains?

- **State persistence** — Postgres checkpointer enables debugging and replay
- **Conditional routing** — Intent-based graph traversal without spaghetti if/else
- **Observability** — LangGraph Studio visualizes execution in real-time
- **Extensibility** — New nodes (e.g., a "competitor analysis" agent) can be added without rewiring existing logic

### Why H3 over raw lat/lng lookups?

- **O(1) lookup** — `grid_id` primary key vs. O(n) nearest-neighbor scans
- **Consistent aggregation** — Equal-area hexagons enable fair comparison across sites
- **Neighbor queries** — `h3.grid_disk()` gives k-ring neighbors without DB round-trips

### Why deterministic scoring?

- **Reproducibility** — Same inputs always produce the same score
- **Auditability** — Every contribution is traceable (`raw × weight = contribution`)
- **Speed** — No LLM call needed for the core calculation
- **LLM for interpretation only** — The insight node converts numbers to narrative, it doesn't generate numbers

### Why two LLM nodes, not one?

- **Advisory** specializes in weight recommendation (structured JSON output)
- **Insight** specializes in natural language summarization (free-form text)
- Different system prompts, different output formats, different failure modes
- Each has its own graceful fallback (defaults for advisory, template for insight)

---

## License

This project is proprietary. For licensing inquiries, contact the project maintainers.
