# SLM Parser Evaluation

Experiment to evaluate whether small language models (SLMs) can convert
natural-language QA instructions into structured JSON test steps, and how
they compare against a rule-based baseline parser.

---

## Research Question

Can a locally-running SLM reliably parse natural-language test instructions
into a structured action schema well enough to replace or augment a
rule-based parser in a browser QA agent?

---

## Experiment Structure
```
experiments/slm-parser/
├──dataset
│  └── dataset.json             ← 30 labeled test instructions with expected outputs
├──evaluation
│  └── evaluation.md            ← results table and findings (filled after running)
├── models/
│  └── llm_models.py            ← LLM model registry, call functions, output parser
│  └── rule_based_parser.py     ← regex baseline parser (Baseline A)
│  └── ollama_models.py         ← local model registry, call functions, output parser
├──prompts
│  └── prompts.md               ← fixed prompt template used for all models
├── README.md        
├── requirements.txt            ← Python dependencies for this experiment only
├── run_evaluation.py           ← main evaluation runner
└── results/                    ← auto-generated result files (git-ignored)
```


---

## Models Compared

### Local Models (via Ollama)

| Key | Model | Type |
|---|---|---|
| rule_based | Regex parser | Baseline — no LLM |
| qwen_1_5b | qwen2.5-coder:1.5b | Main SLM candidate |
| qwen_3b | qwen2.5-coder:3b | Larger Qwen variant |
| phi_3_5 | phi3.5 | Stronger reasoning model |
| smollm_1_7b | smollm2:1.7b | Lightweight fast model |

### Cloud Models (via API)

| Key | Model | Provider |
|---|---|---|
| gemini_flash_lite | gemini-3.5-flash-lite | Google Gemini |
| gemini_flash_3_5 | gemini-3.5-flash | Google Gemini |
| gemini_3_6_flash | gemini-3.6-flash | Google Gemini |
| groq_gpt_oss_20b | openai/gpt-oss-20b | Groq |
| groq_gpt_oss_120b | openai/gpt-oss-120b | Groq |
| groq_qwen_3_8_27b | qwen/qwen3.8-27b | Groq |
| groq_allam_2_7b | allam-2-7b | Groq |
| nvidia_minimax_m3 | MiniMax-M3 | NVIDIA |
| nvidia_nemotron_3_5_lightning | Nemotron-3.5 Lightning | NVIDIA |
| nvidia_nemotron_3_super | Nemotron-3 Super | NVIDIA |
---

## Action Schema

Every model is asked to return a JSON array where each step follows this format:

```json
[
  { "action": "goto",          "target": "Login" },
  { "action": "type",          "target": "Email",    "value": "user@example.com" },
  { "action": "type",          "target": "Password", "value": "pass123" },
  { "action": "click",         "target": "Login" },
  { "action": "check_visible", "target": "Welcome" }
]
```

Allowed actions: `goto`, `click`, `type`, `check_visible`, `check_contains`

---

## Dataset

30 labeled test cases across 6 categories:

| Category | Count | Description |
|---|---|---|
| login | 5 | Login flow, wrong credentials, empty fields |
| users | 5 | User list, invite, delete, search |
| projects | 5 | Create, edit, delete projects |
| billing | 5 | Plan check, profile update, invoice |
| self_healing | 5 | Same intent written differently — tests robustness |
| ambiguous | 5 | Vague, messy, or incomplete instructions |

---

## Metrics

| Metric | Definition |
|---|---|
| JSON Validity | % of outputs that are parseable JSON |
| Step Accuracy | % of examples where all steps are fully correct |
| Action Accuracy | % of individual steps with correct action name |
| Target Accuracy | % of individual steps with correct target name |
| Hallucination Rate | % of outputs containing extra invented steps |
| Avg Latency | Average response time per instruction in seconds |

---

## Setup

### 1. Create and activate virtual environment

```bash
cd experiments/slm-parser
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
.venv\Scripts\activate           # Windows
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Pull local models via Ollama

```bash
ollama pull qwen2.5-coder:1.5b
ollama pull qwen2.5-coder:3b
ollama pull phi3.5
ollama pull smollm2:1.7b
```

### 4. Set up API keys for cloud models

Create a `.env` file in the `experiments/slm-parser/` directory:

```bash
GEMINI_API_KEY=your-gemini-key-here
GROQ_API_KEY=your-groq-key-here
NVIDIA_API_KEY=your-nvidia-key-here
```

Free API keys:
- Gemini: https://aistudio.google.com/app/apikey
- Groq: https://console.groq.com/keys
- NVIDIA: https://build.nvidia.com

### 5. Confirm Ollama is running

```bash
ollama list
```


---

## Running the Evaluation

### Run all enabled models

```bash
python run_evaluation.py
```

### Run only local SLMs

```bash
python run_evaluation.py --slm-only
```

### Run only cloud models

```bash
python run_evaluation.py --cloud-only
```

### Run a single model

```bash
# Local models
python run_evaluation.py --model rule_based
python run_evaluation.py --model qwen_1_5b
python run_evaluation.py --model qwen_3b
python run_evaluation.py --model phi_3_5
python run_evaluation.py --model smollm_1_7b

# Groq models
python run_evaluation.py --model groq_gpt_oss_20b
python run_evaluation.py --model groq_gpt_oss_120b
python run_evaluation.py --model groq_qwen_3_8_27b
python run_evaluation.py --model groq_allam_2_7b

# Gemini models
python run_evaluation.py --model gemini_flash_lite
python run_evaluation.py --model gemini_3_6_flash

# NVIDIA models
python run_evaluation.py --model nvidia_minimax_m3
python run_evaluation.py --model nvidia_nemotron_3_super
python run_evaluation.py --model nvidia_nemotron_3_5_lightning
```

### Enable or disable a model

- For local models: open `models/ollama_models.py` and set `enabled: True/False`
- For cloud models: open `models/llm_models.py` and set `enabled: True/False`

No other file needs to change.

### Add a new model

**Local model** — add to `models/ollama_models.py`:
```python
"qwen_7b": {
    "name":        "qwen2.5-coder:7b",
    "file_tag":    "Qwen2_5_Coder_7B",
    "description": "Qwen 2.5 Coder 7B",
    "enabled":     True
}
```

**Cloud model** — add to `models/llm_models.py`:
```python
"groq_new_model": {
    "name":        "model-name-on-groq",
    "provider":    "groq",
    "file_tag":    "Groq_New_Model",
    "description": "Description here",
    "enabled":     True
}
```
---

## Output Files

All result files are saved to `results/` (git-ignored).

| File | Contents |
|---|---|
| `{ModelTag}_results.json` | Per-example predictions, scores, latency |
| `{ModelTag}_summary.json` | Aggregated metrics for that model |
| `summary_all_models.json` | Combined — run without flags |
| `summary_slm_models.json` | Combined — run with --slm-only |
| `summary_cloud_models.json` | Combined — run with --cloud-only |
| `summary_{model_key}.json` | Combined — run with --model flag | 
---

## Notes

- The same prompt is used for every model — no per-model tuning
- Models run locally via Ollama — no internet needed for local models
- Cloud models require valid API keys in `.env`
- Output normalization handles minor formatting differences
  (markdown fences, double braces) but does not correct semantic errors
- Errors and wrong outputs are recorded as-is — they are research findings
- Gemini free tier has strict rate limits — add delays between calls
  if running the full 30-case dataset against Gemini models
- Some models (Groq Qwen 3.6 27B, NVIDIA Kimi K2) returned 0% due to
  format mismatch or API errors — check evaluation.md for details
- Model output can vary between runs on shared inference infrastructure
  (observed on Groq Qwen 3.8 27B) — rerun if results seem unexpectedly low