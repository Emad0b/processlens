import argparse, csv, json
from pathlib import Path
from .io import load_xes, load_csv
from .core import analyse
from .provenance import capture

ROOT = Path.cwd()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path)
    p.add_argument("--output", type=Path, default=ROOT / "reports")
    p.add_argument("--sla-hours", type=float, default=168)
    p.add_argument(
        "--policy",
        type=Path,
        help="JSON terminal_activities, precedence and expected_start",
    )
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = json.loads(
        Path(__file__).with_name("source.json").read_text(encoding="utf-8")
    )
    path = args.input or ROOT / "data/raw" / source["filename"]
    cases, audit = (
        load_csv(path)
        if path.suffix.lower() == ".csv"
        else load_xes(path, None if args.input else source["sha256"])
    )
    policy = (
        json.loads(args.policy.read_text(encoding="utf-8"))
        if args.policy
        else (
            {"terminal_activities": [], "precedence": {}, "expected_start": None}
            if args.input
            else {}
        )
    )
    result = analyse(cases, args.sla_hours, **policy)
    result["policy_overrides"] = policy
    result["data_quality"] = audit
    (args.output / "results.json").write_text(
        json.dumps(result, indent=2, allow_nan=False)
    )
    with (args.output / "edge_diagnostics.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(result["edges"][0])
            if result["edges"]
            else [
                "source",
                "target",
                "count",
                "median_elapsed_hours",
                "p90_elapsed_hours",
                "total_elapsed_hours",
                "training_count",
                "rare_or_unseen",
            ],
        )
        writer.writeheader()
        writer.writerows(result["edges"])
    dot = ["digraph process {", "rankdir=LR;", "node [shape=box];"]
    for edge in result["edges"][:35]:
        a = json.dumps(edge["source"])
        b = json.dumps(edge["target"])
        label = f"n={edge['count']}, median={edge['median_elapsed_hours']:.1f}h"
        dot.append(f"{a} -> {b} [label={json.dumps(label)}];")
    (args.output / "process.dot").write_text("\n".join(dot + ["}"]))
    text = f"# ProcessLens real event-log analysis\n\n{result['cases']:,} cases; {audit['events']:,} raw events; {result['complete_events']:,} complete events.\n\n"
    text += f"- {result['distinct_variants']:,} distinct complete-event variants.\n- {result['illustrative_sla']['unresolved_or_censored']:,} cases lack the configured terminal event; they are not counted as meeting the illustrative SLA.\n- Temporal reference: {result['temporal']['training_cases']:,} completed training traces; {result['temporal']['test_cases']:,} later-starting test traces; {result['temporal']['embargoed_overlapping_cases']:,} overlapping cases excluded from reference fitting.\n"
    text += "\nTop test transitions by total observed elapsed gap:\n\n"
    for edge in result["edges"][:5]:
        text += f"- {edge['source']} -> {edge['target']}: {edge['total_elapsed_hours']:.0f} total hours over {edge['count']} transitions; median {edge['median_elapsed_hours']:.2f} hours.\n"
    text += "\nElapsed gaps, matched service durations and schedule-to-start waits are reported separately. Handoff associations and rare paths are investigation leads, not causal explanations or compliance findings.\n"
    (args.output / "summary.md").write_text(text, encoding="utf-8")
    if args.input:
        import hashlib

        source = dict(
            name="User-supplied local log",
            sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        )
    capture(args.output, source)
    print(text)


if __name__ == "__main__":
    main()
