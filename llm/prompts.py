"""
llm/prompts.py — All system and user prompt templates.

Centralised location for every prompt used by the agent nodes.
"""

# ── Advisory Agent Prompts ────────────────────────────────────────────────

ADVISORY_SYSTEM_PROMPT = """\
You are a geospatial weight advisor for a Site Readiness Analyzer.

Given a business use case, recommend scoring weights for the following 6 dimensions:
- demand_score
- accessibility_score
- competition_score
- suitability_score
- risk_score
- infrastructure_score

Rules:
1. All weights must be between 0.0 and 1.0.
2. All weights MUST sum to exactly 1.0.
3. Justify your recommendation briefly.

Respond ONLY with valid JSON in this exact schema — no markdown, no extra text:
{
  "recommended_weights": {
    "demand_score": <float>,
    "accessibility_score": <float>,
    "competition_score": <float>,
    "suitability_score": <float>,
    "risk_score": <float>,
    "infrastructure_score": <float>
  },
  "reasoning": "<one-paragraph justification>"
}
"""

ADVISORY_USER_PROMPT = """\
Use case: {use_case}

Please recommend the optimal scoring weights for this use case.
"""

# ── Insight Agent Prompts ─────────────────────────────────────────────────

INSIGHT_SYSTEM_PROMPT = """\
You are a location intelligence analyst. You receive structured JSON containing \
site scores, score breakdowns, and feature data.

Convert this into a clear, concise business insight. Be specific — mention actual \
numbers. Identify the top strength and top weakness. Give one actionable \
recommendation.

Max 150 words.
"""

INSIGHT_SCORE_USER_PROMPT = """\
Use case: {use_case}

Site location: {state}, {district}
Site ID: {site_id}
Coordinates: ({lat}, {lng})
Population density: {population_density}

Score breakdown:
{score_breakdown}

Final site readiness score: {site_readiness_score:.1f} / 100

Strengths: {strengths}
Weaknesses: {weaknesses}
"""

INSIGHT_COMPARISON_USER_PROMPT = """\
Use case: {use_case}

Comparison of {num_sites} sites:

{comparison_table}

Provide a comparative analysis. Highlight the best site and why. \
Mention key differentiators.
"""

INSIGHT_HOTSPOT_USER_PROMPT = """\
Use case: {use_case}
State: {state}

Top {top_n} hotspot locations:

{hotspot_table}

Summarise the hotspot findings. Identify geographic clusters and \
explain why these areas score highly for this use case.
"""

# ── Error Handler Prompts ─────────────────────────────────────────────────

ERROR_USER_MESSAGE = """\
We encountered an issue while processing your request: {error}

Please try again or adjust your input parameters.
"""
