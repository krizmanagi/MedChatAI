"""Evaluate medical terminology recognition against a labeled test set.

Usage:
    python -m eval.evaluate                      # lexicon recognizer (default)
    python -m eval.evaluate --method all         # compare every method available
    python -m eval.evaluate --method llm         # GPT-4 extraction (needs credentials)
    python -m eval.evaluate --dataset eval/dataset.jsonl --out eval/results

Metrics (concept level, per question, micro-averaged):
    precision  = correct concepts found / all concepts found
    recall     = correct concepts found / all labeled concepts in the lexicon
    strict recall also counts labeled medical terms the lexicon has no entry
               for ("out_of_lexicon") as misses, so coverage gaps are visible.
    F1         = harmonic mean of precision and recall
    negation accuracy = share of correctly found concepts whose negated/affirmed
               status matches the label
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from medchat.chat import LLMTermExtractor  # noqa: E402
from medchat.config import get_settings  # noqa: E402
from medchat.llm import build_provider  # noqa: E402
from medchat.terminology import TerminologyRecognizer  # noqa: E402


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    oov: int = 0  # labeled terms outside the lexicon (always misses)
    neg_correct: int = 0
    neg_total: int = 0

    def add(self, other: "Counts") -> None:
        for k in self.__dataclass_fields__:
            setattr(self, k, getattr(self, k) + getattr(other, k))

    def metrics(self) -> dict:
        p = self.tp / (self.tp + self.fp) if self.tp + self.fp else 1.0
        r = self.tp / (self.tp + self.fn) if self.tp + self.fn else 1.0
        sr = self.tp / (self.tp + self.fn + self.oov) if self.tp + self.fn + self.oov else 1.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        return {
            "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4),
            "strict_recall": round(sr, 4),
            "negation_accuracy": round(self.neg_correct / self.neg_total, 4) if self.neg_total else None,
            "tp": self.tp, "fp": self.fp, "fn": self.fn, "out_of_lexicon": self.oov,
        }


@dataclass
class ExampleResult:
    id: str
    text: str
    expected: list[str]
    predicted: list[str]
    false_positives: list[str]
    false_negatives: list[str]
    negation_errors: list[str]
    out_of_lexicon: list[str]
    tags: list[str]
    counts: Counts = field(default_factory=Counts)


def load_dataset(path: Path) -> list[dict]:
    rows = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{i}: invalid JSON ({exc})")
    return rows


def predict_fn(method: str, recognizer: TerminologyRecognizer):
    """Return text -> {concept_id: negated} for the chosen method."""

    def collapse(matches) -> dict[str, bool]:
        out: dict[str, bool] = {}
        for m in matches:
            if m.concept_id is None:
                continue
            # a concept counts as negated only if every mention is negated
            out[m.concept_id] = out.get(m.concept_id, True) and m.negated
        return out

    if method == "lexicon":
        return lambda text: collapse(recognizer.recognize(text).matches)
    if method == "lexicon-exact":
        exact = TerminologyRecognizer(enable_fuzzy=False)
        return lambda text: collapse(exact.recognize(text).matches)

    settings = get_settings()
    provider = build_provider(settings)
    if provider.name == "mock":
        raise RuntimeError("LLM methods need Azure OpenAI or OpenAI credentials (see .env.example).")
    extractor = LLMTermExtractor(provider, recognizer)
    if method == "llm":
        return lambda text: collapse(extractor.extract(text))
    if method == "hybrid":
        def hybrid(text: str) -> dict[str, bool]:
            lex = collapse(recognizer.recognize(text).matches)
            llm = collapse(extractor.extract(text))
            merged = dict(llm)
            merged.update(lex)  # lexicon wins on negation status where both agree on a concept
            return merged
        return hybrid
    raise ValueError(f"unknown method {method}")


def evaluate(rows: list[dict], predict, recognizer: TerminologyRecognizer) -> tuple[Counts, list[ExampleResult]]:
    total = Counts()
    results = []
    for row in rows:
        expected = set(row["expected"])
        unknown = expected - set(recognizer.concepts)
        if unknown:
            raise SystemExit(f"{row['id']}: labels not in lexicon: {sorted(unknown)}")
        negated_gold = set(row.get("negated", []))
        pred = predict(row["text"])
        found = set(pred)

        c = Counts(
            tp=len(found & expected), fp=len(found - expected), fn=len(expected - found),
            oov=len(row.get("out_of_lexicon", [])),
        )
        neg_errors = []
        for cid in found & expected:
            c.neg_total += 1
            if pred[cid] == (cid in negated_gold):
                c.neg_correct += 1
            else:
                neg_errors.append(cid)
        total.add(c)
        results.append(ExampleResult(
            id=row["id"], text=row["text"], expected=sorted(expected), predicted=sorted(found),
            false_positives=sorted(found - expected), false_negatives=sorted(expected - found),
            negation_errors=neg_errors, out_of_lexicon=row.get("out_of_lexicon", []),
            tags=row.get("tags", []), counts=c,
        ))
    return total, results


def breakdown(results: list[ExampleResult], recognizer: TerminologyRecognizer) -> tuple[dict, dict]:
    by_tag: dict[str, Counts] = defaultdict(Counts)
    for r in results:
        for tag in r.tags:
            by_tag[tag].add(r.counts)

    by_cat: dict[str, Counts] = defaultdict(Counts)
    for r in results:
        for cid in set(r.expected) & set(r.predicted):
            by_cat[recognizer.get(cid).category].tp += 1
        for cid in r.false_negatives:
            by_cat[recognizer.get(cid).category].fn += 1
        for cid in r.false_positives:
            by_cat[recognizer.get(cid).category].fp += 1
    return ({k: v.metrics() for k, v in sorted(by_tag.items())},
            {k: v.metrics() for k, v in sorted(by_cat.items())})


def markdown_report(summary: dict) -> str:
    lines = [
        "# Terminology recognition evaluation",
        "",
        f"- Generated: {summary['generated_at']}",
        f"- Dataset: `{summary['dataset']}` ({summary['examples']} questions, {summary['labeled_concepts']} labeled concepts, "
        f"{summary['out_of_lexicon_terms']} labeled terms outside the lexicon)",
        f"- Lexicon: v{summary['lexicon_version']}, {summary['lexicon_concepts']} concepts",
        "",
        "## Overall",
        "",
        "| Method | Precision | Recall | F1 | Strict recall | Negation accuracy |",
        "|---|---|---|---|---|---|",
    ]
    for method, res in summary["methods"].items():
        m = res["overall"]
        neg = f"{m['negation_accuracy']:.1%}" if m["negation_accuracy"] is not None else "n/a"
        lines.append(f"| {method} | {m['precision']:.1%} | {m['recall']:.1%} | {m['f1']:.1%} | {m['strict_recall']:.1%} | {neg} |")

    for method, res in summary["methods"].items():
        lines += ["", f"## {method}: by entity category", "", "| Category | Precision | Recall | F1 | TP | FP | FN |", "|---|---|---|---|---|---|---|"]
        for cat, m in res["by_category"].items():
            lines.append(f"| {cat} | {m['precision']:.1%} | {m['recall']:.1%} | {m['f1']:.1%} | {m['tp']} | {m['fp']} | {m['fn']} |")
        lines += ["", f"## {method}: by question type", "", "| Tag | Precision | Recall | F1 |", "|---|---|---|---|"]
        for tag, m in res["by_tag"].items():
            lines.append(f"| {tag} | {m['precision']:.1%} | {m['recall']:.1%} | {m['f1']:.1%} |")
        errors = [e for e in res["examples"] if e["false_positives"] or e["false_negatives"] or e["negation_errors"]]
        lines += ["", f"## {method}: errors ({len(errors)} questions)", ""]
        for e in errors:
            parts = []
            if e["false_negatives"]:
                parts.append("missed " + ", ".join(e["false_negatives"]))
            if e["false_positives"]:
                parts.append("extra " + ", ".join(e["false_positives"]))
            if e["negation_errors"]:
                parts.append("negation wrong for " + ", ".join(e["negation_errors"]))
            lines.append(f"- **{e['id']}** \"{e['text']}\": {'; '.join(parts)}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default=str(ROOT / "eval" / "dataset.jsonl"))
    ap.add_argument("--method", default="lexicon", choices=["lexicon", "lexicon-exact", "llm", "hybrid", "all"])
    ap.add_argument("--out", default=str(ROOT / "eval" / "results"))
    args = ap.parse_args(argv)

    recognizer = TerminologyRecognizer()
    rows = load_dataset(Path(args.dataset))
    methods = ["lexicon-exact", "lexicon", "llm", "hybrid"] if args.method == "all" else [args.method]

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": Path(args.dataset).name,
        "examples": len(rows),
        "labeled_concepts": sum(len(r["expected"]) for r in rows),
        "out_of_lexicon_terms": sum(len(r.get("out_of_lexicon", [])) for r in rows),
        "lexicon_version": recognizer.version,
        "lexicon_concepts": len(recognizer.concepts),
        "methods": {},
    }

    for method in methods:
        try:
            predict = predict_fn(method, recognizer)
        except RuntimeError as exc:
            print(f"[skip] {method}: {exc}")
            continue
        total, results = evaluate(rows, predict, recognizer)
        by_tag, by_cat = breakdown(results, recognizer)
        summary["methods"][method] = {
            "overall": total.metrics(),
            "by_category": by_cat,
            "by_tag": by_tag,
            "examples": [{k: v for k, v in r.__dict__.items() if k != "counts"} for r in results],
        }
        m = total.metrics()
        neg = f"{m['negation_accuracy']:.1%}" if m["negation_accuracy"] is not None else "n/a"
        print(f"{method:14s} P={m['precision']:.1%}  R={m['recall']:.1%}  F1={m['f1']:.1%}  "
              f"strictR={m['strict_recall']:.1%}  neg={neg}  (tp={m['tp']} fp={m['fp']} fn={m['fn']} oov={m['out_of_lexicon']})")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out / "report.md").write_text(markdown_report(summary), encoding="utf-8")
    print(f"Wrote {out / 'report.md'} and {out / 'results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
