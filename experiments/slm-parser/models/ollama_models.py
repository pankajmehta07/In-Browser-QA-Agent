import time
import json
from ollama import chat
from prompts.prompt import PROMPT_TEMPLATE

# ── Model Registry ────────────────────────────────────────────────

MODELS = {
    "rule_based": {
        "name":        None,
        "file_tag":    "rule_based",
        "description": "Regex baseline parser — no LLM",
        "enabled":     True
    },
    "qwen_1_5b": {
        "name":        "qwen2.5-coder:1.5b",
        "file_tag":    "Qwen2_5_Coder_1_5B",
        "description": "Qwen 2.5 Coder 1.5B — main SLM candidate",
        "enabled":     True
    },
    "qwen_3b": {
        "name":        "qwen2.5-coder:3b",
        "file_tag":    "Qwen2_5_Coder_3B",
        "description": "Qwen 2.5 Coder 3B — larger Qwen variant",
        "enabled":     True
    },
    "phi_3_5": {
        "name":        "phi3.5",
        "file_tag":    "Phi3_5_Mini",
        "description": "Phi 3.5 Mini — stronger reasoning model",
        "enabled":     True
    },
    "smollm_1_7b": {
        "name":        "smollm2:1.7b",
        "file_tag":    "SmolLM2_1_7B",
        "description": "SmolLM2 1.7B — lightweight fast model",
        "enabled":     True
    }
}


# ── Normalize Steps ───────────────────────────────────────────────

def normalize_steps(steps: list):
    """
    Convert common wrong formats into our expected schema.

    Handles:
        {"goto": "Login"}                        → {"action": "goto",  "target": "Login"}
        {"type": "Email", "value": "..."}        → {"action": "type",  "target": "Email", "value": "..."}
        {"type": {"value": "...", "element": ""}}→ {"action": "type",  "target": "",      "value": "..."}
        {"action": "goto", "target": "Login"}    → unchanged (already correct)
    """
    VALID_ACTIONS = {
        "goto", "click", "type",
        "check_visible", "check_contains"
    }

    normalized = []

    for step in steps:
        if not isinstance(step, dict):
            continue

        # ── Already correct format ────────────────────────────
        if "action" in step and "target" in step:
            normalized.append(step)
            continue

        # ── Action is the key instead of a field ─────────────
        for key in list(step.keys()):
            if key in VALID_ACTIONS:
                val = step[key]

                # {"goto": "Login"}
                if isinstance(val, str):
                    new_step = {"action": key, "target": val}
                    if "value" in step:
                        new_step["value"] = step["value"]
                    normalized.append(new_step)
                    break

                # {"type": {"value": "...", "element": "Email"}}
                elif isinstance(val, dict):
                    target = (
                        val.get("element") or
                        val.get("target") or
                        val.get("name") or
                        ""
                    )
                    value = val.get("value", "")
                    new_step = {"action": key, "target": target}
                    if value:
                        new_step["value"] = value
                    normalized.append(new_step)
                    break

                # {"type": "Email", "value": "..."}
                else:
                    new_step = {"action": key, "target": str(val)}
                    if "value" in step:
                        new_step["value"] = step["value"]
                    normalized.append(new_step)
                    break
        else:
            print(f"  ⚠️  Could not normalize step: {step}")
            continue

    return normalized


# ── Parse Raw Output ──────────────────────────────────────────────

def parse_output(raw: str):
    """
    Strip markdown fences, fix double braces,
    parse JSON, then normalize.
    Returns (valid: bool, steps: list)
    """
    try:
        cleaned = raw.strip()

        # Strip markdown fences
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        # Fix double braces model copies from prompt examples
        cleaned = cleaned.replace("{{", "{").replace("}}", "}")

        parsed = json.loads(cleaned)

        if not isinstance(parsed, list):
            print(f"  ⚠️  Returned {type(parsed).__name__} instead of list")
            return False, []

        if len(parsed) > 0 and not isinstance(parsed[0], dict):
            print(f"  ⚠️  Returned list of strings instead of dicts")
            return False, []

        # Normalize into expected schema
        normalized = normalize_steps(parsed)

        if not normalized:
            return False, []

        return True, normalized

    except json.JSONDecodeError as e:
        print(f"  ⚠️  JSON decode error: {e}")
        return False, []


# ── Call Model ────────────────────────────────────────────────────

def call_model(model_key: str, instruction: str):
    """
    Call a registered model by its key.
    Returns (valid, steps, latency, raw)
    """
    entry = MODELS.get(model_key)

    if not entry:
        raise ValueError(f"Model key '{model_key}' not found in MODELS")

    if not entry["enabled"]:
        raise ValueError(f"Model '{model_key}' is disabled")

    if entry["name"] is None:
        raise ValueError(f"'{model_key}' is rule_based — use rule_based_parse() instead")

    prompt = PROMPT_TEMPLATE.replace("{instruction}", instruction)
    start  = time.time()

    response = chat(
        model    = entry["name"],
        messages = [{"role": "user", "content": prompt}]
    )

    latency      = round(time.time() - start, 2)
    raw          = response.message.content
    valid, steps = parse_output(raw)

    return valid, steps, latency, raw


# ── Utilities ─────────────────────────────────────────────────────

def get_enabled_models():
    return [key for key, entry in MODELS.items() if entry["enabled"]]


def get_file_tag(model_key: str):
    return MODELS[model_key]["file_tag"]


def print_registry():
    print("\n📋 Registered Models:")
    print("-" * 60)
    for key, entry in MODELS.items():
        status = "✅ enabled" if entry["enabled"] else "⏸️  disabled"
        name   = entry["name"] or "rule-based (no model)"
        print(f"  {key:<15} {status}   {name}")
        print(f"  {'':15} tag: {entry['file_tag']}")
        print(f"  {'':15} {entry['description']}\n")