# ProcessLens

ProcessLens turns time-stamped records into a map of how work actually moves through a process. Use it to see where loan applications wait, repeat steps, or take an unusual route.

Process mining over a real loan-application event log: discover observed paths, identify repeated work, examine elapsed-time concentrations and review deviations. Algorithms and reports are provided as a Python package and CLI.

## Implemented

- Bounded XES/XES.GZ parser and CSV event-log ingestion; timezone normalisation and input-quality checks.
- Complete-event process variants and directly-follows graphs (DFGs).
- Separate observed case spans, resolution times, matched service intervals and schedule-to-start waits.
- Resource-handoff counts that exclude missing-resource comparisons.
- Empirical conformance diagnostics plus illustrative precedence rules.
- Case-level temporal reference/test split with overlapping cases embargoed.
- Explicit unresolved/censored cases and an illustrative seven-day SLA.
- JSON metrics, edge diagnostics, a Graphviz DOT process map and an executive Markdown report.

## Run

Python 3.12 recommended. From this repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python -m processlens.fetch_data
python -m processlens.cli
python -m pytest -q
```

Use `source .venv/bin/activate` on macOS/Linux. The downloader checks the exact pinned SHA-256. The official download endpoint repeatedly timed out during development; the evaluated local copy came from a public mirror with the **same MD5 published by the dataset owner**, and its SHA-256 is pinned. Both URLs and checksums are recorded in [data/source.json](data/source.json). Raw logs are ignored by Git.

## Evidence

- [Analysis summary](reports/summary.md)
- [Complete findings](reports/results.json)
- [Transition diagnostics](reports/edge_diagnostics.csv)
- [Discovered graph](reports/process.dot)
- [Run provenance](reports/provenance.json)

Optionally render the process map with Graphviz: `dot -Tsvg reports/process.dot -o reports/process.svg`. No Graphviz installation is required for the Python analysis.

## Methodology

The BPI 2012 log interleaves application (`A_`), offer (`O_`) and work (`W_`) events. The main DFG and variants use COMPLETE events; START and SCHEDULE records are used separately for lifecycle intervals. Sorting is stable by UTC timestamp and source position; original out-of-order traces are counted. Equal timestamps are allowed and are not automatically causality evidence.

We distinguish three quantities:

1. **Observed elapsed gaps:** time between adjacent complete events. These can contain work, queuing, nights, weekends and parallel activity.
2. **Matched service intervals:** a compatible START followed by COMPLETE for a work activity.
3. **Matched waiting intervals:** a compatible SCHEDULE followed by START.

Without activity-instance IDs, repeated/concurrent activity matching uses compatible-resource FIFO. Missing resources can match known resources; ambiguous and unmatched pairs are explicitly counted. Summed intervals can overlap and must not be interpreted as exclusive case wall-clock time or resource utilisation.

The reference cutoff is the 70th percentile of case start times. Reference cases must finish before it; test cases must start on or after it. Cases crossing the boundary are excluded from reference discovery, avoiding future events leaking into the baseline. Edges seen fewer than five times in reference are marked rare/unseen in test. This is empirical path rarity, not Petri-net alignment fitness or a compliance certification.

For this loan log, terminal outcomes are A_ACTIVATED, A_DECLINED or A_CANCELLED. Resolution duration runs from the first complete event to the latest configured terminal event. Cases without one are unresolved/censored; they are not automatically marked as meeting the seven-day SLA. The SLA and precedence checks are illustrative analytical policies, not a bank's contractual controls.

Handoff/duration associations are descriptive among resolved cases. Repeated activity can be legitimate work. Neither a correlation nor a large elapsed gap proves the cause of a delay or the benefit of an intervention.

## Own event logs

CSV columns: `case_id,activity,timestamp`; optional `lifecycle,resource`. Timestamps must include a timezone. Lifecycle defaults to `complete` when absent. XES and gzip-compressed XES are also supported.

```powershell
python -m processlens.cli --input my_events.csv --policy docs/example-policy.json --output reports/custom
```

Configure terminal events, expected starting activity and precedence rules for the actual process before interpreting resolution/SLA or conformance findings. The bundled default is specific to the BPI loan process. Custom input without --policy uses no terminal or precedence assumptions and leaves resolution status unknown. The example policy is illustrative; replace it with a process-owner-approved definition. All analysis runs locally. Do not commit confidential input or reports.

## Validation and limits

Tests cover lifecycle intervals, missing resources, concurrent matching ambiguity, censoring, tied precedence timestamps, complete-event DFGs, temporal embargo, timezones, CSV ordering, XML entity rejection and XES parsing. The original log is not needed for CI. The workflow is included; hosted execution has not been claimed.

The benchmark is retrospective and reflects a single historical institution. It does not evaluate an operational intervention. Useful next work includes a stakeholder-approved normative model, activity-instance identifiers, business-calendar durations, incremental discovery and a controlled process change.

## Attribution and rights

Boudewijn van Dongen (2012), *BPI Challenge 2012*, Eindhoven University of Technology / 4TU.ResearchData. DOI: https://doi.org/10.4121/uuid:3926db30-f712-4394-aebc-75976070e91f . Publisher metadata: https://api.figshare.com/v2/articles/12689204 . The publisher lists **4TU General Terms of Use**. Consult the original record and applicable terms before reuse. This repository does not redistribute the raw log or resource/case identifiers. MIT applies to our code, not the source dataset.

## Verified result

15 tests passed. The benchmark analysed 13,087 applications and 262,200 events, retained 399 unresolved/censored cases, and excluded 829 overlapping cases from reference fitting.

[Decision memo](docs/decision-memo.md) explains the evidence and limits.

For the recorded Python 3.12 versions, run `pip install -r requirements-lock.txt` then `pip install -e . --no-deps`.
