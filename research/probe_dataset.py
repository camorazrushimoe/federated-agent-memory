#!/usr/bin/env python3
"""Dataset acceptance probe for the Federated Agent Memory research commission.

Purpose: decide whether a corpus is FIT to be worked on. This script answers
"can this data support a question at all" — not "what is the answer".

Design note on padding detection
--------------------------------
Synthetic corpora are often inflated with random filler tokens. Per-token shape
heuristics (length, vowel ratio, character diversity) miss short filler and are
not reproducible across corpora. This script instead uses a **corpus-frequency**
definition, which is stable and cheap:

    a token is REAL if it occurs at least --real-min-count times in the sample
    everything else is treated as padding / one-off noise

Rationale: natural language reuses its vocabulary. Random padding does not.
On a genuine corpus most mass sits on recurring tokens; on a padded corpus the
token inventory explodes and `hapax_share` approaches 1.0.

`hapax_share` alone is the single most robust discriminator we found:
    Syncora/strova-ai  0.955   (padded)
    TWCS (TNE-AI)      0.56    (natural language)

Usage
-----
  python research/probe_dataset.py --cite-review

  python research/probe_dataset.py --kind syncora \
      --path customer_support_data.csv --sample-messages 20000

  python research/probe_dataset.py --kind twcs \
      --path twcs_conversations.parquet --sample 500

  python research/probe_dataset.py --kind abcd \
      --path abcd_v1.1.json --guidelines guidelines.json

Requires: pandas (csv/parquet). pyarrow for parquet. Nothing for ABCD json.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections import Counter
from pathlib import Path

_WORD = re.compile(r"[A-Za-z']+")

# Numbers quoted in docs/research-customer-support-dialogue-datasets.md.
# Each block records the exact command that regenerates it. --cite-review only
# PRINTS these; it does not compute anything. Run the command to verify.
REVIEW_CITATIONS = {
    "_meta": {
        "warning": "These are CITED constants, not a live computation. "
                   "Run the command in 'reproduce_with' to verify each block.",
    },
    "syncora_strova_ai": {
        "source": "first 31 MB slice of customer_support_data.csv",
        "reproduce_with": "probe_dataset.py --kind syncora --path customer_support_data.csv --sample-messages 20000",
        "verdict": "REJECT - padded text, sampled labels",
        "header": [
            "conv_id", "turn_index", "role", "text", "timestamp", "industry",
            "product", "issue_type", "language", "channel", "customer_name",
            "agent_name", "overall_sentiment", "overall_urgency", "outcome",
            "primary_intent",
        ],
        "conversation_ids_in_slice": 3431,
        "slice_note": "the 31 MB slice ends mid-conversation, so the last conversation id is partial; complete conversations = 3430",
        "turns_per_conv_median": 14,
        "turns_per_conv_range": [9, 18],
        "turns_per_conv_range_note": "min 9 is the truncated tail conversation; complete range is 10-18",
        "median_words_per_message": 68,
        "median_real_words_per_message": 8,
        "median_padding_share": 0.884,
        "hapax_share": 0.963,
        "real_vocabulary_size": 149,
        "outcome_counts_per_conversation": [704, 694, 689, 686, 658],
        "outcome_counts_note": "per CONVERSATION. Turn-level counts are ~14x larger; do not compare units.",
        "outcome_origin": "sampled (near-uniform over 5 values)",
        "labels_constant_within_conversation": True,
        "intent_x_issue_cells_populated": "14x15 = 210 / 210 (crossed at random)",
        "unique_customer_names": 3430,
        "unique_agent_names": 3419,
        "repeat_source_entities": False,
    },
    "twcs_tne_ai": {
        "source": "TNE-AI mirror, 500 conversations sampled as 100 rows at each of "
                  "5 offsets (0, 5000, 120000, 400000, 700000) via the HF rows API",
        "reproduce_with": "probe_dataset.py --kind twcs --path twcs_conversations.parquet "
                          "--offsets 0,5000,120000,400000,700000 --per-offset 100",
        "sampling_note": (
            "DO NOT use --sample 500: that reads the FIRST 500 rows, which is a "
            "different and biased sample and reproduces none of the figures below. "
            "Reported by lab-1 during Phase 0 - the earlier reproduce_with line was wrong."
        ),
        "verdict": "ACCEPT for research (license: non-commercial)",
        "n_conversations_full": 794335,
        "n_brands_full": 109,
        "median_real_words_per_turn": 18,
        "distinct_tokens_in_sample": 5836,
        "hapax_share": 0.56,
        "median_turns": 3,
        "max_turns": 48,
        "distinct_turn_patterns_per_500": 103,
        "repeat_brand_examples": {"AmazonHelp": 52, "AppleSupport": 36},
        "final_customer_turn_signal": {
            "clearly_positive": 0.11,
            "clearly_negative": 0.04,
            "no_signal": 0.85,
        },
        "outcome_origin": "organic-implicit; 85% of threads carry no explicit signal",
    },
    "abcd": {
        "source": "asappresearch/abcd data/abcd_v1.1.json.gz + guidelines.json + ontology.json",
        "reproduce_with": "probe_dataset.py --kind abcd --path abcd_v1.1.json --guidelines guidelines.json",
        "verdict": "ACCEPT - MIT, action ground truth present",
        "n_conversations": 10042,
        "splits": {"train": 8034, "dev": 1004, "test": 1004},
        "n_flows": 10,
        "conversations_per_flow_range": [713, 1094],
        "n_subflows_in_ontology": 55,
        "n_subflows_present_in_data": 96,
        "subflows_in_data_absent_from_ontology": 50,
        "subflows_in_ontology_absent_from_data": 9,
        "per_subflow_min": 3,
        "per_subflow_median": 69.5,
        "per_subflow_max": 361,
        "subflows_under_100_conversations": 54,
        "subflows_under_50_conversations": 36,
        "action_turns_total": 36482,
        "conversations_with_at_least_one_action": 1.0,
        "guidelines_subflows_documented": 55,
        "guidelines_name_join_matches": 32,
        "guidelines_conversation_coverage": 0.456,
        "guidelines_join_warning": (
            "guidelines.json uses Title Case names ('Initiate Refund'); the data uses "
            "snake_case ('return_color', 'boots_how_1'). Naive normalisation joins only "
            "32 names = 46% of conversations. A manual 96->55 mapping table is required "
            "before playbook scoring can cover the full corpus."
        ),
        "license": "MIT",
        "repeat_agent_identity": False,
    },
}


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD.finditer(text or "")]


def median(xs):
    if not xs:
        return 0
    ys = sorted(xs)
    mid = len(ys) // 2
    return ys[mid] if len(ys) % 2 else 0.5 * (ys[mid - 1] + ys[mid])


def text_stats(texts: list[str], real_min_count: int = 50) -> dict:
    """Corpus-frequency padding detection. See module docstring."""
    per_msg = [tokenize(t) for t in texts]
    counts = Counter(t for ws in per_msg for t in ws)
    real_vocab = {t for t, c in counts.items() if c >= real_min_count}

    totals = [len(ws) for ws in per_msg]
    reals = [sum(1 for w in ws if w in real_vocab) for ws in per_msg]
    shares = [
        1 - (r / t) for t, r in zip(totals, reals) if t
    ]
    hapax = sum(1 for c in counts.values() if c == 1)

    return {
        "n_messages": len(per_msg),
        "real_min_count": real_min_count,
        "median_words": median(totals),
        "median_real_words": median(reals),
        "median_padding_share": round(median(shares), 3),
        "distinct_tokens": len(counts),
        "hapax": hapax,
        "hapax_share": round(hapax / max(len(counts), 1), 3),
        "real_vocabulary_size": len(real_vocab),
        "_verdict_hint": (
            "PADDED - reject" if median(shares) > 0.5 or hapax / max(len(counts), 1) > 0.9
            else "natural language"
        ),
    }


def load_any(path: Path, sample: int | None):
    suffix = path.suffix.lower()
    if suffix == ".gz":
        with gzip.open(path, "rt") as f:
            return json.load(f)
    if suffix == ".json":
        with path.open() as f:
            return json.load(f)
    import pandas as pd

    if suffix == ".parquet":
        df = pd.read_parquet(path)
    elif suffix in {".csv", ".tsv"}:
        df = pd.read_csv(
            path,
            sep="\t" if suffix == ".tsv" else ",",
            engine="python",
            on_bad_lines="skip",
        )
    else:
        raise SystemExit(f"unsupported suffix: {suffix}")
    if sample:
        df = df.head(sample)
    return df


def take_offsets(df, offsets: list[int], per_offset: int):
    """Concatenate `per_offset` rows starting at each offset.

    A head(n) slice of TWCS is biased: the mirror is ordered, so the first rows
    over-represent a handful of brands. Spreading the sample is what the cited
    figures were measured on.
    """
    import pandas as pd

    chunks = []
    for off in offsets:
        if off >= len(df):
            print(f"warning: offset {off} beyond {len(df)} rows, skipped", file=sys.stderr)
            continue
        chunks.append(df.iloc[off:off + per_offset])
    if not chunks:
        raise SystemExit("no rows selected - check --offsets against the file length")
    return pd.concat(chunks, ignore_index=True)


def probe_syncora(df, sample_messages: int, real_min_count: int) -> dict:
    texts = df["text"].astype(str).tolist()[:sample_messages] if "text" in df.columns else []
    out = {
        "kind": "syncora",
        "columns": list(df.columns),
        "text": text_stats(texts, real_min_count),
    }
    if "conv_id" in df.columns:
        out["conversation_ids"] = int(df["conv_id"].nunique())
        tpc = df.groupby("conv_id").size()
        out["turns_per_conv"] = {
            "min": int(tpc.min()), "median": float(tpc.median()), "max": int(tpc.max()),
        }
    if "outcome" in df.columns and "conv_id" in df.columns:
        per_conv = df.groupby("conv_id")["outcome"].first().value_counts()
        out["outcome_counts_per_conversation"] = per_conv.to_dict()
        vals = list(per_conv.values)
        spread = (max(vals) - min(vals)) / max(sum(vals), 1)
        out["outcome_origin_hint"] = (
            "SAMPLED (near-uniform -> generator knob)" if spread < 0.05
            else "possibly derived - inspect"
        )
    for col in ("customer_name", "agent_name"):
        if col in df.columns:
            out[f"unique_{col}"] = int(df[col].nunique())
    if {"primary_intent", "issue_type"}.issubset(df.columns):
        import pandas as pd

        ct = pd.crosstab(df["primary_intent"], df["issue_type"])
        out["intent_x_issue"] = {
            "shape": list(ct.shape),
            "cells_populated": int((ct > 0).sum().sum()),
            "cells_total": int(ct.shape[0] * ct.shape[1]),
        }
    return out


def probe_twcs(df, real_min_count: int) -> dict:
    col = "conversation" if "conversation" in df.columns else "text"
    blobs = df[col].astype(str).tolist() if col in df.columns else []
    turn_re = re.compile(r"^(Customer|Support):\s*(.*)$")

    turns, patterns, turn_counts, last_customer = [], Counter(), [], []
    for blob in blobs:
        seq, cust = "", []
        for line in blob.split("\n"):
            m = turn_re.match(line.strip())
            if not m:
                continue
            role, body = m.group(1), m.group(2)
            seq += "C" if role == "Customer" else "S"
            turns.append(body)
            if role == "Customer":
                cust.append(body)
        if seq:
            patterns[seq] += 1
            turn_counts.append(len(seq))
        if cust:
            last_customer.append(cust[-1])

    pos = re.compile(r"\b(thank(s| you)|thx|appreciate|that worked|fixed|resolved|sorted|perfect|got it|awesome)\b", re.I)
    neg = re.compile(r"\b(still (not|isn'?t|no)|useless|terrible|worst|unacceptable|cancel(ling)? my|escalate|ridiculous|awful)\b", re.I)
    n = max(len(last_customer), 1)
    p = sum(1 for t in last_customer if pos.search(t))
    ng = sum(1 for t in last_customer if neg.search(t))

    out = {
        "kind": "twcs",
        "columns": list(df.columns),
        "n_rows_in_sample": len(df),
        "text": text_stats(turns, real_min_count),
        "median_turns": median(turn_counts),
        "max_turns": max(turn_counts) if turn_counts else 0,
        "distinct_turn_patterns": len(patterns),
        "top_turn_patterns": patterns.most_common(6),
        "turn_pattern_hint": (
            "TEMPLATED - reject" if len(patterns) < 0.2 * max(len(df), 1)
            else "varied structure - ok"
        ),
        "final_customer_turn_signal": {
            "clearly_positive": round(p / n, 3),
            "clearly_negative": round(ng / n, 3),
            "no_signal": round((n - p - ng) / n, 3),
        },
    }
    if "company" in df.columns:
        vc = df["company"].value_counts()
        out["n_companies"] = int(vc.size)
        out["companies_appearing_more_than_once"] = int((vc > 1).sum())
        out["top_companies"] = vc.head(6).to_dict()
        out["repeat_sources_hint"] = (
            "present -> can study source reputation" if (vc > 1).sum() > 5
            else "absent -> reputation/evidence-accumulation not testable"
        )
    return out


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def probe_abcd(obj, guidelines_path: Path | None,
               mapping_path: Path | None = None) -> dict:
    splits = {k: v for k, v in obj.items() if isinstance(v, list)} if isinstance(obj, dict) else {"all": obj}
    convos = [c for v in splits.values() for c in v]

    subflows, flows = Counter(), Counter()
    action_turns, with_action = 0, 0
    for c in convos:
        sc = c.get("scenario") or {}
        if sc.get("subflow"):
            subflows[sc["subflow"]] += 1
        if sc.get("flow"):
            flows[sc["flow"]] += 1
        k = sum(1 for t in (c.get("delexed") or []) if t.get("speaker") == "action")
        action_turns += k
        with_action += 1 if k else 0

    counts = sorted(subflows.values())
    out = {
        "kind": "abcd",
        "splits": {k: len(v) for k, v in splits.items()},
        "n_conversations": len(convos),
        "n_flows": len(flows),
        "conversations_per_flow": dict(flows),
        "n_subflows_present": len(subflows),
        "per_subflow": {
            "min": counts[0] if counts else None,
            "median": median(counts),
            "max": counts[-1] if counts else None,
            "under_100": sum(1 for x in counts if x < 100),
            "under_50": sum(1 for x in counts if x < 50),
        },
        "action_turns_total": action_turns,
        "conversations_with_at_least_one_action": round(with_action / max(len(convos), 1), 3),
        "power_hint": (
            "subflow level is UNDERPOWERED for success-vs-failure comparison; "
            "group by flow (see conversations_per_flow)"
            if counts and median(counts) < 150 else "subflow level may be workable"
        ),
    }

    if guidelines_path and guidelines_path.exists():
        g = json.loads(guidelines_path.read_text())
        documented = {}
        for flow, body in g.items():
            for name in (body.get("subflows") or {}):
                documented[name] = flow
        doc_norm = {_norm(k) for k in documented}
        matched = {k for k in subflows if _norm(k) in doc_norm}
        covered = sum(v for k, v in subflows.items() if k in matched)
        out["guidelines"] = {
            "flows_documented": len(g),
            "subflows_documented": len(documented),
            "naive_name_join_matches": len(matched),
            "conversation_coverage": round(covered / max(sum(subflows.values()), 1), 3),
            "unjoined_examples": sorted(set(subflows) - matched)[:10],
            "action_required": (
                "Build an explicit mapping table from the data's snake_case subflows to "
                "guidelines' Title Case names. Without it, playbook scoring covers only "
                "the joined subset."
            ),
        }

    if mapping_path and mapping_path.exists():
        m = json.loads(mapping_path.read_text())
        rows = {r["subflow"]: r for r in m.get("mapping", [])}
        mapped = {s for s, r in rows.items()
                  if r.get("guidelines_subflow") and s in subflows}
        uncovered = sorted(set(subflows) - mapped)
        covered = sum(v for k, v in subflows.items() if k in mapped)
        out["mapping"] = {
            "mapping_file": str(mapping_path),
            "mapped_subflows": len(mapped),
            "unmapped_subflows": uncovered,
            "conversation_coverage": round(covered / max(sum(subflows.values()), 1), 3),
            "note": (
                "Coverage using the explicit 96->55 mapping table "
                "(research/abcd_subflow_mapping.json). The 'guidelines' block "
                "above is the naive name join, kept for comparison."
            ),
        }
    return out


def main() -> int:
    p = argparse.ArgumentParser(
        description="Dataset acceptance probe (fitness, not findings).",
    )
    p.add_argument("--cite-review", action="store_true",
                   help="print cited constants from the docs (no computation)")
    p.add_argument("--kind", choices=["syncora", "twcs", "abcd"])
    p.add_argument("--path", type=Path)
    p.add_argument("--guidelines", type=Path, default=None,
                   help="ABCD only: path to guidelines.json for join coverage")
    p.add_argument("--mapping", type=Path, default=None,
                   help="ABCD only: path to the 96->55 subflow mapping JSON "
                        "(research/abcd_subflow_mapping.json); reports mapping coverage")
    p.add_argument("--sample", type=int, default=None,
                   help="rows to read (twcs: conversations)")
    p.add_argument("--offsets", type=str, default=None,
                   help="twcs: comma-separated row offsets to sample from, e.g. "
                        "0,5000,120000,400000,700000. Spreads the sample; a head() "
                        "slice of TWCS is biased toward a few brands.")
    p.add_argument("--per-offset", type=int, default=100,
                   help="twcs: rows to take at each --offsets position (default 100)")
    p.add_argument("--sample-messages", type=int, default=20000,
                   help="syncora: messages used for text stats")
    p.add_argument("--real-min-count", type=int, default=50,
                   help="token must occur >= N times in the sample to count as real")
    args = p.parse_args()

    if args.cite_review:
        print(json.dumps(REVIEW_CITATIONS, indent=2))
        return 0
    if not args.kind or not args.path:
        p.error("provide --kind and --path, or --cite-review")

    if args.kind == "twcs" and args.offsets:
        if args.sample:
            p.error("--offsets and --sample are mutually exclusive; --sample reads "
                    "the first N rows and does not reproduce the cited TWCS figures")
        data = take_offsets(
            load_any(args.path, None),
            [int(x) for x in args.offsets.split(",") if x.strip()],
            args.per_offset,
        )
    else:
        data = load_any(args.path, args.sample if args.kind != "syncora" else None)

    if args.kind == "syncora":
        res = probe_syncora(data, args.sample_messages, args.real_min_count)
    elif args.kind == "twcs":
        res = probe_twcs(data, args.real_min_count)
    else:
        res = probe_abcd(data, args.guidelines, args.mapping)

    print(json.dumps(res, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
