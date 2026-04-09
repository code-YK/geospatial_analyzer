# GeoSpatial Site Readiness Analyzer — Setup Guide

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11 or higher |
| PostgreSQL | 15+ with PostGIS extension |
| pip / uv | Latest |

---

## 1. Clone & Navigate

```bash
cd geo_site_v2
```

---

## 2. Create Virtual Environment

### Using `venv` (standard)
```bash
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Windows (CMD)
.\venv\Scripts\activate.bat

# Linux / macOS
source venv/bin/activate
```

### Using `uv` (faster alternative)
```bash
uv venv
uv venv activate  # or source .venv/bin/activate
```

---

## 3. Install Dependencies

### Using pip
```bash
pip install -e .
```

### Using uv
```bash
uv pip install -e .
```

This will install all dependencies defined in `pyproject.toml`:
- **FastAPI** + **Uvicorn** (API server)
- **SQLAlchemy 2.0** (async) + **asyncpg** (PostgreSQL async driver)
- **LangGraph** + **LangChain** (Groq, OpenAI, Anthropic)
- **H3** (spatial indexing)
- **Typer** + **Rich** (CLI)
- **Pydantic** + **pydantic-settings** (config & validation)

---

## 4. Set Up Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```env
# Database — update with your PostgreSQL credentials
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/geospatial_db
LANGGRAPH_CHECKPOINT_URL=postgresql://user:password@localhost:5432/geospatial_db

# LLM — default is Groq
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

> **Note:** To use a different LLM provider, change `LLM_PROVIDER` to `openai`, `anthropic`, or `ollama` and set the corresponding API key.

---

## 5. Set Up PostgreSQL Database

### 5.1 Create the Database
```sql
CREATE DATABASE geospatial_db;
```

### 5.2 Run Database Migrations

Alembic handles all schema creation automatically. No manual SQL needed.

```bash
# Apply all migrations (creates tables, indexes, and enables PostGIS)
alembic upgrade head
```

To verify the migration was applied:
```bash
alembic current
```

### 5.3 Common Migration Commands

```bash
# Apply all pending migrations
alembic upgrade head

# Check current migration version
alembic current

# Show migration history
alembic history

# Rollback one version
alembic downgrade -1

# Rollback everything
alembic downgrade base

# Create a new migration (for future schema changes)
alembic revision -m "add_new_column"
```

> **Note:** The data pipeline (ETL) for loading geospatial data into the `site_features` table is separate and not included in this codebase. Ensure data is loaded before running the analyzer.

---

## 6. Running the Application

### 6.1 Run the FastAPI Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/

### 6.2 Run the CLI

```bash
python -m cli
```

Or if you installed the package in editable mode:
```bash
geo-cli
```

---

## 7. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `GET` | `/sites/{h3_id}` | Fetch features for a specific H3 cell |
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

### Example: Compare Sites

```bash
curl -X POST http://localhost:8000/compare \
  -H "Content-Type: application/json" \
  -d '{
    "sites": [
      {"lat": 23.0225, "lng": 72.5714},
      {"lat": 23.0300, "lng": 72.5800}
    ],
    "use_case": "retail"
  }'
```

---

## 8. Project Structure

```
geo_site_v2/
├── main.py                       # FastAPI app entry point
├── cli.py                        # Menu-based CLI (Typer + Rich)
├── pyproject.toml                # Dependencies & project config
├── .env.example                  # Environment template
├── SETUP.md                      # This file
│
├── core/
│   ├── __init__.py
│   ├── config.py                 # pydantic-settings config
│   ├── database.py               # Async SQLAlchemy engine
│   └── exceptions.py             # Custom exceptions
│
├── llm/
│   ├── __init__.py
│   ├── llm_config.py             # Provider-agnostic LLM wrapper
│   └── prompts.py                # All prompt templates
│
├── agents/
│   ├── __init__.py
│   ├── graph.py                  # LangGraph StateGraph
│   ├── state.py                  # AgentState TypedDict
│   ├── orchestrator.py           # Deterministic routing
│   ├── advisory.py               # LLM weight advisor
│   ├── geospatial.py             # Spatial ops node
│   └── insight.py                # LLM insight generator
│
├── tools/
│   ├── __init__.py
│   ├── site_tools.py             # DB fetch functions
│   ├── scoring_tools.py          # Score wrappers
│   ├── spatial_tools.py          # H3 + PostGIS tools
│   ├── explainability_tools.py   # Breakdown + what-if
│   └── config_tools.py           # Weight validation
│
├── scoring/
│   ├── __init__.py
│   ├── engine.py                 # Core scoring logic
│   ├── normalizer.py             # Normalization functions
│   ├── weights.py                # Default weight configs
│   └── formulas.py               # Distance decay formulas
│
├── models/
│   ├── __init__.py
│   ├── site.py                   # Site/Score Pydantic models
│   ├── weights.py                # WeightConfig model
│   ├── request.py                # API request/response models
│   └── agent.py                  # Agent I/O models
│
└── api/
    ├── __init__.py
    ├── routes/
    │   ├── sites.py              # /sites endpoints
    │   ├── scoring.py            # /score endpoints
    │   ├── comparison.py         # /compare endpoints
    │   └── hotspots.py           # /hotspots endpoints
    └── dependencies.py           # FastAPI deps
```

---

## 9. Supported LLM Providers

| Provider | `.env` Config | Required Package |
|---|---|---|
| Groq (default) | `LLM_PROVIDER=groq` + `GROQ_API_KEY` | `langchain-groq` |
| OpenAI | `LLM_PROVIDER=openai` + `OPENAI_API_KEY` | `langchain-openai` |
| Anthropic | `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` | `langchain-anthropic` |
| Ollama (local) | `LLM_PROVIDER=ollama` | `langchain-community` |

---

## 10. Quick Start Summary

```bash
# 1. Navigate to project
cd geo_site_v2

# 2. Create venv
python -m venv venv
.\venv\Scripts\Activate.ps1   # Windows PowerShell

# 3. Install
pip install -e .

# 4. Configure
cp .env.example .env
# Edit .env with your DB credentials and GROQ_API_KEY

# 5. Set up PostgreSQL (ensure DB + extensions + table exist)

# 6. Start API server
uvicorn main:app --reload --port 8000

# 7. Or run CLI
python -m cli
```

---

## Troubleshooting

| Issue | Solution |
|---|---|
| `ModuleNotFoundError` | Ensure you ran `pip install -e .` from the `geo_site_v2/` root |
| DB connection error | Verify `DATABASE_URL` in `.env` and that PostgreSQL is running |
| `h3` import error | Run `pip install h3` — ensure C compiler is available on your system |
| LLM timeout | Check your API key and network connection |
| PostGIS missing | Run `CREATE EXTENSION postgis;` in your database |
