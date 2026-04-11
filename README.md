# 🌍 GeoSpatial Site Readiness Analyzer

An AI-powered location intelligence platform that evaluates and scores geographic sites for business use cases using precomputed geospatial features, a deterministic scoring engine, and LangGraph multi-agent orchestration with conversational chat.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Agent Graph](#agent-graph)
- [Chat Interface](#chat-interface)
- [Validation Framework](#validation-framework)
- [Scoring Engine](#scoring-engine)
- [Use Case Catalog](#use-case-catalog)
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

Given a natural language query (e.g. *"Score a retail site at 23.02, 72.57"*), it:

1. **Parses intent** via the chat node — extracts lat/lng, use case, and weights from free text
2. **Validates** the site against legal, proximity, environmental, and viability rules
3. Finds the **nearest site** using PostGIS spatial indexing (`<->` operator)
4. Fetches **68 precomputed geospatial features** from PostgreSQL
5. Applies a **weighted scoring formula** across 6 dimensions
6. Generates an **explainable score breakdown** (strengths, weaknesses, contributions)
7. Produces a **natural language insight** via LLM

All intelligence flows through a **LangGraph state graph** — API routes never call tools directly.

### Supported Use Cases

**95 business types** across 15 categories: Necessity & Civic, Healthcare, Education, Food & Beverage, Retail, Energy & Fuel, Finance, Fun & Leisure, Hospitality, Industrial, Chemical, Logistics, Professional Services, Religious & Civic, and Agriculture.

---

## Architecture

```mermaid
graph TB
    subgraph Entry Points
        A["FastAPI<br/>(main.py)"]
        B["Chat CLI<br/>(cli.py)"]
        C["LangGraph Studio<br/>(langgraph.json)"]
    end

    subgraph LangGraph StateGraph
        D0["chat"]
        D["orchestrator"]
        E["advisory"]
        F["fetch_features"]
        G["fetch_scores"]
        V["validation"]
        H["compute_score"]
        I["geospatial"]
        J["explainability"]
        K["insight"]
        CR["chat_response"]
        L["error_handler"]
    end

    subgraph Backend
        M["Tools Layer"]
        N["Scoring Engine"]
        VT["Validation Tools"]
        O["LLM - Groq"]
        P[("PostgreSQL + PostGIS")]
    end

    A --> D0
    B --> D0
    C --> D0
    D0 --> D
    D0 -->|direct/follow-up| CR
    D --> E
    D --> F
    D --> I
    D --> L
    E --> F
    F --> G
    F -.->|err| L
    G --> V
    G -.->|err| L
    V --> H
    V -.->|block| L
    H --> J
    H -.->|err| L
    I --> K
    J --> K
    J -.->|err| L
    K --> CR
    CR --> END["__end__"]
    L --> END

    F -.-> M
    G -.-> M
    H -.-> N
    V -.-> VT
    E -.-> O
    K -.-> O
    D0 -.-> O
    M -.-> P
```

### Key Principles

| Principle | Implementation |
|---|---|
| **Chat-first** | All interactions start at the `chat` node — natural language in, structured analysis out |
| **Graph-first** | All routes call the LangGraph graph — never tools or scoring directly |
| **Validate before scoring** | Legal, proximity, environmental checks run before any score is computed |
| **LLM isolation** | LLM is called in only 3 nodes: `chat`, `advisory`, and `insight` |
| **Deterministic scoring** | The scoring engine has zero randomness, zero LLM calls |
| **Explainability** | Every score includes per-dimension contribution breakdown |
| **Swappable LLM** | Change `LLM_PROVIDER` in `.env` — no code changes needed |

---

## Agent Graph

The system uses a **LangGraph StateGraph** with 12 nodes and conditional routing. Every pipeline node checks for errors and routes to `error_handler` on failure.

```mermaid
flowchart TD
    START(["__start__"]) --> chat

    chat --> |needs_graph| orchestrator
    chat --> |direct_answer/follow_up| END_DIRECT(["__end__"])
    chat --> |off_topic| END_DIRECT

    orchestrator --> advisory
    orchestrator --> fetch_features
    orchestrator --> geospatial
    orchestrator --> error_handler

    advisory --> fetch_features

    fetch_features -->|ok| fetch_scores
    fetch_features -.->|err| error_handler

    fetch_scores -->|ok| validation
    fetch_scores -.->|err| error_handler

    validation -->|pass/warn| compute_score
    validation -.->|block| error_handler

    compute_score -->|ok| explainability
    compute_score -.->|err| error_handler

    explainability -->|ok| insight
    explainability -.->|err| error_handler

    geospatial --> insight

    insight --> chat_response
    chat_response --> END(["__end__"])
    error_handler --> END

    style START fill:#1a1a2e,stroke:#e94560,color:#fff
    style END fill:#1a1a2e,stroke:#e94560,color:#fff
    style END_DIRECT fill:#1a1a2e,stroke:#e94560,color:#fff
    style chat fill:#1a2e1a,stroke:#4CAF50,color:#a5d6a7
    style orchestrator fill:#16213e,stroke:#0f3460,color:#e0e0e0
    style advisory fill:#2d2d0f,stroke:#b8860b,color:#ffd700
    style fetch_features fill:#0d3320,stroke:#2e8b57,color:#90ee90
    style fetch_scores fill:#0d3320,stroke:#2e8b57,color:#90ee90
    style validation fill:#2d1a2d,stroke:#9C27B0,color:#E1BEE7
    style compute_score fill:#0d3320,stroke:#2e8b57,color:#90ee90
    style geospatial fill:#1a1a3e,stroke:#6a5acd,color:#b8b8ff
    style explainability fill:#2d1a1a,stroke:#cd5c5c,color:#ffb6b6
    style insight fill:#1a1a3e,stroke:#6a5acd,color:#b8b8ff
    style chat_response fill:#1a2e1a,stroke:#4CAF50,color:#a5d6a7
    style error_handler fill:#2d1a1a,stroke:#8b0000,color:#ff6b6b
```

### Nodes

| Node | File | LLM? | Purpose |
|---|---|---|---|
| `chat` | `agents/chat.py` | ✅ | Intent detection, follow-up answers, off-topic handling |
| `orchestrator` | `agents/orchestrator.py` | ❌ | Validate input, detect graph intent, route |
| `advisory` | `agents/advisory.py` | ✅ | Recommend scoring weights for use case |
| `fetch_features` | `agents/graph.py` | ❌ | Fetch 68-column row from PostgreSQL via PostGIS |
| `fetch_scores` | `agents/graph.py` | ❌ | Fetch Layer 7 precomputed scores |
| `validation` | `agents/graph.py` | ❌ | Legal, proximity, environmental, viability checks |
| `compute_score` | `agents/graph.py` | ❌ | Weighted-sum final score calculation |
| `geospatial` | `agents/geospatial.py` | ❌ | Hotspot detection, catchment analysis |
| `explainability` | `agents/graph.py` | ❌ | Score breakdown with strengths/weaknesses |
| `insight` | `agents/insight.py` | ✅ | Natural language insight from structured data |
| `chat_response` | `agents/chat.py` | ❌ | Format final response, set analysis_complete |
| `error_handler` | `agents/graph.py` | ❌ | Graceful error formatting |

### Intent Routing

The **chat node** classifies user intent via LLM:

| Intent | Action |
|---|---|
| `needs_graph` | Extract lat/lng/use_case → run orchestrator → full pipeline |
| `direct_answer` | Answer general system questions from LLM (no DB) |
| `follow_up` | Answer from existing state data (post-analysis) |
| `off_topic` | Redirect politely, increment retry counter |
| `ask_field` | Ask for missing information (one field at a time) |

The **orchestrator** detects graph intent **deterministically** (no LLM):

```mermaid
flowchart LR
    O["orchestrator"] --> |advise_weights| A["advisory → fetch → validate → score → explain → insight"]
    O --> |score_site| B["fetch → validate → score → explain → insight"]
    O --> |compare_sites| C["fetch → validate → score → explain → insight"]
    O --> |find_hotspots| D["geospatial → insight"]
    O --> |explain_result| E["fetch → validate → score → explain → insight"]
    O --> |error| F["error_handler"]
```

### State Schema

```python
class AgentState(TypedDict, total=False):
    # Input
    thread_id: str
    use_case: str                            # any key in USE_CASE_CATALOG
    site_input: SiteInput                    # lat, lng
    user_weights: Optional[WeightConfig]     # 6 weights (0.0–1.0, sum=1.0)

    # Routing
    intent: str                              # detected by orchestrator
    current_node: str
    error: Optional[str]
    state_name: str                          # for hotspot queries

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

    # Chat layer
    conversation_history: List[dict]
    chat_intent: str                         # needs_graph | direct_answer | follow_up | off_topic
    missing_fields: List[str]
    retry_count: int
    analysis_complete: bool
    raw_user_message: str
    chat_response: str

    # Validation
    validation_warnings: List[str]
```

---

## Chat Interface

The chat node is the **single entry point** for all user interaction. It replaces the old menu-based CLI with free-text input.

### Capabilities

- Parse natural language to extract `lat`, `lng`, `use_case`, `weights`
- Detect intent: `needs_graph` / `direct_answer` / `follow_up` / `off_topic`
- Ask ONE follow-up question at a time if info is missing
- After graph runs, accept follow-up questions using existing state data
- Enforce topic boundaries (only location/business questions)
- Enforce max retry limits (3 off-topic messages → session ends)

### Example Interactions

```
You: Score a retail site at 23.02, 72.57
Analyzer: Analyzing a retail site at (23.02, 72.57)...
          [Score: 74.2/100 — breakdown table follows]

You: Why is the risk score low?
Analyzer: The risk score of 42 is low because the site has a flood risk
          score of 65 and AQI of 120, both indicating moderate environmental
          concerns for this location.

You: What is the weather like?
Analyzer: I can only help with site selection and business location analysis.
          Try asking: 'Score a retail site at 23.02, 72.57'
```

---

## Validation Framework

Location-aware validation runs **before scoring** to catch legal, regulatory, and viability issues.

### Validators

| Validator | File | What it checks |
|---|---|---|
| **Legal** | `tools/validation_tools.py` | State-level prohibitions (e.g. alcohol in Gujarat) |
| **Proximity** | `tools/validation_tools.py` | Distance rules (liquor near schools, chemicals in residential) |
| **Environmental** | `tools/validation_tools.py` | Flood risk, earthquake risk, severe AQI |
| **Land Use** | `tools/validation_tools.py` | Agricultural land detection, industrial zoning |
| **Viability** | `tools/validation_tools.py` | Population density, competitor saturation, power reliability |

### Result Types

| Status | Action | Example |
|---|---|---|
| `block` | Stop processing, show error | "Alcohol is prohibited in Gujarat" |
| `warn` | Apply score penalty, continue | "High seismic risk — IS 1893 compliance required" |
| `pass` | No action | — |

### Score Penalties

Warnings apply point deductions to specific scoring dimensions:

| Rule | Penalty Dimension | Points |
|---|---|---|
| Healthcare near industrial zone | `risk_score` | −15 |
| Education near high AQI | `risk_score` | −10 |
| Food business in severe AQI | `suitability_score` | −10 |
| Fuel station in residential | `risk_score` | −8 |
| Low population density | `demand_score` | −20 |
| High competitor saturation | `competition_score` | −15 |

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

---

## Use Case Catalog

95 business types across 15 categories with individually tuned default weights. See `scoring/weights.py` for the full catalog.

### Categories

| Category | Examples | Count |
|---|---|---|
| Necessity & Civic | Public toilet, post office, fire station | 8 |
| Healthcare | Hospital, clinic, pharmacy, dialysis centre | 10 |
| Education | School, college, library, vocational training | 6 |
| Food & Beverage | Restaurant, café, cloud kitchen, liquor store | 11 |
| Retail & Commerce | Retail store, supermarket, showroom | 5 |
| Energy & Fuel | Petrol pump, EV charging, solar plant | 8 |
| Finance & Banking | Bank branch, ATM, microfinance | 4 |
| Fun & Leisure | Multiplex, sports complex, spa | 9 |
| Hospitality | Hotel, dharamshala | 2 |
| Industrial / GIDC | Warehouse, GIDC plot, textile factory | 8 |
| Chemical & Process | Chemical factory, pharma, ETP | 5 |
| Logistics | Cold storage, delivery hub, truck terminal | 4 |
| Professional Services | Co-working, gym, salon, data centre | 8 |
| Religious & Civic | Place of worship | 1 |
| Agriculture | Agri input store, greenhouse, aquaculture | 4 |

### Sample Default Weights

| Use Case | Demand | Access | Comp | Suit | Risk | Infra |
|---|---|---|---|---|---|---|
| Retail | 0.30 | 0.20 | 0.20 | 0.10 | 0.10 | 0.10 |
| EV Charging | 0.25 | 0.30 | 0.05 | 0.10 | 0.10 | 0.20 |
| Hospital | 0.30 | 0.25 | 0.10 | 0.10 | 0.15 | 0.10 |
| Warehouse | 0.15 | 0.35 | 0.05 | 0.15 | 0.15 | 0.15 |
| Data Centre | 0.10 | 0.20 | 0.05 | 0.15 | 0.20 | 0.30 |

---

## Data Layer

### Database: PostgreSQL 15+ with PostGIS

Single table: `site_features` with **68 columns** across 7 layers:

| Layer | Category | Columns | Source |
|---|---|---|---|
| 0 | Identifiers | `id`, `latitude`, `longitude`, `state`, `district`, `geom` | ETL pipeline |
| 1 | Demographics | `population_density`, `population_*km`, `sex_ratio`, `dependency_ratio`, `literacy_rate`, etc. | WorldPop, Census 2011, VIIRS |
| 2 | Transportation | `road_density`, `distance_to_highway`, `connectivity_score`, etc. | OSM, OSRM |
| 3 | POI / Economic | `poi_count_*`, `competitor_count`, `restaurant_count`, `shop_count`, etc. | OSM |
| 4 | Land Use | `commercial_ratio`, `residential_ratio`, `building_density`, etc. | OSM |
| 5 | Environment / Risk | `aqi`, `pm25`, `flood_risk_score`, `earthquake_risk_score`, etc. | OpenAQ, GDACS, NASA |
| 6 | Infrastructure | `distance_to_power_substation`, `public_transport_score`, etc. | OSM |
| 7 | Derived Scores | `demand_score`, `accessibility_score`, ... (6 scores, 0–100) | ETL pipeline |

### PostGIS Spatial Lookup

- Nearest-site lookup uses the PostGIS **`<->` operator** with a GIST spatial index — O(log n)
- No H3 dependency — all spatial operations use native PostGIS
- `ST_DWithin` is used for radius/catchment queries
- The `geom` column is auto-populated from `latitude`/`longitude` by the `sync_job.py` loader

---

## API Reference

All routes are **async** and call the LangGraph graph (never tools directly).

### Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `GET` | `/sites/{site_id}` | Fetch all features for a site by ID |
| `GET` | `/sites/nearest/?lat=&lng=` | Find nearest site by coordinates |
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

Response includes `site_score`, `score_breakdown`, `insight_text`, `validation_warnings`, and optional `advisory_text`.

---

## CLI Interface

Conversational chat CLI built with **Rich**.

```
╭─────────────────────────────────────────────────╮
│   GeoSpatial Site Readiness Analyzer            │
│   Ask me anything — 'Score a retail site at     │
│   23.02, 72.57' or 'Find EV hotspots in Gujarat'│
╰─────────────────────────────────────────────────╯

You: Score a retail site at 23.02, 72.57

  Thinking...

Analyzer: Analyzing a retail site at (23.02, 72.57)...

  ┌─ Site Readiness Score: 74.2 / 100   ▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░ ─┐
  │                                                               │
  └───────────────────────────────────────────────────────────────┘

  ┌─ Score Breakdown ──────────────────────────────────────────────┐
  │ Dimension           │  Raw │ Weight │ Contribution │ Visual   │
  │ Demand Score        │   74 │   0.30 │        22.2  │ ████████ │
  │ ...                 │      │        │              │          │
  └─────────────────────────────────────────────────────────────────┘
```

### Features

- **Free-text input** — no menus, just natural conversation
- **Follow-up questions** — ask about scores after analysis
- **Validation warnings** — regulatory issues shown in yellow
- **Rich tables** — comparison and hotspot results in formatted tables
- **Score breakdown** — per-dimension contribution with visual bars
- **Off-topic handling** — polite redirects with escalation

---

## Project Structure

```
geo_site_v2/
├── main.py                       # FastAPI app entry point
├── cli.py                        # Conversational chat CLI (Rich)
├── sync_job.py                   # CSV → PostgreSQL data loader
├── pyproject.toml                # Dependencies & project config
├── requirements.txt              # pip-compatible dependency list
├── alembic.ini                   # Alembic migration config
├── langgraph.json                # LangGraph Studio configuration
├── .env.example                  # Environment variable template
├── SETUP.md                      # Database setup & install guide
├── DERIVED_COLUMNS.md            # Layer 7 score formulas
├── FRONTEND_INTEGRATION.md       # Frontend integration guide
├── README.md                     # This file
│
├── agents/                       # LangGraph multi-agent system
│   ├── state.py                  # AgentState TypedDict (30+ fields)
│   ├── graph.py                  # StateGraph definition (12 nodes, conditional edges)
│   ├── chat.py                   # Chat node — intent detection, follow-up, off-topic
│   ├── orchestrator.py           # Deterministic intent routing (no LLM)
│   ├── advisory.py               # LLM weight advisor node
│   ├── geospatial.py             # Spatial operations node (no LLM)
│   └── insight.py                # LLM insight generator node
│
├── scoring/                      # Deterministic scoring engine
│   ├── engine.py                 # Weighted-sum computation + contributions
│   ├── normalizer.py             # Min-max, clipped, inverted normalization
│   ├── weights.py                # USE_CASE_CATALOG (95 use cases, 15 categories)
│   └── formulas.py               # Distance decay functions
│
├── tools/                        # Tool functions (called by agent nodes)
│   ├── site_tools.py             # DB fetch: features + precomputed scores (PostGIS)
│   ├── scoring_tools.py          # Score computation + ranking wrappers
│   ├── spatial_tools.py          # PostGIS spatial queries, hotspot detection
│   ├── explainability_tools.py   # Score breakdown + what-if analysis
│   ├── config_tools.py           # Weight validation + normalization
│   └── validation_tools.py       # Legal, proximity, environmental, viability checks
│
├── models/                       # Pydantic v2 data models
│   ├── site.py                   # SiteFeatures (68 cols), SiteScore, ScoreBreakdown
│   ├── weights.py                # WeightConfig (sum-to-1.0 validator)
│   ├── request.py                # API request/response schemas
│   └── agent.py                  # Agent I/O models
│
├── llm/                          # LLM abstraction layer
│   ├── llm_config.py             # Provider-agnostic factory
│   └── prompts.py                # All system/user prompt templates
│
├── core/                         # Configuration & infrastructure
│   ├── config.py                 # pydantic-settings (.env loader)
│   ├── database.py               # Async SQLAlchemy engine + session factory
│   ├── logger.py                 # Centralized logging
│   └── exceptions.py             # Custom exception classes
│
├── api/                          # FastAPI route layer
│   ├── dependencies.py           # DB session injection
│   └── routes/
│       ├── sites.py              # GET /sites/{site_id}, GET /sites/nearest
│       ├── scoring.py            # POST /score, POST /score/what-if
│       ├── comparison.py         # POST /compare
│       └── hotspots.py           # POST /hotspots
│
└── experiments/                  # Jupyter notebooks for testing
    ├── agent-test.ipynb          # Original graph tests
    └── agent-chat-test.ipynb     # Chat + validation workflow tests
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
| Spatial Indexing | PostGIS GIST index (`<->` operator) |
| Data Loading | Pandas + psycopg2 (`sync_job.py`) |
| CLI | Rich |
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

# 5. Set up PostgreSQL and run migrations
alembic upgrade head

# 6. Load data into PostgreSQL
python sync_job.py                   # auto-detects data/*.csv
python sync_job.py --file data/india_sites.csv  # explicit path
python sync_job.py --truncate        # fresh load

# 7. Start API server
uvicorn main:app --reload --port 8000

# 8. Or run CLI (conversational chat)
python -m cli

# 9. Or run in LangGraph Studio
pip install "langgraph-cli[inmem]"
langgraph dev
```

For detailed database setup and SQL schema, see **[SETUP.md](./SETUP.md)**.

For frontend integration, see **[FRONTEND_INTEGRATION.md](./FRONTEND_INTEGRATION.md)**.

---

## Design Decisions

### Why LangGraph over plain function chains?

- **State persistence** — Postgres checkpointer enables debugging and replay
- **Conditional routing** — Intent-based graph traversal without spaghetti if/else
- **Observability** — LangGraph Studio visualizes execution in real-time
- **Extensibility** — New nodes can be added without rewiring existing logic

### Why a chat node?

- **Natural interface** — Users describe what they want in plain language
- **Context awareness** — Follow-up questions use existing analysis data
- **Session management** — Retry limits prevent abuse, history enables context
- **Single entry point** — All paths (API, CLI, Studio) go through one node

### Why validation before scoring?

- **Fail fast** — Block illegal sites immediately (e.g., liquor in Gujarat)
- **Score accuracy** — Penalties adjust scores to reflect regulatory reality
- **User trust** — Warnings about regulations build confidence in the system
- **Separation of concerns** — Rule tables in `validation_tools.py`, not scattered in nodes

### Why PostGIS over H3?

- **Native spatial indexing** — GIST index with `<->` operator gives O(log n) nearest-neighbor
- **No external dependency** — PostGIS ships with PostgreSQL
- **Flexible queries** — `ST_DWithin` for radius/catchment, all in SQL

### Why deterministic scoring?

- **Reproducibility** — Same inputs always produce the same score
- **Auditability** — Every contribution is traceable (`raw × weight = contribution`)
- **Speed** — No LLM call needed for the core calculation
- **LLM for interpretation only** — The insight node converts numbers to narrative

---

## License

This project is proprietary. For licensing inquiries, contact the project maintainers.
