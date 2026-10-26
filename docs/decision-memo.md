# ProcessLens investigation memo

The real event log contains 13,087 cases and 262,200 events. 399 cases do not reach the configured terminal events; they are not counted as meeting the illustrative SLA.

The largest aggregate elapsed-time concentration in test traces is **W_Nabellen offertes -> W_Nabellen offertes**, across 3,209 transitions. The median gap is 50.97 hours. Aggregated transition-hours are not the wall-clock duration of one process.

Investigate repeated offer follow-ups with process owners, considering customer response, path complexity and resource constraints. This is an investigation lead, not a causal explanation. Service intervals, schedule/start waits and complete-event gaps are deliberately separate. Matched intervals may overlap.

Lifecycle diagnostics retain 192 ambiguous FIFO matches and 10 open starts. Exact exclusive resource utilisation cannot be inferred. Handoff correlations are confounded by path length and case complexity. Rare paths and illustrative precedence checks are not compliance findings.

The temporal reference excludes 829 cases crossing its cutoff. Outcomes are retrospective; no operational intervention is evaluated.
