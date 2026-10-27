# First-order-line survival: risk-table

Prescriptions UTC [2026-08-15, 2026-10-15); uploads UTC [2026-08-01, 2026-10-26).

One observation per audited REFNUM 20 distinct order/order-line pair; all statuses and flags. Event is the earlier of actual/estimated upload and cancellation, including ties. The 0.96 upload estimate is treated as an event time. S(t) is the probability that neither upload nor cancellation has occurred by elapsed day t; it is not an upload-completion probability. Right censor missing or later events at 2026-10-26T00:00:00+00:00; an event exactly at cutoff is observed. Exclude missing creation, creation after cutoff and negative event durations from the curve; preserve them in line details. Zero durations are included. Kaplan–Meier uses events before censoring for equal durations and no extrapolation beyond follow-up. The shaded band is a pointwise 95% log-log Greenwood confidence interval conditional on supplied event times; it does not capture uncertainty from the 0.96 estimation rule. Independent right censoring is assumed. The PNG shows days 0–13 with vertical markers at days 3, 6, 10 and 11 and labeled horizontal guides for S(3), S(6) and S(10); the curve table retains full follow-up. For PNG rendering only, retain the first and last exact step in each horizontal output-pixel bin; the exported curve retains every step.

Source extracted 2026-10-27T20:49:05.973408+00:00; source SHA-256 fd732aa99c7c38471e4f15560fd7795f2417890686abcad25e3f27914637ac45. Estimator reference: https://www.statsmodels.org/stable/duration.html

| elapsed_days | at_risk | cumulative_events | cumulative_censored | survival_probability |
| --- | --- | --- | --- | --- |
| 0 | 94790 | 0 | 0 | 1.0 |
| 1 | 65327 | 29463 | 0 | 0.6891760734255885 |
| 3 | 50910 | 43880 | 0 | 0.5370819706722851 |
| 6 | 43741 | 51049 | 0 | 0.4614516299190569 |
| 10 | 26441 | 68349 | 0 | 0.27894292646917374 |
| 12 | 42 | 94747 | 1 | 0.0004529310405460531 |
| 20 | 17 | 94770 | 3 | 0.00020432979272754295 |
| 40 | 8 | 94770 | 12 | 0.00020432979272754295 |
| 60 | 4 | 94770 | 16 | 0.00020432979272754295 |
