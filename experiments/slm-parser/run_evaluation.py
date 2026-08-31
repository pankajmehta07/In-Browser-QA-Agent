import json
import time
import os
import argparse
from colorama import Fore, Style, init


from models.ollama_models import (
    MODELS,
    call_model,
    get_enabled_models,
    get_file_tag,
    print_registry
)
from models.rule_based_parser import rule_based_parser

init(autoreset=True)


# ── Load Dataset ──────────────────────────────────────────────────

def load_dataset():
    path = os.path.join(os.path.dirname(__file__), "dataset/dataset.json")
    with open(path, "r") as f:
        return json.load(f)


# ── Score One Result ──────────────────────────────────────────────

def score(predicted: list, expected: list):
    total = len(expected)

    if not predicted:
        return {
            "fullyCorrect":   False,
            "actionAccuracy": 0.0,
            "targetAccuracy": 0.0,
            "valueAccuracy":  0.0,
            "hallucinated":   0
        }

    if not isinstance(predicted[0], dict):
        print(f"  ⚠️  Model returned wrong format — expected list of dicts")
        return {
            "fullyCorrect":   False,
            "actionAccuracy": 0.0,
            "targetAccuracy": 0.0,
            "valueAccuracy":  0.0,
            "hallucinated":   0
        }

    if total == 0:
        return {
            "fullyCorrect":   False,
            "actionAccuracy": 0.0,
            "targetAccuracy": 0.0,
            "valueAccuracy":  0.0,
            "hallucinated":   len(predicted)
        }

    correct_actions = 0
    correct_targets = 0
    correct_values  = 0
    value_total     = 0

    for i in range(min(len(predicted), total)):
        p = predicted[i]
        e = expected[i]

        # Action check
        p_action = (p.get("action") or "").strip()
        e_action = (e.get("action") or "").strip()
        if p_action == e_action:
            correct_actions += 1

        # Target check
        p_target = (p.get("target") or "").lower().strip()
        e_target = (e.get("target") or "").lower().strip()
        if p_target == e_target:
            correct_targets += 1

        # Value check
        if "value" in e:
            value_total += 1
            p_val = (p.get("value") or "").lower().strip()
            e_val = (e.get("value") or "").lower().strip()
            if p_val == e_val:
                correct_values += 1

    hallucinated  = max(0, len(predicted) - total)
    fully_correct = (
        correct_actions == total and
        correct_targets == total and
        len(predicted)  == total
    )

    return {
        "fullyCorrect":   fully_correct,
        "actionAccuracy": round(correct_actions / total, 2),
        "targetAccuracy": round(correct_targets / total, 2),
        "valueAccuracy":  round(correct_values / value_total, 2)
                          if value_total > 0 else 1.0,
        "hallucinated":   hallucinated
    }

# ── Run One Model Against Full Dataset ───────────────────────────

def run_model(model_key: str, dataset: list):
    file_tag = get_file_tag(model_key)
    print(f"\n{Fore.CYAN}🤖 Running: {model_key}  ({file_tag}){Style.RESET_ALL}")
    print("-" * 55)

    results   = []
    latencies = []

    for item in dataset:
        instruction = item["instruction"]
        expected    = item["expectedSteps"]

        # ── Get prediction ──────────────────────────────────────
        if model_key == "rule_based":
            start      = time.time()
            predicted  = rule_based_parser(instruction)
            latency    = round(time.time() - start, 4)
            valid      = True
            raw        = None
        else:
            valid, predicted, latency, raw = call_model(
                model_key, instruction
            )

        latencies.append(latency)

        # ── Score ───────────────────────────────────────────────
        if valid:
            scores = score(predicted, expected)
        else:
            scores = {
                "fullyCorrect":   False,
                "actionAccuracy": 0.0,
                "targetAccuracy": 0.0,
                "valueAccuracy":  0.0,
                "hallucinated":   0
            }

        # ── Print line ──────────────────────────────────────────
        status = (
            f"{Fore.GREEN}✅" if scores["fullyCorrect"]
            else f"{Fore.RED}❌"
        )
        print(
            f"  {status} {item['id']:<22} "
            f"valid={str(valid):<6} "
            f"act={scores['actionAccuracy']:.0%}  "
            f"tgt={scores['targetAccuracy']:.0%}  "
            f"{latency}s"
        )

        results.append({
            "id":           item["id"],
            "category":     item.get("category", ""),
            "instruction":  instruction,
            "expected":     expected,
            "predicted":    predicted,
            "validJSON":    valid,
            "latency":      latency,
            "raw_output":   raw,
            **scores
        })

    return results, latencies


# ── Summarize ─────────────────────────────────────────────────────

def summarize(results: list, latencies: list):
    total      = len(results)
    valid      = sum(1 for r in results if r["validJSON"])
    correct    = sum(1 for r in results if r["fullyCorrect"])
    hallucin   = sum(1 for r in results if r["hallucinated"] > 0)
    avg_action = sum(r["actionAccuracy"] for r in results) / total
    avg_target = sum(r["targetAccuracy"] for r in results) / total
    avg_lat    = sum(latencies) / len(latencies)

    # Per category breakdown
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "correct": 0}
        categories[cat]["total"]   += 1
        categories[cat]["correct"] += 1 if r["fullyCorrect"] else 0

    cat_accuracy = {
        cat: f"{v['correct']}/{v['total']}"
        for cat, v in categories.items()
    }

    return {
        "total":             total,
        "jsonValidity":      f"{valid / total:.0%}",
        "stepAccuracy":      f"{correct / total:.0%}",
        "actionAccuracy":    f"{avg_action:.0%}",
        "targetAccuracy":    f"{avg_target:.0%}",
        "hallucinationRate": f"{hallucin / total:.0%}",
        "avgLatency":        f"{avg_lat:.2f}s",
        "byCategory":        cat_accuracy
    }


# ── Save Results ──────────────────────────────────────────────────

def save_results(model_key: str, results: list, summary: dict):
    """
    Files saved as:
        Qwen2_5_Coder_1_5B_results.json
        Qwen2_5_Coder_1_5B_summary.json
    """
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)

    file_tag = get_file_tag(model_key)

    # Detailed per-example results
    results_path = os.path.join(
        results_dir, f"{file_tag}_results.json"
    )
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    # Summary metrics
    summary_path = os.path.join(
        results_dir, f"{file_tag}_summary.json"
    )
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"  💾 Saved → {file_tag}_results.json")
    print(f"  💾 Saved → {file_tag}_summary.json")


# ── Print Final Comparison Table ──────────────────────────────────

def print_table(all_summaries: dict):
    print(f"\n\n{Fore.YELLOW}{'='*90}")
    print("📊  EVALUATION SUMMARY")
    print(f"{'='*90}{Style.RESET_ALL}")

    print(
        f"{'Model':<25} {'JSON':>8} {'Steps':>8} "
        f"{'Actions':>9} {'Targets':>9} "
        f"{'Hallucin':>10} {'Latency':>10}"
    )
    print("-" * 90)

    for model_key, s in all_summaries.items():
        file_tag = get_file_tag(model_key)
        print(
            f"{file_tag:<25} "
            f"{s['jsonValidity']:>8} "
            f"{s['stepAccuracy']:>8} "
            f"{s['actionAccuracy']:>9} "
            f"{s['targetAccuracy']:>9} "
            f"{s['hallucinationRate']:>10} "
            f"{s['avgLatency']:>10}"
        )

    print(f"{'='*90}")

    # Per category breakdown
    print(f"\n{Fore.YELLOW}📂 Per Category Accuracy (fully correct steps / total){Style.RESET_ALL}")
    print("-" * 60)

    # Collect all categories
    all_cats = set()
    for s in all_summaries.values():
        all_cats.update(s["byCategory"].keys())

    for cat in sorted(all_cats):
        print(f"\n  {cat}:")
        for model_key, s in all_summaries.items():
            file_tag = get_file_tag(model_key)
            val = s["byCategory"].get(cat, "N/A")
            print(f"    {file_tag:<30} {val}")


# ── Argument Parser ───────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="SLM Parser Evaluation"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=(
            "Run a specific model by key. "
            "Options: rule_based, qwen_1_5b, qwen_3b, phi_3_5, smollm_1_7b. "
            "If not set, runs all enabled models."
        )
    )
    return parser.parse_args()


# ── Main ──────────────────────────────────────────────────────────

def main():
    args          = parse_args()
    dataset       = load_dataset()
    all_summaries = {}

    print(f"\n{Fore.YELLOW}🚀 SLM Parser Evaluation{Style.RESET_ALL}")
    print_registry()

    # Decide which models to run
    if args.model:
        # Single model mode
        if args.model not in MODELS:
            print(f"{Fore.RED}❌ Unknown model key: '{args.model}'")
            print(f"   Available keys: {', '.join(MODELS.keys())}{Style.RESET_ALL}")
            return

        if not MODELS[args.model]["enabled"]:
            print(f"{Fore.RED}❌ Model '{args.model}' is disabled.")
            print(f"   Set enabled=True in ollama_models.py to use it.{Style.RESET_ALL}")
            return

        to_run = [args.model]
        print(f"  Mode    : single model → {args.model}")
    else:
        # All enabled models
        to_run = get_enabled_models()
        print(f"  Mode    : all enabled models")

    print(f"  Dataset : {len(dataset)} test cases")
    print(f"  Running : {', '.join(to_run)}")

    for model_key in to_run:
        results, latencies       = run_model(model_key, dataset)
        summary                  = summarize(results, latencies)
        all_summaries[model_key] = summary
        save_results(model_key, results, summary)

    # Save combined summary
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    with open(os.path.join(results_dir, "all_summaries.json"), "w") as f:
        json.dump(all_summaries, f, indent=2)

    print_table(all_summaries)
    print(f"\n{Fore.GREEN}✅ Done. Results saved to results/{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()