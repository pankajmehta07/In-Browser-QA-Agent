# SLM Parser Evaluation — Results & Analysis

Experiment to determine which parser best converts natural-language QA
instructions into structured JSON test steps for the In-Browser QA Agent.

---

## Experiment Setup

- **Date:** August 2026
- **Dataset:** 30 labeled test cases across 6 categories
- **Models tested:** 5 (1 rule-based baseline + 4 SLMs)
- **Hardware:** Local machine via Ollama (CPU inference)
- **Prompt:** Single fixed prompt — identical for all models
- **Scoring:** Strict exact matching — errors recorded as-is

---

## Models Tested

| Key | Model | Type |
|---|---|---|
| rule_based | Regex parser | Baseline — no LLM |
| qwen_1_5b | qwen2.5-coder:1.5b | Main SLM candidate |
| qwen_3b | qwen2.5-coder:3b | Larger Qwen variant |
| phi_3_5 | phi3.5 | Stronger reasoning model |
| smollm_1_7b | smollm2:1.7b | Lightweight fast model |

---

## Metrics Definition

| Metric | Definition |
|---|---|
| JSON Validity | % of outputs that are parseable JSON |
| Step Accuracy | % of examples where ALL steps are fully correct |
| Action Accuracy | % of individual steps with correct action name |
| Target Accuracy | % of individual steps with correct target name |
| Hallucination Rate | % of outputs containing extra invented steps |
| Avg Latency | Average response time per instruction in seconds |

---

## Overall Results

| Model | JSON Valid | Step Acc | Action Acc | Target Acc | Hallucin | Avg Latency |
|---|---:|---:|---:|---:|---:|---:|
| rule_based | 100% | 17% | 65% | 41% | 0% | 0.00s |
| Qwen2.5-Coder 1.5B | 100% | 50% | 87% | 77% | 3% | 3.50s |
| Qwen2.5-Coder 3B | 100% | 67% | 90% | 87% | 17% | 5.87s |
| Phi3.5 Mini | 90% | 67% | 86% | 78% | 0% | 9.92s |
| SmolLM2 1.7B | 97% | 57% | 78% | 79% | 7% | 5.33s |

---

## Per Category Results (fully correct steps / total)

| Category | rule_based | Qwen 1.5B | Qwen 3B | Phi3.5 | SmolLM2 |
|---|:---:|:---:|:---:|:---:|:---:|
| login | 1/5 | 1/5 | 2/5 | **5/5** | 4/5 |
| users | 0/5 | 4/5 | **5/5** | 3/5 | 3/5 |
| projects | 3/5 | 3/5 | **5/5** | **5/5** | 3/5 |
| billing | 1/5 | **5/5** | **5/5** | **5/5** | 4/5 |
| self_healing | 0/5 | 1/5 | 2/5 | 1/5 | 2/5 |
| ambiguous | 0/5 | 1/5 | 1/5 | 1/5 | 1/5 |
| **TOTAL** | **5/30** | **15/30** | **20/30** | **20/30** | **15/30** |

---

## Key Findings Per Model

### Rule-Based Parser (Baseline)
- **Step accuracy: 17%** — performs poorly overall
- Only works reliably on simple, structured instructions
  that exactly match its regex patterns
- Completely fails on self-healing (0/5) and ambiguous (0/5) categories
  — cannot handle natural language variation at all
- Action accuracy (65%) is misleading — it parses some actions correctly
  but gets targets wrong consistently (41% target accuracy)
- Zero hallucination and zero latency — reliable but extremely limited
- **Verdict:** Useful only as a fast fallback for very strictly formatted
  instructions. Cannot serve as a primary parser for real-world use

---

### Qwen2.5-Coder 1.5B
- **Step accuracy: 50%** — best among small models for its size
- 100% JSON validity — never produces malformed output
- Strong on billing (5/5) and users (4/5) — handles structured
  instructions well
- Struggles with login (1/5) — target naming inconsistency
  ("the Login button" vs "Login")
- Self-healing (1/5) and ambiguous (1/5) categories remain weak
- Low hallucination rate (3%) — rarely invents extra steps
- Fast latency (3.50s avg) — most practical for local deployment
- **Verdict:** Best balance of accuracy and speed among tested models.
  Recommended as the primary SLM candidate for the MVP

---

### Qwen2.5-Coder 3B
- **Step accuracy: 67%** — highest step accuracy among all models
- 100% JSON validity — never produces malformed output
- Perfect on users (5/5), projects (5/5), and billing (5/5)
- Fails login (2/5) — step count mismatch and target naming issues
- Self-healing (2/5) shows some robustness to varied phrasing
- **High hallucination rate (17%)** — most concerning finding.
  Frequently adds extra steps not present in the instruction
- Slower latency (5.87s avg) due to larger model size
- **Verdict:** Highest accuracy but hallucination rate is a serious
  concern for a QA agent where extra actions could corrupt test results.
  Needs hallucination mitigation before production use

---

### Phi3.5 Mini
- **Step accuracy: 67%** — tied highest with Qwen 3B
- **JSON validity: 90%** — only model with JSON failures.
  3 cases produced invalid JSON (healing-005, ambiguous-002,
  ambiguous-003) with "Extra data" and parse errors
- Perfect on login (5/5) and projects (5/5) — strongest on
  structured, well-formed instructions
- Fails on users (3/5) — target naming inconsistency
- Self-healing (1/5) and ambiguous (1/5) remain weak
- Zero hallucination — never invents extra steps
- **Slowest latency (9.92s avg)** — nearly 2x slower than Qwen 1.5B
- **Verdict:** Strong accuracy and zero hallucination are positives,
  but JSON failures and slow latency make it unsuitable as the
  primary local parser. Could serve as a higher-tier fallback

---

### SmolLM2 1.7B
- **Step accuracy: 57%** — mid-range performance
- JSON validity: 97% — one JSON parse failure (healing-004)
- Solid on login (4/5) and billing (4/5)
- Weak on self-healing (2/5) and ambiguous (1/5)
- Moderate hallucination (7%) and latency (5.33s avg)
- Action accuracy (78%) is the lowest among SLMs —
  occasionally uses wrong action types
- **Verdict:** No clear advantage over Qwen 1.5B despite similar
  model size. Not recommended as primary parser

---

## Category-Level Observations

### Structured instructions (login, users, billing, projects)
All SLMs perform significantly better than the rule-based parser.
Qwen 3B and Phi3.5 achieve perfect scores on billing and projects.
This confirms SLMs are viable for well-formed QA instructions.

### Self-Healing category
All models score poorly (0-2/5). This is the most important finding
for the project — models struggle when the same intent is expressed
differently (e.g. "press the login button" vs "click Login").
This is the target accuracy problem — models use descriptive names
from the instruction rather than canonical UI element names.

### Ambiguous category
All models score 1/5. Rule-based scores 0/5.
Vague instructions ("login with admin credentials",
"check if users page works") require inference beyond what
current SLMs can reliably handle without page context.
This confirms that page context (accessibility tree) must be
provided to the model for ambiguous cases — which is exactly
what the main QA agent pipeline does.

---

## Critical Observations

### 1. Target Naming Is the Primary Failure Mode
The most common error across all models is target naming —
models use the phrasing from the instruction rather than the
canonical UI element name:
- "Login button" instead of "Login"
- "email input" instead of "Email"
- "the user list" instead of "user list"

This is expected behavior when models only see the instruction
with no page context. In the full agent pipeline, the accessibility
tree is provided — this should significantly reduce target errors.

### 2. JSON Validity Is Largely Solved
With output normalization (markdown fence stripping, double-brace
fixing), JSON validity is 97-100% for most models.
Phi3.5 is the exception with 90% — it occasionally appends
explanation text after the JSON array.

### 3. Hallucination Is a Real Risk
Qwen 3B's 17% hallucination rate is concerning. In a QA agent,
extra invented steps could click wrong elements or submit forms
unexpectedly. Any production use of Qwen 3B needs a step-count
validation layer that rejects outputs with significantly more
steps than the instruction implies.

### 4. Rule-Based Parser Has a Specific Role
Despite 17% step accuracy, the rule-based parser has two strengths:
zero latency and zero hallucination. For very simple, predictable
instructions ("Click Login", "Go to Users"), it remains a valid
fast-path option that requires no model inference.

### 5. Ambiguous Instructions Need Page Context
The universal failure on ambiguous instructions ("check if users
page works") is not a model weakness — it is a task definition
issue. These instructions are genuinely underspecified without
knowing what elements exist on the page. The full agent pipeline
addresses this by injecting the accessibility tree into the prompt.

---

## Recommendation

### Option A — Prioritize Reliability: Qwen2.5-Coder 1.5B
- 100% JSON validity — never crashes the pipeline
- 3.50s avg latency — faster for large test suites
- Lower accuracy (50%) but always returns something parseable
- Recommended if pipeline stability is the priority

### Option B — Prioritize Accuracy: Phi3.5 Mini
- Higher step accuracy (67%) and zero hallucination
- Acceptable latency (9.92s) for test automation context
- JSON failures on 3/30 cases — needs a retry/fallback layer
- Recommended if accuracy is the priority and a fallback
  exists for JSON parse failures

### Final Recommendation
Use Phi3.5 Mini as primary with Qwen 1.5B as JSON-failure fallback:

Instruction
    ↓
Phi3.5 Mini
    ↓ JSON parse error
Qwen 1.5B retry
    ↓ still fails
Cloud LLM fallback

## Limitations of This Evaluation

- Dataset is synthetic and controlled — real user instructions
  will be more varied and unpredictable
- No page context was provided — full agent pipeline includes
  the accessibility tree which should improve target accuracy
- Models were run on CPU — GPU inference would significantly
  reduce latency numbers
- Single run per example — results may vary slightly between runs
  due to model temperature and sampling
- 30 examples is a small dataset — findings are indicative,
  not statistically conclusive
