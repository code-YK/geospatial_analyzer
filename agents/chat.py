"""
agents/chat.py — Conversational chat node.

Single entry point for all user interaction.  Sits at the start of
the LangGraph graph and determines how to handle each message:
  • needs_graph  → extract params, trigger the scoring/hotspot pipeline
  • direct_answer → answer general questions about the system
  • follow_up    → answer from existing state data (post-analysis)
  • off_topic    → politely redirect, track retry count

Also called AFTER the insight node to wrap the final response in a
conversational format.
"""

import json
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from agents.state import AgentState
from core.logger import get_logger
from llm.llm_config import get_llm
from llm.prompts import (
    CHAT_DIRECT_ANSWER_PROMPT,
    CHAT_FOLLOW_UP_PROMPT,
    CHAT_INTENT_PROMPT,
)
from models.site import SiteInput
from scoring.weights import VALID_USE_CASES, USE_CASE_CATALOG

logger = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────

MAX_RETRIES = 3          # max off-topic / invalid attempts before session ends
MAX_HISTORY = 20         # max conversation turns kept in memory

FIELD_QUESTIONS = {
    "lat":        "What is the latitude of the site you'd like to evaluate?",
    "lng":        "What is the longitude of the site?",
    "use_case":   "What type of business are you planning? (e.g. retail store, EV charging, hospital)",
    "state_name": "Which Indian state is this site located in?",
}


# ── Main Chat Node ───────────────────────────────────────────────────────

async def chat_node(state: AgentState) -> dict:
    """
    Entry point for all user interaction.

    Flow:
    1. Append user message to conversation_history
    2. If retry_count >= MAX_RETRIES → set error, route to error_handler
    3. Call _detect_intent() — LLM call with strict JSON output
    4. Branch on intent:
       - "needs_graph"    → extract params, validate completeness, trigger graph
       - "direct_answer"  → answer from general knowledge (bounded)
       - "follow_up"      → answer from existing site_features / score_breakdown
       - "off_topic"      → increment retry_count, politely redirect
    5. Append assistant response to conversation_history
    6. Trim history to MAX_HISTORY turns
    """
    updates: dict = {"current_node": "chat"}

    raw_message = state.get("raw_user_message", "")
    history = list(state.get("conversation_history", []))
    retry_count = state.get("retry_count", 0)

    # 1. Append user turn
    if raw_message:
        history.append({"role": "user", "content": raw_message})

    # 2. Check retry limit
    if retry_count >= MAX_RETRIES:
        updates["error"] = "Session ended: too many off-topic messages."
        updates["chat_response"] = (
            "I'm sorry, this session has ended due to too many "
            "off-topic messages. Please start a new session."
        )
        updates["conversation_history"] = history
        return updates

    # 3. Detect intent
    try:
        intent_data = await _detect_intent(raw_message, history, state)
    except Exception as exc:
        logger.error("Intent detection failed: %s", exc)
        updates["chat_response"] = (
            "I had trouble understanding that. Could you rephrase? "
            "Try something like: 'Score a retail site at 23.02, 72.57'"
        )
        updates["chat_intent"] = "error"
        history.append({"role": "assistant", "content": updates["chat_response"]})
        updates["conversation_history"] = _trim_history(history)
        return updates

    intent = intent_data.get("intent", "off_topic")
    updates["chat_intent"] = intent

    # 4. Branch on intent
    if intent == "needs_graph":
        response, updates = await _handle_needs_graph(
            state, intent_data, updates, history
        )
    elif intent == "direct_answer":
        response = await _answer_direct(raw_message, history)
        updates["chat_response"] = response
        updates["retry_count"] = 0  # valid interaction resets
    elif intent == "follow_up":
        if state.get("analysis_complete"):
            response = await _answer_follow_up(state, raw_message, history)
        else:
            response = (
                "No site has been analyzed yet in this session. "
                "Try: 'Score a retail site at 23.02, 72.57'"
            )
        updates["chat_response"] = response
        updates["retry_count"] = 0
    elif intent == "off_topic":
        response = _handle_off_topic(retry_count)
        updates["chat_response"] = response
        updates["retry_count"] = retry_count + 1
        # After max retries, set error for next turn
        if retry_count + 1 >= MAX_RETRIES:
            updates["error"] = "Session ended: too many off-topic messages."
    else:
        response = "I'm not sure how to help with that. Try asking about a business location."
        updates["chat_response"] = response

    # 5. Append assistant turn
    history.append({"role": "assistant", "content": updates.get("chat_response", "")})

    # 6. Trim
    updates["conversation_history"] = _trim_history(history)

    return updates


# ── Chat Response Node (post-insight) ────────────────────────────────────

async def chat_response_node(state: AgentState) -> dict:
    """
    Called AFTER the insight node to format the final conversational
    response and set analysis_complete = True.
    """
    updates: dict = {"current_node": "chat_response"}

    insight = state.get("insight_text", "")
    warnings = state.get("validation_warnings", [])

    # Build conversational wrapper
    parts = []
    if insight:
        parts.append(insight)
    if warnings:
        parts.append("\n⚠️ **Regulatory Warnings:**")
        for w in warnings:
            parts.append(f"  • {w}")

    updates["chat_response"] = "\n".join(parts) if parts else insight
    updates["analysis_complete"] = True

    # Append to history
    history = list(state.get("conversation_history", []))
    history.append({"role": "assistant", "content": updates["chat_response"]})
    updates["conversation_history"] = _trim_history(history)

    return updates


# ── Intent Detection ─────────────────────────────────────────────────────

async def _detect_intent(
    message: str,
    history: List[dict],
    state: AgentState,
) -> dict:
    """
    LLM call to classify user intent and extract parameters.
    Returns parsed JSON dict with keys: intent, extracted, confidence.
    """
    llm = get_llm()

    # Include recent history for context
    recent = history[-6:] if len(history) > 6 else history
    history_text = "\n".join(
        f"{t['role'].upper()}: {t['content']}" for t in recent
    )

    user_prompt = (
        f"Conversation history:\n{history_text}\n\n"
        f"Current user message: {message}\n\n"
        f"Analysis already done: {state.get('analysis_complete', False)}"
    )

    messages = [
        SystemMessage(content=CHAT_INTENT_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    response = await llm.ainvoke(messages)
    content = response.content.strip()

    # Strip markdown fences
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
    if content.endswith("```"):
        content = content[:-3].strip()
    if content.startswith("json"):
        content = content[4:].strip()

    parsed = json.loads(content)
    logger.info("Intent detected: %s (confidence: %.2f)",
                parsed.get("intent"), parsed.get("confidence", 0))
    return parsed


# ── Needs-Graph Handler ──────────────────────────────────────────────────

async def _handle_needs_graph(
    state: AgentState,
    intent_data: dict,
    updates: dict,
    history: List[dict],
) -> tuple:
    """
    Handle the 'needs_graph' intent — extract params, check completeness,
    and either ask for missing fields or trigger the graph.
    """
    extracted = intent_data.get("extracted") or {}

    # Merge with any previously-extracted partial data
    lat = extracted.get("lat") or state.get("site_input", {})
    if isinstance(lat, dict):
        lat = lat.get("lat")
    elif hasattr(lat, "lat"):
        lat = lat.lat
    else:
        lat = extracted.get("lat")

    lng = extracted.get("lng") or None
    if lng is None and state.get("site_input"):
        si = state.get("site_input")
        lng = si.lng if hasattr(si, "lng") else None
    else:
        lng = extracted.get("lng")

    use_case = extracted.get("use_case") or state.get("use_case")
    state_name = extracted.get("state_name") or state.get("state_name", "")

    # Normalize use_case: try fuzzy match to catalog keys
    if use_case:
        use_case = _normalize_use_case(use_case)

    # Check what's missing — only lat, lng, and use_case are required.
    # state_name is optional (inferred from DB after fetching site features).
    REQUIRED_FIELDS = {"lat", "lng", "use_case"}
    missing = [f for f in extracted.get("missing_fields", []) if f in REQUIRED_FIELDS]
    if not missing:
        missing = []
        if lat is None:
            missing.append("lat")
        if lng is None:
            missing.append("lng")
        if not use_case:
            missing.append("use_case")

    if missing:
        # Ask for ONE missing field
        field = missing[0]
        question = FIELD_QUESTIONS.get(
            field,
            f"Could you provide the {field}?"
        )
        updates["chat_response"] = question
        updates["chat_intent"] = "ask_field"
        updates["missing_fields"] = missing

        # Store partial extractions
        if lat is not None and lng is not None:
            updates["site_input"] = SiteInput(lat=float(lat), lng=float(lng))
        if use_case:
            updates["use_case"] = use_case
        if state_name:
            updates["state_name"] = state_name

        return question, updates

    # All fields present — set up for graph run
    updates["site_input"] = SiteInput(lat=float(lat), lng=float(lng))
    updates["use_case"] = use_case
    updates["state_name"] = state_name
    updates["missing_fields"] = []
    updates["retry_count"] = 0
    updates["chat_response"] = (
        f"Analyzing a **{USE_CASE_CATALOG.get(use_case, use_case)}** site "
        f"at ({lat}, {lng})..."
    )

    # Check if this is a hotspot request (no specific lat/lng, has state_name)
    comparison_sites = extracted.get("comparison_sites")
    if comparison_sites:
        updates["comparison_sites"] = [
            SiteInput(lat=s["lat"], lng=s["lng"])
            for s in comparison_sites if "lat" in s and "lng" in s
        ]

    return updates["chat_response"], updates


# ── Follow-Up Answer ─────────────────────────────────────────────────────

async def _answer_follow_up(
    state: AgentState,
    user_message: str,
    history: List[dict],
) -> str:
    """
    Answer using ONLY data already in state — no new DB calls.
    """
    features = state.get("site_features")
    breakdown = state.get("score_breakdown")
    final_score = state.get("final_score") or 0
    use_case = state.get("use_case") or ""

    # Build site context (key fields only)
    site_ctx = "No site data available."
    if features:
        site_ctx = (
            f"State: {getattr(features, 'state', 'N/A')}, "
            f"District: {getattr(features, 'district', 'N/A')}, "
            f"Population density: {getattr(features, 'population_density', 'N/A')}, "
            f"AQI: {getattr(features, 'aqi', 'N/A')}, "
            f"Flood risk: {getattr(features, 'flood_risk_score', 'N/A')}, "
            f"Road density: {getattr(features, 'road_density', 'N/A')}, "
            f"Commercial ratio: {getattr(features, 'commercial_ratio', 'N/A')}"
        )

    # Build score context
    score_ctx = f"Final score: {final_score:.1f}/100\n"
    if breakdown:
        for dim, contrib in breakdown.contributions.items():
            score_ctx += (
                f"  {dim}: raw={contrib.raw:.0f}, "
                f"weight={contrib.weight:.2f}, "
                f"contribution={contrib.contribution:.1f}\n"
            )
        score_ctx += f"Use case: {use_case}\n"
        score_ctx += f"Strengths: {', '.join(breakdown.strengths)}\n"
        score_ctx += f"Weaknesses: {', '.join(breakdown.weaknesses)}"

    # History context
    recent = history[-6:] if len(history) > 6 else history
    hist_text = "\n".join(
        f"{t['role'].upper()}: {t['content']}" for t in recent
    )

    llm = get_llm()
    prompt = CHAT_FOLLOW_UP_PROMPT.format(
        site_context=site_ctx,
        score_context=score_ctx,
        history=hist_text,
    )

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=user_message),
    ]

    try:
        response = await llm.ainvoke(messages)
        return response.content.strip()
    except Exception as exc:
        logger.error("Follow-up answer failed: %s", exc)
        return (
            f"The site scored {final_score:.1f}/100 for {use_case}. "
            "I couldn't generate a detailed answer right now — please try again."
        )


# ── Direct Answer ────────────────────────────────────────────────────────

async def _answer_direct(
    user_message: str,
    history: List[dict],
) -> str:
    """Answer general questions about the system — no DB calls."""
    llm = get_llm()

    messages = [
        SystemMessage(content=CHAT_DIRECT_ANSWER_PROMPT),
        HumanMessage(content=user_message),
    ]

    try:
        response = await llm.ainvoke(messages)
        return response.content.strip()
    except Exception as exc:
        logger.error("Direct answer failed: %s", exc)
        return (
            "The GeoSpatial Site Readiness Analyzer scores locations "
            "across 6 dimensions: demand, accessibility, competition, "
            "suitability, risk, and infrastructure.  Each dimension is "
            "weighted by use case. Ask me to score a specific site to "
            "see it in action!"
        )


# ── Off-Topic Handler ────────────────────────────────────────────────────

def _handle_off_topic(retry_count: int) -> str:
    """Escalating redirects for off-topic messages."""
    if retry_count == 0:
        return (
            "I can only help with site selection and business location "
            "analysis. Try asking: 'Score a retail site at lat 23.02, "
            "lng 72.57' or 'Find top EV charging hotspots in Gujarat'."
        )
    elif retry_count == 1:
        return (
            "Let's stay focused on location analysis. "
            "What business type and location would you like to evaluate?"
        )
    else:
        return (
            "I'm designed specifically for geospatial site analysis. "
            "This session will end after one more off-topic message."
        )


# ── Helpers ──────────────────────────────────────────────────────────────

def _normalize_use_case(raw: str) -> str:
    """
    Try to match a free-text use case to a catalog key.
    Falls back to the raw string if no match found.
    """
    if not raw:
        return raw

    # Exact match (e.g. "retail", "ev_charging")
    key = raw.lower().strip().replace(" ", "_").replace("-", "_")
    if key in VALID_USE_CASES:
        return key

    raw_lower = raw.lower()

    # Keyword mapping for common short terms (checked BEFORE fuzzy name match)
    KEYWORD_MAP = {
        "ev": "ev_charging",
        "electric vehicle": "ev_charging",
        "charging": "ev_charging",
        "petrol": "petrol_pump",
        "gas station": "cng_station",
        "doctor": "clinic",
        "medical": "hospital",
        "shop": "retail",
        "store": "retail",
        "factory": "manufacturing",
        "office": "coworking",
        "gym": "gym",
        "fitness": "gym",
        "hair": "salon",
        "beauty": "salon",
        "food": "restaurant",
        "eat": "restaurant",
        "bank": "bank_branch",
        "atm": "atm",
        "school": "school",
        "college": "college",
        "hotel": "hotel",
        "warehouse": "warehouse",
        "godown": "warehouse",
        "solar": "solar_plant",
        "wind": "wind_farm",
        "telecom": "telecom_tower",
        "tower": "telecom_tower",
        "data center": "data_center",
        "cold storage": "cold_storage",
    }

    for keyword, mapped_key in KEYWORD_MAP.items():
        if raw_lower == keyword or raw_lower == keyword + "s":
            return mapped_key

    # Fuzzy match: check if any catalog display name contains the raw text
    # (only for inputs with 4+ chars to avoid false matches)
    if len(raw_lower) >= 4:
        for k, cfg in USE_CASE_CATALOG.items():
            if raw_lower in cfg.name.lower() or cfg.name.lower() in raw_lower:
                return k

    # Partial keyword match (substring)
    for keyword, mapped_key in KEYWORD_MAP.items():
        if keyword in raw_lower:
            return mapped_key

    # Give up — return cleaned version
    return key


def _trim_history(history: List[dict]) -> List[dict]:
    """Keep only the last MAX_HISTORY turns."""
    if len(history) > MAX_HISTORY:
        return history[-MAX_HISTORY:]
    return history
