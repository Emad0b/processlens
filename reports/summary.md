# ProcessLens real event-log analysis

13,087 cases; 262,200 raw events; 164,506 complete events.

- 4,336 distinct complete-event variants.
- 399 cases lack the configured terminal event; they are not counted as meeting the illustrative SLA.
- Temporal reference: 8,332 completed training traces; 3,926 later-starting test traces; 829 overlapping cases excluded from reference fitting.

Top test transitions by total observed elapsed gap:

- W_Nabellen offertes -> W_Nabellen offertes: 259707 total hours over 3209 transitions; median 50.97 hours.
- W_Completeren aanvraag -> W_Completeren aanvraag: 117155 total hours over 3919 transitions; median 6.50 hours.
- W_Completeren aanvraag -> W_Nabellen offertes: 75017 total hours over 1056 transitions; median 0.17 hours.
- W_Nabellen offertes -> O_SENT_BACK: 74810 total hours over 796 transitions; median 91.60 hours.
- W_Nabellen incomplete dossiers -> W_Nabellen incomplete dossiers: 34973 total hours over 2217 transitions; median 3.19 hours.

Elapsed gaps, matched service durations and schedule-to-start waits are reported separately. Handoff associations and rare paths are investigation leads, not causal explanations or compliance findings.
