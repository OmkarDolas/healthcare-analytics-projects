"""Run the clinical-note extraction harness for one backend.

Examples:
    python -m src.run_extraction_eval --backend rules
    python -m src.run_extraction_eval --backend ollama --model llama3.1:8b          # local GPU
    python -m src.run_extraction_eval --backend openai --model gpt-4o-mini          # cloud
    python -m src.run_extraction_eval --backend openai --model meta-llama/Llama-3.1-8B-Instruct \\
        --base-url http://localhost:8000/v1                                         # vLLM server
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src.notes.dataset import build_eval_set
from src.notes.extractors import (LLMExtractor, OllamaClient, OpenAICompatibleClient,
                                  RuleBasedExtractor)
from src.notes.harness import error_examples, run_extractor, score

ROOT = Path(__file__).resolve().parents[1]


def make_extractor(args):
    if args.backend == "rules":
        return RuleBasedExtractor()
    if args.backend == "ollama":
        return LLMExtractor(OllamaClient(model=args.model), name=f"ollama:{args.model}")
    if args.backend == "openai":
        client = OpenAICompatibleClient(model=args.model, base_url=args.base_url)
        return LLMExtractor(client, name=f"openai-compatible:{args.model}")
    raise ValueError(args.backend)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backend", choices=["rules", "ollama", "openai"], default="rules")
    ap.add_argument("--model", default="llama3.1:8b")
    ap.add_argument("--base-url", default="https://api.openai.com/v1")
    ap.add_argument("--notes-dir", default=str(ROOT / "data" / "synthea" / "notes" / "notes"))
    ap.add_argument("--csv-dir", default=str(ROOT / "data" / "synthea" / "notes" / "csv"))
    ap.add_argument("--limit", type=int, default=None, help="Evaluate only the first N notes")
    args = ap.parse_args()

    cache = ROOT / "data" / "extraction_eval_set.parquet"
    if cache.exists():
        eval_set = pd.read_parquet(cache)
    else:
        eval_set = build_eval_set(Path(args.notes_dir), Path(args.csv_dir))
        eval_set.to_parquet(cache, index=False)
    if args.limit:
        eval_set = eval_set.head(args.limit)

    extractor = make_extractor(args)
    results = run_extractor(extractor, eval_set)
    scores = score(results, extractor.name)
    if hasattr(extractor, "stats"):
        for k, v in extractor.stats.items():
            scores["summary"][f"llm_{k}"] = v

    out = ROOT / "outputs" / "extraction" / extractor.name.replace(":", "_").replace("/", "_")
    out.mkdir(parents=True, exist_ok=True)
    for k, df in scores.items():
        df.to_csv(out / f"{k}.csv", index=False)
    pd.concat([error_examples(results, "conditions").assign(field="conditions"),
               error_examples(results, "medication_classes").assign(field="medication_classes")]
              ).to_csv(out / "error_examples.csv", index=False)
    print(scores["summary"].T.to_string(header=False))
    print(scores["labels"].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
