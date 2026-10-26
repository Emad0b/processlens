from collections import Counter, defaultdict
import numpy as np
from scipy.stats import spearmanr

TERMINAL = {"A_ACTIVATED", "A_DECLINED", "A_CANCELLED"}
# Illustrative hypotheses grounded in the documented application/offer stages.
PRECEDENCE = {
    "A_FINALIZED": "A_ACCEPTED",
    "A_ACTIVATED": "A_APPROVED",
    "O_SENT": "O_CREATED",
}


def complete(events):
    return [e for e in events if e["lifecycle"] == "complete"]


def lifecycle_durations(events):
    starts = defaultdict(list)
    schedules = defaultdict(list)
    service = []
    waiting = []
    unmatched_complete = unmatched_start = ambiguous = 0

    def take(queue, event):
        nonlocal ambiguous
        # Missing resource is not a separate real resource. Match compatible entries FIFO.
        compatible = [
            i
            for i, item in enumerate(queue)
            if item["time"] <= event["time"]
            and (
                not item["resource"]
                or not event["resource"]
                or item["resource"] == event["resource"]
            )
        ]
        if len(compatible) > 1:
            ambiguous += 1
        return queue.pop(compatible[0]) if compatible else None

    for event in events:
        activity = event["activity"]
        transition = event["lifecycle"]
        if transition == "schedule":
            schedules[activity].append(event)
        elif transition == "start":
            previous = take(schedules[activity], event)
            if previous:
                waiting.append((activity, (event["time"] - previous["time"]) / 3600))
            else:
                unmatched_start += 1
            starts[activity].append(event)
        elif transition == "complete" and (
            activity.startswith("W_") or activity in starts
        ):
            previous = take(starts[activity], event)
            if previous:
                service.append((activity, (event["time"] - previous["time"]) / 3600))
            else:
                unmatched_complete += 1
    return dict(
        service=service,
        waiting=waiting,
        unmatched_work_completions=unmatched_complete,
        starts_without_schedule=unmatched_start,
        open_starts=sum(map(len, starts.values())),
        open_schedules=sum(map(len, schedules.values())),
        ambiguous_fifo_matches=ambiguous,
    )


def case_summary(
    events, terminal_activities=None, precedence=None, expected_start="A_SUBMITTED"
):
    terminal_activities = (
        TERMINAL if terminal_activities is None else set(terminal_activities)
    )
    precedence = PRECEDENCE if precedence is None else precedence
    ordered = complete(events)
    if not ordered:
        raise ValueError("Trace has no complete events")
    activities = [e["activity"] for e in ordered]
    counts = Counter(activities)
    terminal = [e["time"] for e in ordered if e["activity"] in terminal_activities]
    handoffs = sum(
        bool(a["resource"] and b["resource"] and a["resource"] != b["resource"])
        for a, b in zip(ordered, ordered[1:])
    )
    comparable = sum(
        bool(a["resource"] and b["resource"]) for a, b in zip(ordered, ordered[1:])
    )
    first = {}
    for event in ordered:
        first[event["activity"]] = min(
            first.get(event["activity"], float("inf")), event["time"]
        )
    violations = []
    if expected_start is not None and activities[0] != expected_start:
        violations.append("DOES_NOT_START_WITH_" + expected_start)
    for later, earlier in precedence.items():
        if later in first and (earlier not in first or first[earlier] > first[later]):
            violations.append(f"{later}_WITHOUT_PRIOR_{earlier}")
    return dict(
        variant=tuple(activities),
        events=len(ordered),
        observed_hours=(ordered[-1]["time"] - ordered[0]["time"]) / 3600,
        resolved=bool(terminal),
        resolution_hours=(max(terminal) - ordered[0]["time"]) / 3600
        if terminal
        else None,
        repeated_activity_events=sum(max(n - 1, 0) for n in counts.values()),
        handoffs=handoffs,
        comparable_resource_transitions=comparable,
        violations=violations,
        start=events[0]["time"],
        end=events[-1]["time"],
    )


def directly_follows(cases):
    edges = defaultdict(list)
    for events in cases.values():
        selected = complete(events)
        for a, b in zip(selected, selected[1:]):
            edges[(a["activity"], b["activity"])].append((b["time"] - a["time"]) / 3600)
    return edges


def summarise_intervals(values):
    groups = defaultdict(list)
    for name, hours in values:
        groups[name].append(hours)
    return sorted(
        [
            dict(
                activity=name,
                count=len(hours),
                mean_hours=float(np.mean(hours)),
                median_hours=float(np.median(hours)),
                p90_hours=float(np.quantile(hours, 0.9)),
                total_hours=float(np.sum(hours)),
            )
            for name, hours in groups.items()
        ],
        key=lambda r: -r["total_hours"],
    )


def analyse(
    cases,
    sla_hours=168,
    terminal_activities=None,
    precedence=None,
    expected_start="A_SUBMITTED",
):
    terminal_activities = (
        TERMINAL if terminal_activities is None else set(terminal_activities)
    )
    precedence = PRECEDENCE if precedence is None else precedence
    if len(cases) < 3 or sla_hours <= 0:
        raise ValueError("Need >=3 cases and a positive illustrative SLA")
    summaries = {
        case: case_summary(events, terminal_activities, precedence, expected_start)
        for case, events in cases.items()
        if complete(events)
    }
    cutoff = float(np.quantile([s["start"] for s in summaries.values()], 0.70))
    train = {case: cases[case] for case, s in summaries.items() if s["end"] < cutoff}
    test = {case: cases[case] for case, s in summaries.items() if s["start"] >= cutoff}
    if not train or not test:
        raise ValueError("No nonoverlapping temporal training and test traces")
    reference = directly_follows(train)
    observed = directly_follows(test)
    min_support = 5
    rare = {edge for edge in observed if len(reference.get(edge, [])) < min_support}
    deviations = sum(
        any(
            (a["activity"], b["activity"]) in rare
            for a, b in zip(complete(events), complete(events)[1:])
        )
        for events in test.values()
    )
    variants = Counter(s["variant"] for s in summaries.values())
    resolved = [s for s in summaries.values() if s["resolved"]]
    sla_breaches = sum(s["resolution_hours"] > sla_hours for s in resolved)
    lifecycle = Counter()
    service = []
    waiting = []
    for events in cases.values():
        result = lifecycle_durations(events)
        service.extend(result.pop("service"))
        waiting.extend(result.pop("waiting"))
        lifecycle.update(result)
    edges = []
    for (source, target), hours in observed.items():
        edges.append(
            dict(
                source=source,
                target=target,
                count=len(hours),
                median_elapsed_hours=float(np.median(hours)),
                p90_elapsed_hours=float(np.quantile(hours, 0.9)),
                total_elapsed_hours=float(np.sum(hours)),
                training_count=len(reference.get((source, target), [])),
                rare_or_unseen=(source, target) in rare,
            )
        )
    edges.sort(key=lambda r: -r["total_elapsed_hours"])
    handoff_groups = []
    for name, condition in [
        ("0", lambda n: n == 0),
        ("1-5", lambda n: 1 <= n <= 5),
        ("6+", lambda n: n >= 6),
    ]:
        group = [s for s in resolved if condition(s["handoffs"])]
        handoff_groups.append(
            dict(
                handoffs=name,
                resolved_cases=len(group),
                median_resolution_hours=float(
                    np.median([s["resolution_hours"] for s in group])
                )
                if group
                else None,
            )
        )
    handoffs = [s["handoffs"] for s in resolved]
    durations = [s["resolution_hours"] for s in resolved]
    rho, p = (
        spearmanr(handoffs, durations)
        if len(set(handoffs)) > 1 and len(set(durations)) > 1
        else (None, None)
    )
    variant_rows = []
    for variant, count in variants.most_common(12):
        group = [
            s["observed_hours"] for s in summaries.values() if s["variant"] == variant
        ]
        variant_rows.append(
            dict(
                activities=list(variant),
                cases=count,
                median_observed_hours=float(np.median(group)),
            )
        )
    return dict(
        cases=len(cases),
        cases_with_complete_events=len(summaries),
        complete_events=sum(s["events"] for s in summaries.values()),
        distinct_variants=len(variants),
        top_variants=variant_rows,
        repeated_activity_case_rate=float(
            np.mean([s["repeated_activity_events"] > 0 for s in summaries.values()])
        ),
        illustrative_sla=dict(
            hours=sla_hours,
            resolved_cases=len(resolved),
            unresolved_or_censored=len(summaries) - len(resolved),
            breaches=sla_breaches,
            breach_rate=sla_breaches / len(resolved) if resolved else None,
            terminal_definitions=sorted(terminal_activities),
        ),
        temporal=dict(
            cutoff=cutoff,
            training_cases=len(train),
            test_cases=len(test),
            embargoed_overlapping_cases=len(summaries) - len(train) - len(test),
            train_last_event=max(summaries[c]["end"] for c in train),
            test_first_event=min(summaries[c]["start"] for c in test),
        ),
        conformance=dict(
            reference="Empirical directly-follows support, not a normative process model",
            training_min_edge_support=min_support,
            test_cases_with_rare_or_unseen_edges=deviations,
            test_case_deviation_rate=deviations / len(test),
            illustrative_precedence_violation_cases=sum(
                bool(s["violations"]) for s in summaries.values()
            ),
            rules=precedence,
        ),
        edges=edges,
        lifecycle_audit=dict(lifecycle),
        matched_service_intervals=summarise_intervals(service),
        matched_schedule_to_start_waits=summarise_intervals(waiting),
        handoff_groups=handoff_groups,
        handoff_duration_association=dict(
            spearman_r=float(rho) if rho is not None else None,
            p=float(p) if p is not None else None,
            interpretation="Descriptive association among resolved cases, not a causal effect of handoffs",
        ),
        limitations="Completion-to-completion gaps are elapsed time, not pure waiting. FIFO lifecycle pairing is approximate without activity-instance IDs. Repeated work can be legitimate; rare paths are not automatically violations. Observational data do not establish what intervention would reduce delay.",
    )
