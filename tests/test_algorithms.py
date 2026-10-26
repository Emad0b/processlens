import gzip
from pathlib import Path
import pytest
from processlens.io import timestamp, load_xes, load_csv
from processlens.core import (
    lifecycle_durations,
    case_summary,
    directly_follows,
    analyse,
)


def event(activity, time, lifecycle="complete", resource="worker"):
    return dict(
        activity=activity,
        time=float(time),
        lifecycle=lifecycle,
        resource=resource,
        position=0,
    )


def test_service_and_waiting_are_distinct():
    events = [
        event("W_task", 0, "schedule"),
        event("W_task", 3600, "start"),
        event("W_task", 5400),
    ]
    result = lifecycle_durations(events)
    assert result["waiting"] == [("W_task", 1.0)] and result["service"] == [
        ("W_task", 0.5)
    ]


def test_missing_resource_pairing_and_open_starts_are_reported():
    events = [
        event("W_task", 0, "start", None),
        event("W_task", 60),
        event("W_task", 120, "start"),
    ]
    result = lifecycle_durations(events)
    assert result["service"][0][1] == 1 / 60 and result["open_starts"] == 1


def test_concurrent_instances_report_ambiguity():
    r = lifecycle_durations(
        [event("W_task", 0, "start"), event("W_task", 1, "start"), event("W_task", 2)]
    )
    assert r["ambiguous_fifo_matches"] == 1


def test_handoff_count_excludes_unknown_resources():
    events = [
        event("A_SUBMITTED", 0, resource="a"),
        event("work", 1, resource=None),
        event("work2", 2, resource="b"),
    ]
    s = case_summary(events)
    assert s["handoffs"] == 0 and s["comparable_resource_transitions"] == 0


def test_censoring_and_precedence():
    assert not case_summary([event("A_SUBMITTED", 0), event("work", 60)])["resolved"]
    s = case_summary([event("A_SUBMITTED", 0), event("A_ACTIVATED", 30)])
    assert s["resolved"] and "A_ACTIVATED_WITHOUT_PRIOR_A_APPROVED" in s["violations"]


def test_tied_event_times_do_not_create_false_precedence_failure():
    s = case_summary(
        [event("A_SUBMITTED", 0), event("A_ACTIVATED", 30), event("A_APPROVED", 30)]
    )
    assert not s["violations"]


def test_directly_follows_uses_complete_events_only():
    edges = directly_follows(
        {"c": [event("A", 0), event("W", 10, "start"), event("B", 3600)]}
    )
    assert edges == {("A", "B"): [1.0]}


def test_temporal_reference_excludes_overlapping_cases():
    cases = {
        str(i): [event("A_SUBMITTED", i * 10000), event("A_DECLINED", i * 10000 + 100)]
        for i in range(10)
    }
    cases["crossing"] = [event("A_SUBMITTED", 1), event("A_DECLINED", 100000)]
    r = analyse(cases)
    assert (
        r["temporal"]["train_last_event"]
        < r["temporal"]["cutoff"]
        <= r["temporal"]["test_first_event"]
    )
    assert r["temporal"]["embargoed_overlapping_cases"] >= 1


def test_timezone_normalisation_and_naive_rejection():
    assert timestamp("2020-01-01T01:00:00+01:00") == timestamp("2020-01-01T00:00:00Z")
    with pytest.raises(ValueError):
        timestamp("2020-01-01T00:00:00")


def test_csv_loader_sorts_and_audits(tmp_path):
    p = tmp_path / "events.csv"
    p.write_text(
        "case_id,activity,timestamp\nc,B,2020-01-01T01:00:00Z\nc,A,2020-01-01T00:00:00Z\n"
    )
    cases, audit = load_csv(p)
    assert (
        cases["c"][0]["activity"] == "A"
        and audit["originally_out_of_order_traces"] == 1
    )


def test_xml_entity_declarations_rejected(tmp_path):
    p = tmp_path / "bad.xes"
    p.write_text('<!DOCTYPE x [<!ENTITY a "bad">]><log/>')
    with pytest.raises(ValueError):
        load_xes(p)


def test_minimal_xes_lifecycle_is_parsed(tmp_path):
    p = tmp_path / "sample.xes.gz"
    xml = '<log xmlns="http://www.xes-standard.org/"><trace><string key="concept:name" value="case1"/><event><string key="concept:name" value="A_SUBMITTED"/><date key="time:timestamp" value="2020-01-01T00:00:00Z"/><string key="lifecycle:transition" value="COMPLETE"/></event></trace></log>'
    with gzip.open(p, "wb") as f:
        f.write(xml.encode())
    cases, audit = load_xes(p)
    assert audit["events"] == 1 and cases["case1"][0]["lifecycle"] == "complete"


def test_generic_process_policy_and_lifecycle():
    events = [
        event("Open", 0),
        event("Review", 1, "start"),
        event("Review", 61),
        event("Closed", 121),
    ]
    s = case_summary(
        events,
        terminal_activities=["Closed"],
        precedence={"Closed": "Open"},
        expected_start="Open",
    )
    assert s["resolved"] and not s["violations"]
    assert lifecycle_durations(events)["service"] == [("Review", 1 / 60)]


def test_packaged_data_manifest_is_available():
    import importlib.resources, json

    source = json.loads(
        importlib.resources.files("processlens").joinpath("source.json").read_text()
    )
    assert len(source["sha256"]) == 64


def test_custom_policy_applies_to_full_analysis():
    cases = {
        str(i): [event("Open", i * 1000), event("Closed", i * 1000 + 10)]
        for i in range(10)
    }
    r = analyse(
        cases,
        terminal_activities=["Closed"],
        precedence={"Closed": "Open"},
        expected_start="Open",
    )
    assert r["illustrative_sla"]["resolved_cases"] == 10
    assert r["conformance"]["illustrative_precedence_violation_cases"] == 0
