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
│  └── rule_based_parser.py     ← regex baseline parser (Baseline A)
│  └── ollama_models.py         ← model registry, call functions, output parser
├──prompts
│  └── prompts.md               ← fixed prompt template used for all models
├── README.md        
├── requirements.txt            ← Python dependencies for this experiment only
├── run_evaluation.py           ← main evaluation runner
└── results/                    ← auto-generated result files (git-ignored)
```


---

## Models Compared

| Key | Model | Type |
|---|---|---|
| rule_based | Regex parser | Baseline — no LLM |
| qwen_1_5b | qwen2.5-coder:1.5b | Main SLM candidate |
| qwen_3b | qwen2.5-coder:3b | Larger Qwen variant |
| phi_3_5 | phi3.5 | Stronger reasoning model |
| smollm_1_7b | smollm2:1.7b | Lightweight fast model |

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

### 3. Pull models via Ollama

```bash
ollama pull qwen2.5-coder:1.5b
ollama pull qwen2.5-coder:3b
ollama pull phi3.5
ollama pull smollm2:1.7b
```

### 4. Confirm Ollama is running

```bash
ollama list
```

---

## Running the Evaluation

### Run all enabled models

```bash
python run_evaluation.py
```

### Run a single model

```bash
python run_evaluation.py --model rule_based
python run_evaluation.py --model qwen_1_5b
python run_evaluation.py --model qwen_3b
python run_evaluation.py --model phi_3_5
python run_evaluation.py --model smollm_1_7b
```

### Enable or disable a model

Open `models/ollama_models.py` and set `enabled: True` or `enabled: False`
for any model in the `MODELS` registry. No other file needs to change.

### Add a new model

Add one entry to the `MODELS` dict in `models/ollama_models.py`:

```python
"qwen_7b": {
    "name":        "qwen2.5-coder:7b",
    "file_tag":    "Qwen2_5_Coder_7B",
    "description": "Qwen 2.5 Coder 7B — largest Qwen variant",
    "enabled":     True
}
```

No other file needs to change.

---

## Output Files

All result files are saved to `results/` (git-ignored).

| File | Contents |
|---|---|
| `{ModelTag}_results.json` | Per-example predictions, scores, latency |
| `{ModelTag}_summary.json` | Aggregated metrics for that model |
| `all_summaries.json` | Combined summary across all models run |

Example filenames:

```
results/
├── rule_based_results.json
├── rule_based_summary.json
├── Qwen2_5_Coder_1_5B_results.json
├── Qwen2_5_Coder_1_5B_summary.json
├── Qwen2_5_Coder_3B_results.json
├── Qwen2_5_Coder_3B_summary.json
├── Phi3_5_Mini_results.json
├── Phi3_5_Mini_summary.json
├── SmolLM2_1_7B_results.json
├── SmolLM2_1_7B_summary.json
└── all_summaries.json
```


---

## Notes

- The same prompt is used for every model — no per-model tuning
- Models run locally via Ollama — no internet connection needed after setup
- Output normalization handles minor formatting differences
  (markdown fences, double braces) but does not correct semantic errors
- Errors and wrong outputs are recorded as-is — they are research findings