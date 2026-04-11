"""Quick smoke test for all new modules."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 1. Weights catalog
from scoring.weights import USE_CASE_CATALOG, VALID_USE_CASES, USE_CASE_WEIGHTS
errors = []
for key, cfg in USE_CASE_CATALOG.items():
    w = cfg.weights
    total = (w.demand_score + w.accessibility_score + w.competition_score +
             w.suitability_score + w.risk_score + w.infrastructure_score)
    if not (0.99 <= total <= 1.01):
        errors.append(f"{key}: {total:.3f}")
print(f"[1] Catalog: {len(USE_CASE_CATALOG)} entries, weight errors: {errors or 'none'}")

# 2. Config tools
from tools.config_tools import get_default_weights
w = get_default_weights("retail")
print(f"[2] Config tools: retail demand={w.demand_score}")

# 3. Validation
from tools.validation_tools import validate_legal, run_all_validations
r = validate_legal("liquor_store", "Gujarat")
print(f"[3] Legal validation: liquor/Gujarat={r.status}")

# 4. Chat
from agents.chat import _normalize_use_case, _handle_off_topic
print(f"[4] Chat: normalize('ev')={_normalize_use_case('ev')}")

# 5. Prompts
from llm.prompts import CHAT_INTENT_PROMPT, VALIDATION_INSIGHT_ADDENDUM
print(f"[5] Prompts: intent={len(CHAT_INTENT_PROMPT)}c, addendum={len(VALIDATION_INSIGHT_ADDENDUM)}c")

# 6. Graph
from agents.graph import build_graph
g = build_graph()
c = g.compile()
nodes = list(c.get_graph().nodes.keys())
expected = ["chat", "orchestrator", "validation", "chat_response", "error_handler"]
missing = [e for e in expected if e not in nodes]
print(f"[6] Graph: {len(nodes)} nodes, missing={missing or 'none'}")

# 7. Models
from models.agent import AgentOutput
has_cr = "chat_response" in AgentOutput.model_fields
has_vw = "validation_warnings" in AgentOutput.model_fields
print(f"[7] AgentOutput: chat_response={has_cr}, validation_warnings={has_vw}")

# Summary
print()
if errors or missing:
    print("SOME TESTS FAILED")
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
