# Coding Agent Prompt — GeoSpatial Site Readiness Analyzer (Backend + CLI)

## Project Context

You are building the **backend + agent layer** for an AI-powered location intelligence platform called the **GeoSpatial Site Readiness Analyzer**. The system evaluates and scores geographic sites for business use cases (retail, EV charging, warehouse, telecom, renewable energy) using precomputed geospatial feature data stored in PostgreSQL.

This prompt covers:
- FastAPI backend
- LangGraph multi-agent system
- PostgreSQL + PostGIS + pgvector data layer
- Menu-based CLI for testing
- LLM utility layer (Groq, swappable)

**Do NOT build any frontend UI.** The CLI is the only interface for now.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| API framework | FastAPI |
| Agent framework | LangGraph 0.2+ |
| LLM provider | Groq API (`llama-3.3-70b-versatile`) |
| LLM config | Abstracted utility (swappable) |
| Database | PostgreSQL 15+ with PostGIS + pgvector |
| ORM / queries | SQLAlchemy 2.0 (async) + raw SQL for spatial ops |
| Schema validation | Pydantic v2 |
| LangGraph memory | Postgres-backed checkpointer (`langgraph-checkpoint-postgres`) |
| H3 indexing | `h3` Python library |
| CLI | `rich` + `typer` |
| Config | `pydantic-settings` with `.env` |
| Package manager | `uv` or `pip` with `pyproject.toml` |

---

## Project Directory Structure

```
geospatial_analyzer/
│
├── main.py                          # FastAPI app entry point
├── cli.py                           # Menu-based CLI (Typer + Rich)
├── pyproject.toml
├── .env.example
│
├── core/
│   ├── __init__.py
│   ├── config.py                    # pydantic-settings app config
│   ├── database.py                  # Async SQLAlchemy engine + session factory
│   └── exceptions.py               # Custom exception classes
│
├── llm/
│   ├── __init__.py
│   ├── llm_config.py                # LLM abstraction utility (swap here)
│   └── prompts.py                   # All system/user prompt templates
│
├── agents/
│   ├── __init__.py
│   ├── graph.py                     # LangGraph StateGraph definition (wire all nodes)
│   ├── state.py                     # AgentState TypedDict
│   ├── orchestrator.py              # Orchestrator node
│   ├── advisory.py                  # Advisory Chat Agent node
│   ├── geospatial.py                # Geo-Spatial Agent node
│   └── insight.py                   # Insight Agent node
│
├── tools/
│   ├── __init__.py
│   ├── site_tools.py                # fetch_site_features, fetch_precomputed_scores
│   ├── scoring_tools.py             # compute_final_score, apply_weights
│   ├── spatial_tools.py             # h3_lookup, hotspot_detection, catchment_query
│   ├── explainability_tools.py      # score_breakdown, feature_contribution
│   └── config_tools.py             # get_default_weights, validate_weights
│
├── scoring/
│   ├── __init__.py
│   ├── engine.py                    # Core deterministic scoring engine
│   ├── normalizer.py                # Feature normalization functions
│   ├── weights.py                   # Weight schemas + use-case defaults
│   └── formulas.py                  # Distance decay + derived score formulas
│
├── models/
│   ├── __init__.py
│   ├── site.py                      # SiteFeatures, SiteScore Pydantic models
│   ├── weights.py                   # WeightConfig Pydantic model
│   ├── request.py                   # API request/response models
│   └── agent.py                     # Agent input/output models
│
└── api/
    ├── __init__.py
    ├── routes/
    │   ├── sites.py                 # /sites endpoints
    │   ├── scoring.py               # /score endpoints
    │   ├── comparison.py            # /compare endpoints
    │   └── hotspots.py              # /hotspots endpoints
    └── dependencies.py              # FastAPI deps (DB session, auth placeholder)
```

---

## 1. LLM Configuration Utility — `llm/llm_config.py`

Create a **provider-agnostic LLM wrapper** so the entire codebase calls one interface. To swap LLM providers, only this file changes.

```python
# Interface to implement:

class LLMConfig:
    provider: str            # "groq" | "openai" | "anthropic" | "ollama"
    model: str               # e.g. "llama-3.3-70b-versatile"
    temperature: float
    max_tokens: int

def get_llm() -> BaseChatModel:
    """Returns a LangChain-compatible chat model based on LLMConfig."""
    # Default: ChatGroq(model="llama-3.3-70b-versatile", ...)
    # Swap: change provider in .env → returns ChatOpenAI / ChatAnthropic / ChatOllama

def get_llm_config() -> LLMConfig:
    """Returns current LLM config (for logging/debugging)."""
```

- Use `langchain-groq` for the Groq integration.
- Read `LLM_PROVIDER`, `LLM_MODEL`, `GROQ_API_KEY` from `.env` via `pydantic-settings`.
- The rest of the codebase only ever imports `get_llm()` — never imports Groq directly.

---

## 2. Agent State — `agents/state.py`

```python
class AgentState(TypedDict):
    # Input
    thread_id: str
    use_case: str                        # "retail" | "ev_charging" | "warehouse" | "telecom" | "renewable"
    site_input: SiteInput                # lat, lng, h3_id (optional)
    user_weights: Optional[WeightConfig] # 6-7 weights provided by user (0.0–1.0, sum=1.0)
    comparison_sites: Optional[List[SiteInput]]  # for multi-site comparison

    # Routing / flow control
    intent: str                          # "score_site" | "compare_sites" | "find_hotspots" | "explain_result" | "advise_weights"
    current_node: str
    error: Optional[str]

    # Data payloads (populated by tools as graph progresses)
    site_features: Optional[SiteFeatures]
    precomputed_scores: Optional[PrecomputedScores]
    final_score: Optional[float]
    score_breakdown: Optional[ScoreBreakdown]
    comparison_results: Optional[List[SiteScore]]
    hotspot_results: Optional[List[HotspotResult]]

    # Output
    insight_text: str                    # Final natural language output to user
    advisory_text: Optional[str]        # Weight recommendations from advisory agent
    recommended_weights: Optional[WeightConfig]
```

---

## 3. LangGraph Graph — `agents/graph.py`

Build a `StateGraph` with the following nodes and edges.

### Nodes

| Node name | Function | Description |
|---|---|---|
| `orchestrator` | `orchestrator_node()` | Detects intent, validates input, routes to next node |
| `advisory` | `advisory_node()` | Suggests / validates weights for the use case |
| `fetch_features` | `fetch_features_node()` | Calls `site_tools.fetch_site_features()` |
| `fetch_scores` | `fetch_scores_node()` | Calls `site_tools.fetch_precomputed_scores()` |
| `compute_score` | `compute_score_node()` | Calls `scoring_tools.compute_final_score()` |
| `geospatial` | `geospatial_node()` | Handles hotspot / catchment / clustering queries |
| `explainability` | `explainability_node()` | Calls `explainability_tools.score_breakdown()` |
| `insight` | `insight_node()` | LLM converts structured results → natural language |
| `error_handler` | `error_handler_node()` | Catches and formats errors gracefully |

### Edge routing logic

```
START
  └─► orchestrator
        ├─► [intent == "advise_weights"]     → advisory → fetch_features → compute_score → explainability → insight → END
        ├─► [intent == "score_site"]         → fetch_features → fetch_scores → compute_score → explainability → insight → END
        ├─► [intent == "compare_sites"]      → fetch_features → fetch_scores → compute_score → explainability → insight → END
        ├─► [intent == "find_hotspots"]      → geospatial → insight → END
        ├─► [intent == "explain_result"]     → fetch_scores → explainability → insight → END
        └─► [error at any node]              → error_handler → END
```

- Use `add_conditional_edges` from orchestrator based on `state["intent"]`.
- Use **Postgres checkpointer** (`langgraph-checkpoint-postgres`) with `thread_id` as the session key. Each CLI run generates a new `thread_id` (UUID4).
- All nodes are **async**.

---

## 4. Orchestrator Node — `agents/orchestrator.py`

```python
async def orchestrator_node(state: AgentState) -> AgentState:
```

Responsibilities:
1. **Validate `site_input`**: confirm lat/lng are within India bounds (-8 to 37 lat, 68 to 97 lng). If H3 grid ID provided, validate its format.
2. **Validate `user_weights`**: call `config_tools.validate_weights()`. If weights missing, set intent to `"advise_weights"`. If weights invalid, set error.
3. **Detect intent** from the request context:
   - Single site + weights provided → `"score_site"`
   - Multiple sites → `"compare_sites"`
   - No site, area query → `"find_hotspots"`
   - Asking for explanation of a previous score → `"explain_result"`
   - No weights provided → `"advise_weights"`
4. Set `state["current_node"] = "orchestrator"` and return updated state.
5. **No LLM call in this node.** This is purely deterministic routing logic.

---

## 5. Advisory Agent Node — `agents/advisory.py`

```python
async def advisory_node(state: AgentState) -> AgentState:
```

Responsibilities:
1. Called when user has NOT provided weights or wants weight recommendations.
2. Uses LLM (`get_llm()`) to suggest weights based on `use_case`.
3. System prompt must instruct the LLM to **return structured JSON only** with this schema:
```json
{
  "recommended_weights": {
    "demand_score": 0.25,
    "accessibility_score": 0.20,
    "competition_score": 0.15,
    "suitability_score": 0.15,
    "risk_score": 0.10,
    "infrastructure_score": 0.15
  },
  "reasoning": "For EV charging, accessibility and demand are most critical..."
}
```
4. Validate returned weights sum to 1.0 (±0.01 tolerance). If not, normalize them.
5. Set `state["recommended_weights"]` and `state["advisory_text"]`.
6. Then set `state["user_weights"] = state["recommended_weights"]` so the rest of the graph proceeds.

**Default weight configs** (hardcoded fallback in `scoring/weights.py`):

| Use case | demand | accessibility | competition | suitability | risk | infrastructure |
|---|---|---|---|---|---|---|
| retail | 0.30 | 0.20 | 0.20 | 0.10 | 0.10 | 0.10 |
| ev_charging | 0.25 | 0.30 | 0.05 | 0.10 | 0.10 | 0.20 |
| warehouse | 0.15 | 0.35 | 0.05 | 0.15 | 0.15 | 0.15 |
| telecom | 0.10 | 0.25 | 0.10 | 0.15 | 0.15 | 0.25 |
| renewable | 0.10 | 0.20 | 0.05 | 0.25 | 0.20 | 0.20 |

---

## 6. Scoring Engine — `scoring/engine.py`

This is the **deterministic core** — no LLM involvement here.

### `compute_final_score(precomputed_scores, user_weights) → SiteScore`

```python
def compute_final_score(
    precomputed_scores: PrecomputedScores,  # Layer 7 scores (0–100 each)
    user_weights: WeightConfig              # 6 weights summing to 1.0
) -> SiteScore:
```

Formula:
```
site_readiness_score = (
    demand_score        * weights.demand_score +
    accessibility_score * weights.accessibility_score +
    competition_score   * weights.competition_score +
    suitability_score   * weights.suitability_score +
    risk_score          * weights.risk_score +
    infrastructure_score * weights.infrastructure_score
)
```
- Output is 0–100.
- Also returns `contributions: dict[str, float]` — each score's weighted contribution (for explainability).
- Example: `{"demand_score": 18.5, "accessibility_score": 14.2, ...}`

### `scoring/normalizer.py`

Implement **min-max normalization** for all raw features before they are used to derive Layer 7 scores during the ETL pipeline. Keep these functions here even though the ETL runs separately — the scoring engine references them for documentation.

```python
def minmax_normalize(value: float, min_val: float, max_val: float) -> float:
    """Scale value to 0–100."""

def clip_and_normalize(value: float, min_val: float, max_val: float) -> float:
    """Clip outliers then normalize."""

def invert_score(score: float) -> float:
    """For risk/competition: higher raw = lower score. Returns 100 - score."""
```

### `scoring/formulas.py`

```python
def distance_decay(distance_meters: float, decay_type: str = "inverse_square") -> float:
    """
    decay_type options:
    - "inverse_square": weight = 1 / (1 + d^2)   ← for strong local effects (POI)
    - "exponential":    weight = exp(-lambda * d) ← for gradual decay (demographics)
    - "linear":         weight = max(0, 1 - d/max_d) ← for hard cutoff radius
    """
```

---

## 7. Tools Layer

### `tools/site_tools.py`

```python
async def fetch_site_features(
    lat: float, lng: float, h3_id: Optional[str], db: AsyncSession
) -> SiteFeatures:
    """
    Query PostgreSQL for all 71 columns for the nearest H3 cell.
    If h3_id provided: direct lookup by grid_id.
    If only lat/lng: use H3 library to compute h3_id at resolution 8, then lookup.
    Raise SiteNotFoundError if no row found.
    """

async def fetch_precomputed_scores(h3_id: str, db: AsyncSession) -> PrecomputedScores:
    """
    Fetch Layer 7 scores (demand_score, accessibility_score, competition_score,
    suitability_score, risk_score, infrastructure_score) for the given H3 cell.
    These are already normalized 0–100.
    """
```

### `tools/scoring_tools.py`

```python
def compute_final_score(
    precomputed_scores: PrecomputedScores,
    user_weights: WeightConfig
) -> SiteScore:
    """Thin wrapper that calls scoring/engine.py compute_final_score()."""

def rank_sites(site_scores: List[SiteScore]) -> List[SiteScore]:
    """Sort sites by site_readiness_score descending. Return ranked list."""
```

### `tools/spatial_tools.py`

```python
def lat_lng_to_h3(lat: float, lng: float, resolution: int = 8) -> str:
    """Convert lat/lng to H3 index at given resolution."""

def h3_to_lat_lng(h3_id: str) -> Tuple[float, float]:
    """Get centroid lat/lng from H3 index."""

async def get_neighboring_cells(h3_id: str, k_rings: int = 2, db: AsyncSession) -> List[SiteFeatures]:
    """Return k-ring neighbors of a cell from DB."""

async def detect_hotspots(
    state: str,
    use_case: str,
    user_weights: WeightConfig,
    top_n: int = 10,
    db: AsyncSession
) -> List[HotspotResult]:
    """
    For a given state, fetch all H3 cells, compute final scores,
    return top_n cells ranked by site_readiness_score.
    Use PostGIS spatial index for efficient querying.
    """

async def catchment_analysis(
    h3_id: str, radius_km: float, db: AsyncSession
) -> CatchmentResult:
    """
    Return all H3 cells within radius_km of the given cell.
    Use PostGIS ST_DWithin for the spatial query.
    """
```

### `tools/explainability_tools.py`

```python
def score_breakdown(site_score: SiteScore) -> ScoreBreakdown:
    """
    Returns per-dimension contribution breakdown.
    Example output:
    {
      "site_readiness_score": 72.4,
      "contributions": {
        "demand_score":         {"raw": 74, "weight": 0.25, "contribution": 18.5, "rank": 1},
        "accessibility_score":  {"raw": 71, "weight": 0.20, "contribution": 14.2, "rank": 2},
        "competition_score":    {"raw": 55, "weight": 0.15, "contribution": 8.25, "rank": 5},
        "suitability_score":    {"raw": 68, "weight": 0.15, "contribution": 10.2, "rank": 3},
        "risk_score":           {"raw": 60, "weight": 0.10, "contribution": 6.0,  "rank": 6},
        "infrastructure_score": {"raw": 66, "weight": 0.15, "contribution": 9.9,  "rank": 4}
      },
      "strengths": ["demand_score", "accessibility_score"],
      "weaknesses": ["risk_score", "competition_score"]
    }
    Strengths = contributions in top 2. Weaknesses = contributions in bottom 2.
    """

def what_if_analysis(
    precomputed_scores: PrecomputedScores,
    current_weights: WeightConfig,
    modified_weights: WeightConfig
) -> WhatIfResult:
    """
    Compute score under both weight configs.
    Return delta and which dimensions gained/lost impact.
    """
```

### `tools/config_tools.py`

```python
def get_default_weights(use_case: str) -> WeightConfig:
    """Return hardcoded default WeightConfig for a given use case."""

def validate_weights(weights: dict) -> Tuple[bool, Optional[str]]:
    """
    Validate:
    1. All 6 keys present: demand, accessibility, competition, suitability, risk, infrastructure
    2. All values between 0.0 and 1.0
    3. Sum equals 1.0 (±0.01 tolerance)
    Returns (is_valid, error_message).
    """

def normalize_weights(weights: dict) -> WeightConfig:
    """Force weights to sum to 1.0 by proportional normalization."""
```

---

## 8. Pydantic Models — `models/`

### `models/site.py`

```python
class SiteInput(BaseModel):
    lat: float
    lng: float
    h3_id: Optional[str] = None           # If not provided, compute from lat/lng

class SiteFeatures(BaseModel):
    # Layer 0
    id: str
    latitude: float
    longitude: float
    state: str
    district: str
    area_name: str
    grid_id: str
    # Layer 1 — Demographics
    population_1km: float
    population_5km: float
    population_density: float
    # ... (all 71 columns — use Optional[float] for nullable fields)

class PrecomputedScores(BaseModel):
    grid_id: str
    demand_score: float           # 0–100
    accessibility_score: float    # 0–100
    competition_score: float      # 0–100
    suitability_score: float      # 0–100
    risk_score: float             # 0–100
    infrastructure_score: float   # 0–100

class SiteScore(BaseModel):
    grid_id: str
    lat: float
    lng: float
    site_readiness_score: float       # 0–100, final weighted output
    contributions: Dict[str, float]   # per-dimension weighted contribution
    precomputed_scores: PrecomputedScores
    weights_used: WeightConfig
```

### `models/weights.py`

```python
class WeightConfig(BaseModel):
    demand_score: float        = Field(..., ge=0.0, le=1.0)
    accessibility_score: float = Field(..., ge=0.0, le=1.0)
    competition_score: float   = Field(..., ge=0.0, le=1.0)
    suitability_score: float   = Field(..., ge=0.0, le=1.0)
    risk_score: float          = Field(..., ge=0.0, le=1.0)
    infrastructure_score: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "WeightConfig":
        total = sum([
            self.demand_score, self.accessibility_score,
            self.competition_score, self.suitability_score,
            self.risk_score, self.infrastructure_score
        ])
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Weights must sum to 1.0, got {total:.3f}")
        return self
```

---

## 9. FastAPI Routes — `api/routes/`

### `sites.py`

```
GET  /sites/{h3_id}              → fetch all features for a cell
GET  /sites/nearest?lat=&lng=    → find nearest H3 cell and return features
```

### `scoring.py`

```
POST /score
     Body: { site_input: SiteInput, use_case: str, weights: Optional[WeightConfig] }
     → Triggers the full LangGraph graph run
     → Returns: SiteScore + ScoreBreakdown + insight_text

POST /score/what-if
     Body: { h3_id: str, current_weights: WeightConfig, modified_weights: WeightConfig }
     → Returns: WhatIfResult
```

### `comparison.py`

```
POST /compare
     Body: { sites: List[SiteInput], use_case: str, weights: Optional[WeightConfig] }
     → Returns: List[SiteScore] ranked by site_readiness_score + insight_text
```

### `hotspots.py`

```
POST /hotspots
     Body: { state: str, use_case: str, weights: Optional[WeightConfig], top_n: int = 10 }
     → Returns: List[HotspotResult] + insight_text
```

All routes are **async**. All routes inject `db: AsyncSession` via `dependencies.py`.

---

## 10. Insight Agent Node — `agents/insight.py`

```python
async def insight_node(state: AgentState) -> AgentState:
```

This is the ONLY place where LLM is used to generate user-facing text. Give it a structured system prompt that says:

> "You are a location intelligence analyst. You receive structured JSON containing site scores, score breakdowns, and feature data. Convert this into a clear, concise business insight. Be specific — mention actual numbers. Identify the top strength and top weakness. Give one actionable recommendation. Max 150 words."

Pass it: `score_breakdown`, `use_case`, `site_features` (key fields only — state, district, population_density, land use).

Set `state["insight_text"]` with the LLM response.

---

## 11. Geo-Spatial Agent Node — `agents/geospatial.py`

```python
async def geospatial_node(state: AgentState) -> AgentState:
```

Handles intents: `find_hotspots`, `catchment_analysis`.

Calls:
- `spatial_tools.detect_hotspots()` for hotspot intent
- `spatial_tools.catchment_analysis()` for catchment intent

Sets `state["hotspot_results"]` or updates state with catchment data.
Does NOT call LLM — purely tool execution.

---

## 12. CLI — `cli.py`

Build a **menu-based CLI** using `rich` + `typer`. Stateless per run (new `thread_id` = `uuid4()` each run).

### Main menu

```
╔══════════════════════════════════════╗
║   GeoSpatial Site Readiness Analyzer ║
╚══════════════════════════════════════╝

  1. Score a site
  2. Compare multiple sites
  3. Find hotspots in a state
  4. Exit

Enter choice:
```

### Flow 1: Score a site

```
Step 1/3 — Site Location
  Enter latitude  : 23.0225
  Enter longitude : 72.5714
  Enter H3 grid ID (or press Enter to auto-compute): [optional]

Step 2/3 — Use Case
  Select use case:
  1. Retail store
  2. EV charging station
  3. Warehouse / logistics
  Enter choice: 2

Step 3/3 — Scoring Weights
  Use default weights for EV charging? [Y/n]: n
  
  Enter weights (must sum to 1.0):
    Demand score weight       [default: 0.25]: 0.30
    Accessibility score weight [default: 0.30]: 0.25
    Competition score weight  [default: 0.05]: 0.05
    Suitability score weight  [default: 0.10]: 0.15
    Risk score weight         [default: 0.10]: 0.10
    Infrastructure score weight [default: 0.20]: 0.15

  ✓ Weights sum: 1.00

[Running analysis...]

╔══════════════════════════════════════════════╗
║  Site Readiness Score: 74.2 / 100   ▓▓▓▓▓▓░ ║
╚══════════════════════════════════════════════╝

Score Breakdown:
  Demand         74  × 0.30 = 22.2  ████████
  Accessibility  71  × 0.25 = 17.75 ███████
  Competition    55  × 0.05 = 2.75  ██
  Suitability    68  × 0.15 = 10.2  ████
  Risk           60  × 0.10 = 6.0   ███
  Infrastructure 66  × 0.15 = 9.9   ████

Insight:
  This site in Ahmedabad, Gujarat scores 74.2 — above average for EV charging
  suitability. Primary strength is high population density (1,240/km²) and strong
  road accessibility. Main weakness is moderate risk score due to flood zone
  proximity. Recommendation: validate flood risk with NDMA data before committing.
```

### Flow 2: Compare sites

- Accept 2–5 sites (lat/lng each)
- Show a ranked comparison table using `rich.Table`

### Flow 3: Find hotspots

- Accept state name + use case
- Show top 10 H3 cells as a ranked table with scores

### Error handling in CLI

- Wrap all graph invocations in try/except
- Show friendly error messages with `rich` red panel
- Never show raw stack traces to the user

---

## 13. Environment Config — `.env.example`

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/geospatial_db

# LangGraph Checkpointer (same DB, different schema)
LANGGRAPH_CHECKPOINT_URL=postgresql://user:password@localhost:5432/geospatial_db

# LLM
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
LLM_TEMPERATURE=0.2
LLM_MAX_TOKENS=1000
GROQ_API_KEY=your_groq_api_key_here

# App
APP_ENV=development
LOG_LEVEL=INFO
H3_RESOLUTION=8
```

---

## 14. Database Setup Notes

The PostgreSQL DB already has the geospatial data loaded (pipeline is separate). The backend assumes:

```sql
-- Main data table (already populated by data pipeline)
CREATE TABLE site_features (
    grid_id TEXT PRIMARY KEY,
    latitude FLOAT,
    longitude FLOAT,
    state TEXT,
    district TEXT,
    area_name TEXT,
    geom GEOMETRY(Point, 4326),   -- PostGIS geometry column
    -- ... all 71 columns from the schema
    -- Layer 7 scores (precomputed, stored here)
    demand_score FLOAT,
    accessibility_score FLOAT,
    competition_score FLOAT,
    suitability_score FLOAT,
    risk_score FLOAT,
    infrastructure_score FLOAT,
    -- Metadata
    last_updated TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_site_features_geom ON site_features USING GIST(geom);
CREATE INDEX idx_site_features_state ON site_features(state);
CREATE INDEX idx_site_features_grid_id ON site_features(grid_id);
```

When querying by lat/lng (no H3 ID), use the H3 Python library to compute `grid_id` first — do NOT use `ST_NearestNeighbor`. Direct H3 lookup is O(1) and preferred.

---

## 15. Key Implementation Rules

1. **Scoring engine is deterministic** — no randomness, no LLM, no external calls.
2. **LLM is called only in `advisory_node` and `insight_node`**.
3. **All nodes are async** — use `await` for all DB calls.
4. **Never pass raw SiteFeatures (all 71 cols) to the LLM** — extract only the 8–10 most relevant fields for the use case before passing to insight node.
5. **Weight validation happens twice**: in `orchestrator_node` (basic check) and in `WeightConfig` Pydantic model (strict check with sum validation).
6. **`competitor_count` is dynamic** — it is NOT precomputed in Layer 7. The scoring engine computes it at query time by mapping `use_case` → relevant OSM POI categories → sum the relevant count columns from Layer 3.
7. **All FastAPI routes call the LangGraph graph** — routes do not call tools or scoring engine directly. The graph is the single entry point for all intelligence operations.
8. **`thread_id`** is generated fresh per CLI run (`uuid4()`). The Postgres checkpointer stores state per thread for debugging — not for user sessions (stateless per run).
9. **Rich CLI output** should use `rich.progress` for the "Running analysis..." step, `rich.table` for comparisons, `rich.panel` for scores, and `rich.console` throughout.
10. **Use `pydantic-settings`** for all config — no hardcoded strings outside of `core/config.py` and `scoring/weights.py`.

---

## 16. Deliverables Checklist

- [ ] `core/config.py` — pydantic-settings config
- [ ] `core/database.py` — async SQLAlchemy engine
- [ ] `llm/llm_config.py` — swappable LLM utility
- [ ] `llm/prompts.py` — all prompt templates
- [ ] `agents/state.py` — AgentState TypedDict
- [ ] `agents/graph.py` — full StateGraph wired up
- [ ] `agents/orchestrator.py` — deterministic routing node
- [ ] `agents/advisory.py` — LLM weight advisor node
- [ ] `agents/geospatial.py` — spatial ops node
- [ ] `agents/insight.py` — LLM insight generator node
- [ ] `scoring/engine.py` — core scoring logic
- [ ] `scoring/normalizer.py` — normalization functions
- [ ] `scoring/weights.py` — default weight configs
- [ ] `scoring/formulas.py` — distance decay formulas
- [ ] `tools/site_tools.py` — DB fetch functions
- [ ] `tools/scoring_tools.py` — score compute wrappers
- [ ] `tools/spatial_tools.py` — H3 + PostGIS tools
- [ ] `tools/explainability_tools.py` — breakdown + what-if
- [ ] `tools/config_tools.py` — weight validation
- [ ] `models/` — all Pydantic v2 models
- [ ] `api/routes/` — all 4 FastAPI route files
- [ ] `cli.py` — full menu-based Rich + Typer CLI
- [ ] `.env.example`
- [ ] `pyproject.toml` with all dependencies
