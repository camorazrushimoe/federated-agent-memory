#!/usr/bin/env python3
"""Reproduce the dataset-acceptance metrics used in the research docs.

Every number quoted in docs/research-customer-support-dialogue-datasets.md
should be regenerable from this script *or* explicitly tagged as a cited
review measurement (see --cite-review).

Usage:
  python research/probe_dataset.py --cite-review
  python research/probe_dataset.py --kind twcs --path /data/twcs.parquet --sample 500
  python research/probe_dataset.py --kind syncora --path /data/customer_support_data.csv --sample 3430
  python research/probe_dataset.py --kind abcd --path /data/abcd_v1.1.json

Requires: pandas. Optional: pyarrow for parquet.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Filler heuristic used in the Syncora review: tokens that look like random
# lowercase padding (len>=6, no vowels-only-english shape is too brittle).
# We treat a token as "real" if it appears in a small English stoplist *or*
# contains a vowel and is not a long run of consonants.
_VOWEL = re.compile(r"[aeiouAEIOU]")
_WORD = re.compile(r"[A-Za-z']+")

REVIEW_CITATIONS = {
    "syncora": {
        "source": "PR #4 review measurements on first 31 MB / 3,430 complete conversations",
        "header": [
            "conv_id", "turn_index", "role", "text", "timestamp", "industry",
            "product", "issue_type", "language", "channel", "customer_name",
            "agent_name", "overall_sentiment", "overall_urgency", "outcome",
            "primary_intent",
        ],
        "n_conversations": 3430,
        "turns_per_conv_median": 14,
        "turns_per_conv_range": [10, 18],
        "median_words_per_message": 68,
        "median_real_words_per_message": 8,
        "median_filler_share": 0.88,
        "distinct_tokens": 1044426,
        "hapax_tokens": 1005883,
        "tokens_gt_50": 149,
        "outcome_counts": [704, 694, 689, 686, 657],
        "outcome_origin": "sampled",
        "labels_constant_within_conversation": True,
        "intent_x_issue_cells_populated": "14x15 = 210 / 210",
        "unique_customer_names": 3429,
        "unique_agent_names": 3429,
        "repeat_source_entities": False,
    },
    "twcs_tne_sample500": {
        "source": "PR #4 review, TNE-AI mirror, 500-conversation sample",
        "n_conversations_full": 794335,
        "n_brands": 109,
        "median_real_words_per_turn": 18,
        "distinct_tokens_in_sample": 5836,
        "hapax_share_sample": 0.56,
        "median_turns": 3,
        "max_turns": 48,
        "distinct_turn_patterns_per_500": 103,
        "repeat_brands_examples": {"AmazonHelp": 52, "AppleSupport": 36},
        "final_customer_turn_signal": {
            "clearly_positive": 0.11,
            "clearly_negative": 0.04,
            "no_signal": 0.85,
        },
        "outcome_origin": "organic-implicit (keyword/LLM judge required)",
    },
    "abcd": {
        "source": "PR #4 review + asappresearch/abcd ontology.json",
        "n_conversations": 10042,
        "n_flows": 10,
        "n_subflows": 55,
        "mean_conversations_per_subflow_if_uniform": 183,
        "actual_per_subflow_distribution": "UNKNOWN — run --kind abcd on the json",
        "outcome_origin": "action-derived vs guidelines.json (proposed; not a column)",
        "repeat_agent_identity": False,
        "license": "MIT",
        "download": "https://github.com/asappresearch/abcd/raw/master/data/abcd_v1.1.json.gz",
        "download_size_approx": "37 MB gz",
    },
}


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD.finditer(text or "")]


def is_likely_real(tok: str) -> bool:
    if len(tok) <= 2:
        return True
    if not _VOWEL.search(tok):
        return False
    # long random-looking consonant clusters with a stray vowel still fail length+entropy
    if len(tok) >= 10 and len(set(tok)) / len(tok) > 0.7:
        return False
    return True


def text_stats(texts: list[str]) -> dict:
    words_per = [tokenize(t) for t in texts]
    real_per = [[w for w in ws if is_likely_real(w)] for ws in words_per]
    all_toks = [w for ws in words_per for w in ws]
    counts = Counter(all_toks)
    n = len(words_per) or 1

    def median(xs):
        if not xs:
            return 0
        ys = sorted(xs)
        mid = len(ys) // 2
        return ys[mid] if len(ys) % 2 else 0.5 * (ys[mid - 1] + ys[mid])

    return {
        "n_messages": n,
        "median_words": median([len(ws) for ws in words_per]),
        "median_real_words": median([len(ws) for ws in real_per]),
        "median_filler_share": round(
            median(
                [
                    1 - (len(r) / len(w) if w else 0)
                    for w, r in zip(words_per, real_per)
                ]
            ),
            3,
        ),
        "distinct_tokens": len(counts),
        "hapax": sum(1 for c in counts.values() if c == 1),
        "hapax_share": round(sum(1 for c in counts.values() if c == 1) / max(len(counts), 1), 3),
        "tokens_gt_50": sum(1 for c in counts.values() if c > 50),
    }


def load_table(path: Path, sample: int | None):
    suffix = path.suffix.lower()
    if suffix in {".parquet"}:
        import pandas as pd

        df = pd.read_parquet(path)
    elif suffix in {".csv", ".tsv"}:
        import pandas as pd

        sep = "\t" if suffix == ".tsv" else ","
        df = pd.read_csv(path, sep=sep)
    elif suffix == ".json":
        with path.open() as f:
            return json.load(f)
    else:
        raise SystemExit(f"unsupported suffix: {suffix}")
    if sample and hasattr(df, "head"):
        df = df.head(sample)
    return df


def probe_syncora(df) -> dict:
    cols = list(df.columns)
    texts = df["text"].astype(str).tolist() if "text" in df.columns else []
    stats = text_stats(texts)
    out = {"kind": "syncora", "columns": cols, "text": stats}
    if "outcome" in df.columns:
        out["outcome_counts"] = df["outcome"].value_counts().to_dict()
    if "conv_id" in df.columns:
        out["n_conversations"] = int(df["conv_id"].nunique())
    return out


def probe_twcs(df) -> dict:
    cols = list(df.columns)
    text_col = "conversation" if "conversation" in df.columns else "text"
    texts = df[text_col].astype(str).tolist() if text_col in df.columns else []
    # split role-prefixed turns when present
    turns = []
    patterns = Counter()
    for blob in texts:
        parts = re.split(r"\n?(?=Customer:|Support:)", blob)
        roles = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            turns.append(re.sub(r"^(Customer|Support):\s*", "", p))
            roles.append("C" if p.startswith("Customer") else "S" if p.startswith("Support") else "?")
        if roles:
            patterns["-".join(roles)] += 1
    stats = text_stats(turns or texts)
    out = {
        "kind": "twcs",
        "columns": cols,
        "n_rows": len(df),
        "text": stats,
        "n_turn_patterns": len(patterns),
        "top_turn_patterns": patterns.most_common(8),
    }
    if "company" in df.columns:
        vc = df["company"].value_counts()
        out["n_companies"] = int(df["company"].nunique())
        out["top_companies"] = vc.head(8).to_dict()
        out["repeat_sources"] = int((vc > 1).sum())
    return out


def probe_abcd(obj) -> dict:
    splits = obj if isinstance(obj, dict) else {"all": obj}
    convos = []
    for v in splits.values():
        if isinstance(v, list):
            convos.extend(v)
    subflows = Counter()
    n_action_turns = 0
    for c in convos:
        meta = c.get("original") or c
        sf = None
        if isinstance(c, dict):
            sf = (
                c.get("subflow")
                or c.get("target")
                or (c.get("scenario") or {}).get("subflow")
                or (c.get("original") or {}).get("delexed", [{}])
            )
            if isinstance(sf, list):
                sf = None
            for t in c.get("delexed") or c.get("turns") or []:
                if isinstance(t, dict) and t.get("speaker") == "action":
                    n_action_turns += 1
        if isinstance(sf, str):
            subflows[sf] += 1
    return {
        "kind": "abcd",
        "n_conversations_loaded": len(convos),
        "n_subflows_seen": len(subflows),
        "subflow_counts_top": subflows.most_common(15),
        "min_per_subflow": min(subflows.values()) if subflows else None,
        "max_per_subflow": max(subflows.values()) if subflows else None,
        "n_action_turns": n_action_turns,
        "note": "schema varies slightly across dumps; inspect keys if counts look empty",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cite-review", action="store_true", help="print cited review numbers (no file)")
    p.add_argument("--kind", choices=["syncora", "twcs", "abcd"])
    p.add_argument("--path", type=Path)
    p.add_argument("--sample", type=int, default=None)
    args = p.parse_args()

    if args.cite_review:
        print(json.dumps(REVIEW_CITATIONS, indent=2))
        return 0
    if not args.kind or not args.path:
        p.error("provide --kind and --path, or --cite-review")
    data = load_table(args.path, args.sample)
    if args.kind == "syncora":
        print(json.dumps(probe_syncora(data), indent=2, default=str))
    elif args.kind == "twcs":
        print(json.dumps(probe_twcs(data), indent=2, default=str))
    else:
        print(json.dumps(probe_abcd(data), indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
