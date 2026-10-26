import csv, gzip, hashlib, io
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamps must include an explicit timezone")
    return parsed.astimezone(timezone.utc).timestamp()


def load_xes(path, expected_sha256=None):
    path = Path(path)
    if (
        expected_sha256
        and hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256
    ):
        raise ValueError("Event-log fingerprint mismatch")
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as stream:
        raw = stream.read(200_000_001)
    if len(raw) > 200_000_000:
        raise ValueError("Expanded XML exceeds 200 MB limit")
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("DTD and entity declarations are not allowed")
    cases = {}
    audit = dict(events=0, missing_resource=0, originally_out_of_order_traces=0)
    for _, element in ET.iterparse(io.BytesIO(raw), events=["end"]):
        if element.tag.rsplit("}", 1)[-1] != "trace":
            continue
        attrs = {
            x.get("key"): x.get("value")
            for x in element
            if x.tag.rsplit("}", 1)[-1] != "event"
        }
        case = attrs.get("concept:name")
        if not case or case in cases:
            raise ValueError("Missing or duplicate case identifier")
        events = []
        for position, item in enumerate(element):
            if item.tag.rsplit("}", 1)[-1] != "event":
                continue
            values = {x.get("key"): x.get("value") for x in item}
            if not values.get("concept:name") or not values.get("time:timestamp"):
                raise ValueError("Missing activity or timestamp")
            event = dict(
                activity=values["concept:name"],
                time=timestamp(values["time:timestamp"]),
                lifecycle=values.get("lifecycle:transition", "complete").lower(),
                resource=values.get("org:resource"),
                position=position,
            )
            events.append(event)
            audit["events"] += 1
            audit["missing_resource"] += event["resource"] is None
        if not events:
            raise ValueError("Empty trace")
        audit["originally_out_of_order_traces"] += any(
            a["time"] > b["time"] for a, b in zip(events, events[1:])
        )
        cases[case] = sorted(events, key=lambda e: (e["time"], e["position"]))
        element.clear()
    return cases, audit


def load_csv(path):
    cases = {}
    audit = dict(events=0, missing_resource=0, originally_out_of_order_traces=0)
    with open(path, newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not {"case_id", "activity", "timestamp"} <= set(reader.fieldnames or []):
            raise ValueError("CSV needs case_id,activity,timestamp")
        for index, row in enumerate(reader):
            if not row["case_id"] or not row["activity"]:
                raise ValueError("Empty case or activity")
            event = dict(
                activity=row["activity"],
                time=timestamp(row["timestamp"]),
                lifecycle=(row.get("lifecycle") or "complete").lower(),
                resource=row.get("resource") or None,
                position=index,
            )
            cases.setdefault(row["case_id"], []).append(event)
            audit["events"] += 1
            audit["missing_resource"] += event["resource"] is None
    for case, events in cases.items():
        audit["originally_out_of_order_traces"] += any(
            a["time"] > b["time"] for a, b in zip(events, events[1:])
        )
        cases[case] = sorted(events, key=lambda e: (e["time"], e["position"]))
    return cases, audit
