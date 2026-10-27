# First-order-line survival: audit

Prescriptions UTC [2026-08-15, 2026-10-15); uploads UTC [2026-08-01, 2026-10-26).

One observation per audited REFNUM 20 distinct order/order-line pair; all statuses and flags. Event is the earlier of actual/estimated upload and cancellation, including ties. The 0.96 upload estimate is treated as an event time. S(t) is the probability that neither upload nor cancellation has occurred by elapsed day t; it is not an upload-completion probability. Right censor missing or later events at 2026-10-26T00:00:00+00:00; an event exactly at cutoff is observed. Exclude missing creation, creation after cutoff and negative event durations from the curve; preserve them in line details. Zero durations are included. Kaplan–Meier uses events before censoring for equal durations and no extrapolation beyond follow-up. The shaded band is a pointwise 95% log-log Greenwood confidence interval conditional on supplied event times; it does not capture uncertainty from the 0.96 estimation rule. Independent right censoring is assumed. The PNG shows days 0–13 with vertical markers at days 3, 6, 10 and 11 and labeled horizontal guides for S(3), S(6) and S(10); the curve table retains full follow-up. For PNG rendering only, retain the first and last exact step in each horizontal output-pixel bin; the exported curve retains every step.

Source extracted 2026-10-27T20:49:05.973408+00:00; source SHA-256 fd732aa99c7c38471e4f15560fd7795f2417890686abcad25e3f27914637ac45. Estimator reference: https://www.statsmodels.org/stable/duration.html

| measure | count |
| --- | --- |
| Prescriptions | 104307 |
| Unmatched prescription associations | 9237 |
| Distinct matched lines | 95070 |
| Source negative durations (overlapping quality flag) | 280 |
| Included | 94790 |
| Negative event duration | 277 |
| Creation after cutoff | 3 |
| Event | 94770 |
| Excluded | 280 |
| Censored: missing event | 19 |
| Censored: event after cutoff | 1 |
| Included event source: actual_upload | 29340 |
| Included event source: estimated_upload | 63452 |
| Included event source: order_cancellation | 1978 |
| Included event source: tie | 0 |
| Included event source: missing | 0 |
