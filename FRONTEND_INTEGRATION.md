# Frontend Integration Guide

This document explains how to connect a frontend application to the GeoSpatial Site Readiness Analyzer backend.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [API Endpoints](#api-endpoints)
- [Chat Mode Integration](#chat-mode-integration)
- [Scoring API](#scoring-api)
- [Comparison API](#comparison-api)
- [Hotspot API](#hotspot-api)
- [Site Lookup API](#site-lookup-api)
- [WebSocket / Streaming](#websocket--streaming)
- [State Management](#state-management)
- [Error Handling](#error-handling)
- [Example: React Integration](#example-react-integration)

---

## Architecture Overview

```
┌──────────────────┐     HTTP/JSON     ┌──────────────────────┐
│                  │ ◄──────────────── │                      │
│   Frontend App   │                   │  FastAPI Backend      │
│   (React/Next)   │ ────────────────► │  localhost:8000       │
│                  │                   │                      │
└──────────────────┘                   └──────────┬───────────┘
                                                  │
                                       ┌──────────▼───────────┐
                                       │  LangGraph Agent     │
                                       │  (chat → orchestrator│
                                       │   → score → insight) │
                                       └──────────┬───────────┘
                                                  │
                                       ┌──────────▼───────────┐
                                       │  PostgreSQL + PostGIS│
                                       └──────────────────────┘
```

The frontend communicates with the backend exclusively via REST API calls. All intelligence is in the LangGraph graph — the frontend only needs to send requests and render responses.

---

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Health check |
| `GET` | `/sites/{site_id}` | Get site features by ID |
| `GET` | `/sites/nearest/?lat=&lng=` | Find nearest site |
| `POST` | `/score` | Score a single site |
| `POST` | `/score/what-if` | Compare weight configurations |
| `POST` | `/compare` | Compare and rank multiple sites |
| `POST` | `/hotspots` | Find hotspot locations |

**Base URL:** `http://localhost:8000` (development)

---

## Chat Mode Integration

For a conversational UI (chat-like interface), use the `/score` endpoint with the full graph:

### Request

```json
POST /score
{
  "site_input": {"lat": 23.0225, "lng": 72.5714},
  "use_case": "retail",
  "user_weights": null
}
```

### Response

```json
{
  "site_score": {
    "id": "IND_0041234",
    "lat": 23.0225,
    "lng": 72.5714,
    "site_readiness_score": 74.2,
    "contributions": {
      "demand_score": 22.2,
      "accessibility_score": 14.2,
      "competition_score": 11.0,
      "suitability_score": 10.2,
      "risk_score": 7.8,
      "infrastructure_score": 8.8
    },
    "precomputed_scores": { ... },
    "weights_used": { ... }
  },
  "score_breakdown": {
    "site_readiness_score": 74.2,
    "contributions": {
      "demand_score": {"raw": 74, "weight": 0.30, "contribution": 22.2, "rank": 1},
      ...
    },
    "strengths": ["demand_score", "accessibility_score"],
    "weaknesses": ["risk_score", "competition_score"]
  },
  "insight_text": "This retail site in Ahmedabad scores 74.2/100...",
  "advisory_text": null,
  "validation_warnings": [
    "High market saturation — 15+ competitors within 500m."
  ],
  "error": null
}
```

### Rendering Tips

| Field | UI Element |
|---|---|
| `site_readiness_score` | Large number + progress bar (color-coded: green ≥ 60, yellow ≥ 40, red < 40) |
| `contributions` | Bar chart or radar chart showing 6 dimensions |
| `strengths` / `weaknesses` | Tag chips (green/red) |
| `insight_text` | Text card / expandable panel |
| `validation_warnings` | Yellow alert banners |

---

## Scoring API

### Score a Single Site

```javascript
const response = await fetch('http://localhost:8000/score', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    site_input: { lat: 23.0225, lng: 72.5714 },
    use_case: 'ev_charging',
    user_weights: null  // use defaults
  })
});

const data = await response.json();
console.log(data.site_score.site_readiness_score);  // 68.5
console.log(data.insight_text);                      // "This EV charging..."
console.log(data.validation_warnings);               // ["Warning..."]
```

### Score with Custom Weights

```javascript
const response = await fetch('http://localhost:8000/score', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    site_input: { lat: 23.0225, lng: 72.5714 },
    use_case: 'retail',
    user_weights: {
      demand_score: 0.35,
      accessibility_score: 0.20,
      competition_score: 0.15,
      suitability_score: 0.10,
      risk_score: 0.10,
      infrastructure_score: 0.10
    }
  })
});
```

### What-If Analysis

```javascript
const response = await fetch('http://localhost:8000/score/what-if', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    site_input: { lat: 23.0225, lng: 72.5714 },
    use_case: 'retail',
    original_weights: {
      demand_score: 0.30, accessibility_score: 0.20,
      competition_score: 0.20, suitability_score: 0.10,
      risk_score: 0.10, infrastructure_score: 0.10
    },
    modified_weights: {
      demand_score: 0.40, accessibility_score: 0.15,
      competition_score: 0.15, suitability_score: 0.10,
      risk_score: 0.10, infrastructure_score: 0.10
    }
  })
});
```

---

## Comparison API

### Compare Multiple Sites

```javascript
const response = await fetch('http://localhost:8000/compare', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    sites: [
      { lat: 23.0225, lng: 72.5714 },
      { lat: 23.0300, lng: 72.5800 },
      { lat: 22.9900, lng: 72.5500 }
    ],
    use_case: 'retail'
  })
});

const data = await response.json();
// data.comparison_results = [{ id, lat, lng, site_readiness_score }, ...]
// data.insight_text = "Comparative analysis..."
```

### Rendering Tips

- Show comparison as a sorted leaderboard table
- Highlight the #1 site in green
- Use a map to plot all sites with score-colored markers

---

## Hotspot API

### Find Hotspots

```javascript
const response = await fetch('http://localhost:8000/hotspots', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    state: 'Gujarat',
    use_case: 'ev_charging',
    top_n: 10
  })
});

const data = await response.json();
// data.hotspot_results = [{ id, lat, lng, state, district, site_readiness_score }, ...]
// data.insight_text = "Top hotspot findings..."
```

### Rendering Tips

- Plot hotspots on a map with heat-map overlay
- Show a ranked table beside the map
- Allow clicking a hotspot to trigger a full score analysis

---

## Site Lookup API

### Get Site by ID

```javascript
const response = await fetch('http://localhost:8000/sites/IND_0041234');
const features = await response.json();
// features = { id, latitude, longitude, state, district, population_density, aqi, ... }
```

### Find Nearest Site

```javascript
const response = await fetch('http://localhost:8000/sites/nearest/?lat=23.02&lng=72.57');
const nearest = await response.json();
```

---

## WebSocket / Streaming

For real-time progress updates during long graph runs, you can use LangGraph's streaming capabilities:

### Option 1: Server-Sent Events (SSE)

The backend can be extended with an SSE endpoint that streams node completions:

```python
# api/routes/streaming.py (future)
@router.post("/score/stream")
async def score_stream(request: ScoreRequest):
    async def event_generator():
        async for event in graph.astream(state, config):
            yield f"data: {json.dumps(event)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

Frontend consumption:

```javascript
const eventSource = new EventSource('/score/stream');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  updateProgress(data.current_node);
};
```

### Option 2: Polling

For simpler implementations, poll the graph status:

1. `POST /score` → returns immediately with a `task_id`
2. `GET /score/status/{task_id}` → returns current progress
3. Frontend polls every 500ms until `status: "complete"`

---

## State Management

### Frontend State Considerations

```typescript
interface AnalysisState {
  // Input
  lat: number | null;
  lng: number | null;
  useCase: string;
  weights: WeightConfig | null;

  // Results
  score: number | null;
  breakdown: ScoreBreakdown | null;
  insight: string;
  warnings: string[];

  // UI
  isLoading: boolean;
  error: string | null;
  conversationHistory: Message[];
}
```

### Use Case Catalog

The frontend should fetch the use case catalog on load:

```javascript
// Hardcode or fetch from a future /use-cases endpoint
const USE_CASES = {
  retail:       { name: "Retail Store",      category: "Retail & Commerce" },
  ev_charging:  { name: "EV Charging Station", category: "Energy & Fuel" },
  hospital:     { name: "Hospital",          category: "Healthcare" },
  // ... 95 total
};
```

---

## Error Handling

### HTTP Error Codes

| Code | Meaning | Action |
|---|---|---|
| `200` | Success | Render results |
| `400` | Bad request (invalid input) | Show validation error |
| `404` | Site not found | Show "no data" message |
| `422` | Validation error (Pydantic) | Show field-level errors |
| `500` | Server error | Show retry button |

### Application-Level Errors

The response body may contain an `error` field even with HTTP 200:

```json
{
  "error": "⛔ This location is not suitable for liquor store.\nReason: Alcohol is prohibited in Gujarat.",
  "site_score": null,
  "insight_text": ""
}
```

Always check `response.error` before rendering results.

---

## Example: React Integration

### Minimal Score Component

```tsx
import { useState } from 'react';

interface ScoreResult {
  site_score: { site_readiness_score: number } | null;
  insight_text: string;
  validation_warnings: string[];
  error: string | null;
}

export function SiteScorer() {
  const [lat, setLat] = useState(23.0225);
  const [lng, setLng] = useState(72.5714);
  const [useCase, setUseCase] = useState('retail');
  const [result, setResult] = useState<ScoreResult | null>(null);
  const [loading, setLoading] = useState(false);

  const analyze = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/score', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          site_input: { lat, lng },
          use_case: useCase,
        }),
      });
      const data = await res.json();
      setResult(data);
    } catch (err) {
      setResult({ error: 'Network error', site_score: null, insight_text: '', validation_warnings: [] });
    }
    setLoading(false);
  };

  return (
    <div>
      <input type="number" value={lat} onChange={e => setLat(+e.target.value)} />
      <input type="number" value={lng} onChange={e => setLng(+e.target.value)} />
      <select value={useCase} onChange={e => setUseCase(e.target.value)}>
        <option value="retail">Retail</option>
        <option value="ev_charging">EV Charging</option>
        <option value="hospital">Hospital</option>
      </select>
      <button onClick={analyze} disabled={loading}>
        {loading ? 'Analyzing...' : 'Score Site'}
      </button>

      {result?.error && <div className="error">{result.error}</div>}

      {result?.site_score && (
        <div className="score">
          Score: {result.site_score.site_readiness_score.toFixed(1)} / 100
        </div>
      )}

      {result?.validation_warnings?.map((w, i) => (
        <div key={i} className="warning">⚠ {w}</div>
      ))}

      {result?.insight_text && <p>{result.insight_text}</p>}
    </div>
  );
}
```

### Map Integration

For map-based UIs, use **Leaflet** or **Mapbox GL JS**:

```javascript
// On map click → score that location
map.on('click', async (e) => {
  const { lat, lng } = e.latlng;
  const result = await scoreLocation(lat, lng, selectedUseCase);

  // Add marker with popup
  L.marker([lat, lng])
    .addTo(map)
    .bindPopup(`Score: ${result.site_score.site_readiness_score}/100`)
    .openPopup();
});

// For hotspots → add heatmap layer
const hotspots = await fetchHotspots('Gujarat', 'ev_charging');
L.heatLayer(
  hotspots.map(h => [h.lat, h.lng, h.site_readiness_score / 100]),
  { radius: 25 }
).addTo(map);
```

---

## CORS Configuration

If the frontend runs on a different port (e.g., `localhost:3000`), add CORS middleware to the backend:

```python
# main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Authentication (Placeholder)

The current backend has no authentication. For production:

1. Add API key middleware or JWT authentication
2. Use `api/dependencies.py` to inject auth checks
3. Rate-limit endpoints to prevent abuse

---

## Summary

| What | How |
|---|---|
| Score a site | `POST /score` with `{site_input, use_case}` |
| Compare sites | `POST /compare` with `{sites, use_case}` |
| Find hotspots | `POST /hotspots` with `{state, use_case, top_n}` |
| Check validation | Included in `/score` response as `validation_warnings` |
| Get insights | Included in all responses as `insight_text` |
| Error handling | Check `response.error` field |
| Use case list | Hardcode from `scoring/weights.py` or future endpoint |
