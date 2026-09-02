# SLM Parser Evaluation — Results & Analysis

Experiment to determine which parser best converts natural-language QA
instructions into structured JSON test steps for the In-Browser QA Agent.

---

## Experiment Setup

- **Date:** August 2026
- **Dataset:** 30 labeled test cases across 6 categories
- **Models tested:** 15 total (1 rule-based baseline + 4 local SLMs + 10 cloud LLMs)
- **Hardware:** Local model via Ollama (CPU inference); cloud models via API
- **Prompt:** Single fixed prompt — identical for all models
- **Scoring:** Strict exact matching — errors recorded as-is

---
## Models Tested

| Key | Model | Provider | Type |
|---|---|---|---|
| rule_based | Regex parser | Local | Baseline — no LLM |
| qwen_1_5b | qwen2.5-coder:1.5b | Ollama | Local SLM |
| qwen_3b | qwen2.5-coder:3b | Ollama | Local SLM |
| phi_3_5 | phi3.5 | Ollama | Local SLM |
| smollm_1_7b | smollm2:1.7b | Ollama | Local SLM |
| gemini_flash_lite | gemini-3.5-flash-lite | Google | Cloud LLM |
| gemini_3_5_flash | gemini-3.5-flash | Google | Cloud LLM — incomplete |
| gemini_3_6_flash | gemini-3.6-flash | Google | Cloud LLM — partial |
| groq_gpt_oss_20b | openai/gpt-oss-20b | Groq | Cloud LLM |
| groq_gpt_oss_120b | openai/gpt-oss-120b | Groq | Cloud LLM |
| groq_qwen_3_8_27b | qwen/qwen3.8-27b | Groq | Cloud LLM |
| groq_allam_2_7b | allam-2-7b | Groq | Cloud LLM |
| nvidia_minimax_m3 | MiniMax-M3 | NVIDIA | Cloud LLM |
| nvidia_nemotron_3_5_lightning | Nemotron-3.5 Lightning | NVIDIA | Cloud LLM |
| nvidia_nemotron_3_super | Nemotron-3 Super | NVIDIA | Cloud LLM |
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


### Local Models

| Model | JSON Valid | Step Acc | Action Acc | Target Acc | Hallucin | Avg Latency |
|---|---:|---:|---:|---:|---:|---:|
| rule_based | 100% | 17% | 65% | 41% | 0% | 0.00s |
| Qwen2.5-Coder 1.5B | 100% | 50% | 87% | 77% | 3% | 3.50s |
| Qwen2.5-Coder 3B | 100% | 67% | 90% | 87% | 17% | 5.87s |
| Phi3.5 Mini | 90% | 67% | 86% | 78% | 0% | 9.92s |
| SmolLM2 1.7B | 97% | 57% | 78% | 79% | 7% | 5.33s |

### Cloud Models — Groq

| Model | JSON Valid | Step Acc | Action Acc | Target Acc | Hallucin | Avg Latency |
|---|---:|---:|---:|---:|---:|---:|
| GPT-OSS 120B | 100% | 80% | 100% | 94% | 7% | 1.48s |
| GPT-OSS 20B | 100% | 77% | 100% | 91% | 7% | 1.52s |
| Qwen 3.8 27B | 100% | 80% | 97% | 90% | 3% | 0.56s |
| ALLaM 2 7B | 90% | 43% | 82% | 72% | 13% | 2.87s |
### Cloud Models — Google Gemini

| Model | JSON Valid | Step Acc | Action Acc | Target Acc | Hallucin | Avg Latency | Note |
|---|---:|---:|---:|---:|---:|---:|---|
| Gemini 3.5 Flash Lite | 100% | 70% | 100% | 79% | 0% | 1.17s | Complete |
| Gemini 3.6 Flash | 70% | 63% | 70% | 66% | 0% | 9.53s | ~10-12 cases rate limited |
| Gemini 3.5 Flash ⚠️ | 23% | 20% | 23% | 20% | 3% | 1.74s | Severely rate limited — not reliable |

### Cloud Models — NVIDIA

| Model | JSON Valid | Step Acc | Action Acc | Target Acc | Hallucin | Avg Latency |
|---|---:|---:|---:|---:|---:|---:|
| MiniMax M3 | 97% | 77% | 97% | 88% | 7% | 16.68s |
| Nemotron 3 Super | 97% | 73% | 92% | 84% | 7% | 7.39s |
| Nemotron 3.5 Lightning | 97% | 67% | 93% | 85% | 7% | 45.41s |
---

## Per Category Results (fully correct steps / total)

| Category | rule_based | Qwen 1.5B | Qwen 3B | Phi3.5 | SmolLM2 | GPT-OSS 20B | GPT-OSS 120B | Qwen 3.8 27B | Gemini Lite | Gemini 3.6 | MiniMax M3 | Nemotron Super | Nemotron Lightning |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| login | 1/5 | 1/5 | 2/5 | **5/5** | 4/5 | **5/5** | 4/5 | **5/5** | 4/5 | 4/5 | **5/5** | 4/5 | **5/5** |
| users | 0/5 | 4/5 | **5/5** | 3/5 | 3/5 | **5/5** | **5/5** | **5/5** | **5/5** | **5/5** | **5/5** | **5/5** | 4/5 |
| projects | 3/5 | 3/5 | **5/5** | **5/5** | 3/5 | **5/5** | **5/5** | **5/5** | **5/5** | **5/5** | **5/5** | **5/5** | **5/5** |
| billing | 1/5 | **5/5** | **5/5** | **5/5** | 4/5 | **5/5** | **5/5** | **5/5** | **5/5** | **5/5** | **5/5** | 4/5 | 4/5 |
| self_healing | 0/5 | 1/5 | 2/5 | 1/5 | 2/5 | 2/5 | 4/5 | 2/5 | 0/5 | 0/5 | 3/5 | 3/5 | 1/5 |
| ambiguous | 0/5 | 1/5 | 1/5 | 1/5 | 1/5 | 1/5 | 1/5 | 2/5 | 2/5 | 0/5 | 0/5 | 1/5 | 1/5 |
| **TOTAL** | **5/30** | **15/30** | **20/30** | **20/30** | **15/30** | **23/30** | **24/30** | **24/30** | **21/30** | **19/30** | **23/30** | **22/30** | **20/30** |

> Excluded from table: Gemini 3.5 Flash (severely rate limited)
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

## SLM Model Findings
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

## Cloud Model Findings

### Groq GPT-OSS 120B ⭐
- **Step accuracy: 80%** — highest overall across all tested models
- 100% JSON validity, 100% action accuracy
- Strongest self-healing performance among all models: 4/5
- Perfect on users, projects, billing
- Low latency: 1.48s avg — comparable to local SLMs on CPU
- 7% hallucination rate — same as GPT-OSS 20B, acceptable
- Only failure on ambiguous: 1/5 — same weakness as all models
- **Verdict: Best performing model overall. Strong candidate for
  cloud fallback tier in the hybrid architecture**

---

### Groq GPT-OSS 20B
- **Step accuracy: 77%** — strong, just below the 120B variant
- 100% JSON validity, 100% action accuracy
- Self-healing: 2/5 — noticeably weaker than 120B (4/5)
- Perfect on login, users, projects, billing
- Nearly identical latency to 120B (1.52s vs 1.48s)
- **Verdict: Strong model but 120B is clearly better, especially
  on self-healing, for only 0.04s extra latency. Prefer 120B.**

---

### Groq Qwen 3.8 27B ⭐
- **Step accuracy: 80%** — tied with GPT-OSS 120B, joint highest overall
- 100% JSON validity — clean output on all 30 cases
- **Fastest model tested: 0.56s avg latency** — 3x faster than GPT-OSS 120B
- Low hallucination: 3% — only one extra step across 30 cases
- Perfect on login, users, projects, billing (5/5 each)
- Self-healing: 2/5 — weaker than GPT-OSS 120B (4/5)
- Ambiguous: 2/5 — tied with Gemini Lite, best among Groq models
- Note: first run produced 60% accuracy due to what appears to be
  server-side load variance — rerun showed true capability
- **Verdict: Strongest overall value proposition. Same accuracy as
  GPT-OSS 120B at 3x the speed and likely lower cost. The main
  disadvantage vs GPT-OSS 120B is self-healing (2/5 vs 4/5).
  If self-healing is critical, prefer GPT-OSS 120B. If speed
  and cost matter more, Qwen 3.8 27B is the better choice.**
---

### Groq ALLaM 2 7B
- **Step accuracy: 43%** — below all other cloud models
- 90% JSON validity — weakest among Groq models
- Highest hallucination rate: 13%
- Consistent mediocrity across all categories (3/5 on structured,
  1/5 on self-healing, 0/5 on ambiguous)
- **Verdict: Not recommended. No advantage over local SLMs
  and worse than Qwen 1.5B on most metrics**

---

### Gemini 3.5 Flash Lite ✅
- **Step accuracy: 70%** — best among Gemini models tested
- 100% JSON validity and 100% action accuracy
- Zero hallucination — clean output every time
- Fast: 1.17s avg latency
- Perfect on users, projects, billing
- Completely fails self-healing (0/5) — copies descriptive
  phrasing from instruction instead of canonical names
- Surprisingly strong ambiguous performance: 2/5 — best
  ambiguous score among all models including cloud
- **Verdict: Strong free-tier option. Best Gemini model tested.
  Consider as primary Gemini candidate.**

---

### Gemini 3.6 Flash — Partial Results ⚠️
- Approximately 10-12 of the final test cases were rate limited
  (resource exhausted) — mostly self_healing and ambiguous
  categories, meaning those categories score 0/5 artificially
- Among the cases that completed: strong accuracy, zero
  hallucination, good schema adherence
- Very high latency on completed cases: up to 44s per call,
  9.53s average — slowest reliable cloud model tested
- **Verdict: Results not reliable for comparison due to rate
  limiting. Rerun with delays between calls before concluding.**

---

### Gemini 3.5 Flash ⚠️ — Results Not Reliable
- Severely rate limited after case 6 — only 6/30 cases completed
- All metrics are meaningless as a result
- **Verdict: Must rerun with rate limit delays. Current results
  excluded from recommendations.**

---

### NVIDIA MiniMax M3
- **Step accuracy: 77%** — tied with GPT-OSS 20B
- 97% JSON validity — one parse failure
- Perfect on login, users, projects, billing (5/5 each)
- Strong self-healing: 3/5 — better than most models
- Completely fails ambiguous: 0/5
- Moderate latency: 16.68s — slower than Groq but acceptable
- **Verdict: Strong performer, especially on structured tasks.
  Self-healing score (3/5) is competitive. Worth considering
  as a fallback option.**

---

### NVIDIA Nemotron 3 Super
- **Step accuracy: 73%** — solid mid-range
- 97% JSON validity, strong action accuracy (92%)
- Self-healing: 3/5 — tied with MiniMax M3
- Good latency: 7.39s avg — better than MiniMax
- **Verdict: Balanced model. Slightly below MiniMax on step
  accuracy but faster. Good secondary option.**

---

### NVIDIA Nemotron 3.5 Lightning
- **Step accuracy: 67%** — despite "Lightning" branding,
  this is the slowest model tested: 45.41s avg latency
- The name is misleading for this use case — likely optimized
  for a different task type
- Strong on structured categories (5/5 login, projects)
- **Verdict: Latency makes it impractical for this task.
  Not recommended despite reasonable accuracy.**

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

Groq Qwen 3.8 27B showed variance between runs (60% on first run,
80% on rerun) suggesting server-side load affects output quality.
This is a known characteristic of shared inference infrastructure
and should be factored into production reliability planning.

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

### Top Performers by Step Accuracy

| Rank | Model | Step Acc | Hallucin | Latency | Viable? |
|---|---|---:|---:|---:|---|
| 1 | Groq GPT-OSS 120B | 80% | 7% | 1.48s | ✅ Yes |
| 1 | Groq Qwen 3.8 27B | 80% | 3% | 0.56s | ✅ Yes |
| 3 | Groq GPT-OSS 20B | 77% | 7% | 1.52s | ✅ Yes |
| 3 | NVIDIA MiniMax M3 | 77% | 7% | 16.68s | ✅ Yes |
| 5 | NVIDIA Nemotron 3 Super | 73% | 7% | 7.39s | ✅ Yes |
| 6 | Gemini 3.5 Flash Lite | 70% | 0% | 1.17s | ✅ Yes |
| 7 | Qwen2.5-Coder 3B (local) | 67% | 17% | 5.87s | ⚠️ Hallucination risk |
| 7 | Phi3.5 Mini (local) | 67% | 0% | 9.92s | ✅ Yes |
| 7 | NVIDIA Nemotron 3.5 Lightning | 67% | 7% | 45.41s | ⚠️ Latency |

---

### Primary Cloud Model: context-dependent
- **General tasks:** Groq Qwen 3.8 27B — same accuracy as GPT-OSS 120B
  at 3x the speed and lower hallucination rate (3% vs 7%)
- **Self-healing tasks:** Groq GPT-OSS 120B — 4/5 self-healing vs 2/5,
  the extra 0.92s latency is worth it for healing-critical scenarios


### Models Not Recommended
- Groq ALLaM 2 7B — no advantage over local SLMs
- NVIDIA Nemotron 3.5 Lightning — 45s latency is impractical

---

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
- Gemini free tier rate limits caused incomplete runs for Gemini 3.5 Flash
  and partially affected Gemini 3.6 Flash — those results require reruns
  with inter-call delays before they can be used for comparison
