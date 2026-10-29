"""Load the dataset, score recorded responses and build reports.

Usage:
    python -m aiqe.evaluate --build baseline
    python -m aiqe.evaluate --build candidate --compare reports/baseline.json

Exit code is 1 when any case fails unexpectedly, so the command can gate CI.
"""
import argparse
import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

from aiqe.checks import run_check

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_dataset():
    cases = load_json(DATA / "cases.json")
    kb = load_json(DATA / "knowledge_base.json")
    if cases["knowledge_base_version"] != kb["version"]:
        raise SystemExit(
            f"Dataset expects knowledge base {cases['knowledge_base_version']}, found {kb['version']}")
    docs = {d["id"]: d for d in kb["documents"]}
    return cases, kb, docs


def load_responses(build):
    return load_json(DATA / "responses" / f"{build}.json")["responses"]


def context_text(case, docs):
    return " ".join(docs[doc_id]["text"] for doc_id in case["context"])


def classify(case, checks_passed):
    """Turn raw check results into an outcome, accounting for documented limitations."""
    limitation = case.get("known_limitation")
    if limitation == "false_positive":
        return "known_false_positive" if not checks_passed else "pass"
    if limitation == "false_negative":
        return "known_false_negative" if checks_passed else "fail"
    return "pass" if checks_passed else "fail"


def evaluate_case(case, response, docs):
    ctx = context_text(case, docs)
    results = [run_check(spec, response, case, ctx) for spec in case["checks"]]
    passed = all(r.passed for r in results)
    return {
        "id": case["id"],
        "category": case["category"],
        "question": case["question"],
        "expected_behaviour": case["expected_behaviour"],
        "response": response,
        "outcome": classify(case, passed),
        "checks": [r.__dict__ for r in results],
    }


def evaluate(build):
    cases, kb, docs = load_dataset()
    responses = load_responses(build)
    missing = [c["id"] for c in cases["cases"] if c["id"] not in responses]
    if missing:
        raise SystemExit(f"No recorded response for: {missing}")
    results = [evaluate_case(c, responses[c["id"]], docs) for c in cases["cases"]]
    summary = OrderedDict()
    for r in results:
        s = summary.setdefault(r["category"], {"pass": 0, "fail": 0, "known_false_positive": 0, "known_false_negative": 0})
        s[r["outcome"]] += 1
    return {
        "build": build,
        "dataset_version": cases["version"],
        "knowledge_base_version": kb["version"],
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "totals": {k: sum(s[k] for s in summary.values()) for k in ("pass", "fail", "known_false_positive", "known_false_negative")},
        "by_category": summary,
        "results": results,
    }


def compare(current, previous):
    before = {r["id"]: r["outcome"] for r in previous["results"]}
    changes = []
    for r in current["results"]:
        old = before.get(r["id"])
        if old is None:
            changes.append((r["id"], "new case", r["outcome"]))
        elif old != r["outcome"]:
            kind = "regression" if (old == "pass" and r["outcome"] == "fail") else (
                "fixed" if (old == "fail" and r["outcome"] == "pass") else "changed")
            changes.append((r["id"], kind, f"{old} -> {r['outcome']}"))
    return changes


def to_markdown(report, changes=None, baseline_build=None):
    t = report["totals"]
    lines = [
        f"# Evaluation report: `{report['build']}` build",
        "",
        f"Dataset v{report['dataset_version']} · knowledge base v{report['knowledge_base_version']} · generated {report['generated_at']}",
        "",
        f"**{t['pass']} passed · {t['fail']} failed** · {t['known_false_positive']} known false positive · {t['known_false_negative']} known false negative",
        "",
        "| Category | Pass | Fail | Known FP | Known FN |",
        "|---|---|---|---|---|",
    ]
    for cat, s in report["by_category"].items():
        lines.append(f"| {cat} | {s['pass']} | {s['fail']} | {s['known_false_positive']} | {s['known_false_negative']} |")
    if changes is not None:
        lines += ["", f"## Changes compared with `{baseline_build}`", ""]
        if changes:
            lines += ["| Case | Change | Outcome |", "|---|---|---|"]
            lines += [f"| {cid} | {kind} | {detail} |" for cid, kind, detail in changes]
        else:
            lines.append("No outcome changes.")
    lines += ["", "## Case details", ""]
    for r in report["results"]:
        mark = {"pass": "PASS", "fail": "FAIL", "known_false_positive": "KNOWN FP", "known_false_negative": "KNOWN FN"}[r["outcome"]]
        lines += [
            f"### {r['id']} · {r['category']} · {mark}",
            f"- **Question:** {r['question']}",
            f"- **Expected:** {r['expected_behaviour']}",
            f"- **Response:** {r['response']}",
        ]
        lines += [f"- `{c['check']}`: {'pass' if c['passed'] else 'fail'}, {c['detail']}" for c in r["checks"]]
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--build", required=True, help="name of a file in data/responses/ without .json")
    parser.add_argument("--compare", help="earlier JSON report to diff against")
    parser.add_argument("--out", default=str(ROOT / "reports"))
    args = parser.parse_args(argv)

    report = evaluate(args.build)
    changes = baseline = None
    if args.compare:
        previous = load_json(args.compare)
        changes, baseline = compare(report, previous), previous["build"]
        report["changes_vs"] = {"build": baseline, "changes": changes}

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{args.build}.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (out / f"{args.build}.md").write_text(to_markdown(report, changes, baseline) + "\n", encoding="utf-8")

    t = report["totals"]
    print(f"{args.build}: {t['pass']} passed, {t['fail']} failed, "
          f"{t['known_false_positive']} known FP, {t['known_false_negative']} known FN")
    for r in report["results"]:
        if r["outcome"] == "fail":
            reasons = "; ".join(c["detail"] for c in r["checks"] if not c["passed"])
            print(f"  FAIL {r['id']} ({r['category']}): {reasons}")
    if changes:
        print(f"Changes vs {baseline}:")
        for cid, kind, detail in changes:
            print(f"  {cid}: {kind} ({detail})")
    return 1 if t["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
