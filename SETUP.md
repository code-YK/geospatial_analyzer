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
- **Pandas** (data loading)
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

# Data
CSV_DATA_PATH=data/
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

---

## 6. Load Data into PostgreSQL

Use the `sync_job.py` script to load CSV data into the `site_features` table:

```bash
# Auto-detect first .csv in data/ folder
python sync_job.py

# Specify a CSV file explicitly
python sync_job.py --file data/india_sites.csv

# Truncate table before loading (fresh load)
python sync_job.py --truncate

# Custom batch size (default: 1000)
python sync_job.py --batch-size 500
```

> **Note:** CSV must contain required columns: `id`, `latitude`, `longitude`, `state`, `district`. The `geom` column is auto-generated from lat/lng during loading.

---

## 7. Running the Application

### 7.1 Run the FastAPI Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/

### 7.2 Run the CLI

```bash
python -m cli
```

Or if you installed the package in editable mode:
```bash
geo-cli
```

---

## 8. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `GET` | `/sites/{site_id}` | Fetch features for a specific site |
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

## 9. Project Structure

```
geo_site_v2/
├── main.py                       # FastAPI app entry point
├── cli.py                        # Menu-based CLI (Typer + Rich)
├── sync_job.py                   # CSV → PostgreSQL data loader
├── pyproject.toml                # Dependencies & project config
├── .env.example                  # Environment template
├── SETUP.md                      # This file
├── DERIVED_COLUMNS.md            # Layer 7 score formulas
│
├── core/
│   ├── __init__.py
│   ├── config.py                 # pydantic-settings config
│   ├── database.py               # Async SQLAlchemy engine
│   ├── logger.py                 # Centralized logging
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
│   ├── site_tools.py             # DB fetch functions (PostGIS)
│   ├── scoring_tools.py          # Score wrappers
│   ├── spatial_tools.py          # PostGIS spatial queries
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

## 10. Supported LLM Providers

| Provider | `.env` Config | Required Package |
|---|---|---|
| Groq (default) | `LLM_PROVIDER=groq` + `GROQ_API_KEY` | `langchain-groq` |
| OpenAI | `LLM_PROVIDER=openai` + `OPENAI_API_KEY` | `langchain-openai` |
| Anthropic | `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` | `langchain-anthropic` |
| Ollama (local) | `LLM_PROVIDER=ollama` | `langchain-community` |

---

## 11. Quick Start Summary

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

# 5. Set up PostgreSQL (ensure DB exists)
alembic upgrade head

# 6. Load data
python sync_job.py --file data/india_sites.csv

# 7. Start API server
uvicorn main:app --reload --port 8000

# 8. Or run CLI
python -m cli
```

---

## Troubleshooting

| Issue | Solution |
|---|---|
| `ModuleNotFoundError` | Ensure you ran `pip install -e .` from the `geo_site_v2/` root |
| DB connection error | Verify `DATABASE_URL` in `.env` and that PostgreSQL is running |
| PostGIS missing | Run `CREATE EXTENSION postgis;` in your database |
| LLM timeout | Check your API key and network connection |
| Sync job fails | Ensure CSV has required columns: `id`, `latitude`, `longitude`, `state`, `district` |
