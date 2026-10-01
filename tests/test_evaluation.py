"""Guards the evaluation harness and prevents silent regressions in recognition quality."""

from pathlib import Path

from eval.evaluate import evaluate, load_dataset, predict_fn
from medchat.terminology import TerminologyRecognizer

ROOT = Path(__file__).resolve().parent.parent


def run(name):
    rec = TerminologyRecognizer()
    total, _ = evaluate(load_dataset(ROOT / "eval" / name), predict_fn("lexicon", rec), rec)
    return total.metrics()


def test_dev_set_quality_floor():
    m = run("dataset.jsonl")
    assert m["precision"] >= 0.95 and m["recall"] >= 0.93


def test_holdout_quality_floor():
    m = run("holdout.jsonl")
    assert m["precision"] >= 0.95 and m["recall"] >= 0.80


def test_metrics_math():
    from eval.evaluate import Counts
    m = Counts(tp=8, fp=2, fn=2).metrics()
    assert m["precision"] == 0.8 and m["recall"] == 0.8 and m["f1"] == 0.8
