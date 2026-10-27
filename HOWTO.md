# Setup

## Environment setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```sh
make init
```

Enter a project name and description, or press Enter to use
the repository folder name and the existing description (or
`Add your description here` when absent). Names must start
and end with a letter or digit and contain only letters, digits, `.`, `_`, or
`-`. Ctrl-C or end-of-input cancels without writing project configuration.

`make init` creates `.venv` with Python 3.12 (uv may download Python) and
synchronizes dependencies before prompting when configuration exists. It edits
only the project name and description, preserving dependencies, other settings,
and TOML formatting, then synchronizes again to refresh `uv.lock`. Explicitly
running `make init` again prompts again. Cancellation leaves `pyproject.toml`
unchanged; the preliminary synchronization may already have updated the
environment and lockfile.

For subsequent dependency synchronization, run `make setup`. It preserves
existing `pyproject.toml` without prompting. If configuration is absent, either
command prompts for metadata and generates it.
The initial runtime dependencies are defined in `scripts/setup.py`; the
development dependency group includes `pytest>=9.1.1` and `tomlkit>=0.13.3`.
After initialization, edit
`pyproject.toml` to change either list and rerun `make setup`.
An internet connection may be required to download Python and packages.
If dependency resolution fails, the requested constraints remain unchanged;
resolve the reported issue and rerun `make setup`.

Keep `pyproject.toml` and `uv.lock` in version control. Run Python commands
through `.venv/bin/python`.

To run the setup behavior checks after setup:

```sh
.venv/bin/python -m unittest discover -s tests
```

## Matt Pocock skills

With Node.js and npm (which provides `npx`) installed, run:

```sh
make setup-mattpocock-skills
```

This runs `npx skills@latest add mattpocock/skills` with flags to install all
skills for Codex without prompts, locally under `.agents/skills/`. It requires
internet access and does not depend on the Python environment. The CLI records
installed sources in `skills-lock.json`; keep that file and the installed skills
in version control. Rerunning the target fetches the latest upstream skills and
may overwrite local edits to those skills.

To uninstall this collection:

```sh
make uninstall-mattpocock-skills
```

This selects only entries whose source is `mattpocock/skills` in
`skills-lock.json`, then uses the CLI to remove their shared files and agent
links in this project and update the lockfile. Other skills and global
installations are preserved. Missing lockfiles or no
matching entries produce a successful no-op; invalid lockfiles report an error.
Node.js, npm, and internet access for `npx skills@latest` are required.
Uninstalling removes local edits to these skills. Run the setup target to
install them again.

See the [skills CLI reference](https://github.com/vercel-labs/skills/blob/main/docs/commands.md)
for installation options.

## Aged-order upload-to-cancellation distribution (REFNUM 5)

```bash
make create-aged-upload-cancellation-distribution
make create-aged-upload-cancellation-distribution START_DATE=2026-07-30 END_DATE=2026-10-21 CACHED=1
make create-aged-upload-cancellation-distribution PRINT_SQL=1
```

Defaults cover uploads July 30 through October 20, 2026 (UTC, end exclusive).
A fresh run extracts qualifying uploads and current order cancellation fields.
Each aged order contributes its earliest qualifying upload within the window;
multiple prescriptions do not multiply observations. Hours equal cancellation
minus upload, including negative values. No order-placement timestamp is required.
The UTC interpretation of ORDER_CANCEL_DTTM is checked against its Eastern
companion; contradictory evidence stops chart generation. Missing companions
are reported, and at least one paired eligible order is required for a nonempty
chart. Source metadata does not explicitly document this timezone convention.

SQL, Parquet and extraction provenance are saved in
`data/aged-upload-cancellation-distribution/<start>_<end>/`.
The transparent `distribution.png` goes under the matching directory in
`outputs/charts/aged-upload-cancellation-distribution/`; distribution,
quantile and order-detail Markdown tables use descriptive analysis-prefixed filenames under `outputs/tables/<start>_<last-day>/`.
Cached mode validates the SQL and renders without connecting. Quantiles use
linear interpolation. Missing upload timestamps cannot be assigned to the date
window; their source-wide count is reported separately, or unavailable for an
empty extract. Empty cohorts produce tables and no chart.

### Cancellation time stacked by latest prescription lifecycle state

```bash
make create-aged-cancellation-lifecycle-distribution
make create-aged-cancellation-lifecycle-distribution CACHED=1
make create-aged-cancellation-lifecycle-distribution PRINT_SQL=1
```

Run the cancellation distribution first. This target freezes its eligible orders,
selected uploads, durations and bin edges, and refreshes prescription associations
and latest `RXP_PRESCRIPTIONS.RX_LIFECYCLE_STATE`. It counts each order once:
identical states on its selected upload use that state; differing states use
`[Mixed states]`. Missing information stays explicit and can contribute to a mixed
group. This is the latest snapshot, not the state at cancellation.

Dates accept the same START_DATE/END_DATE options. Lifecycle SQL, extract and cohort
fingerprint live in the cancellation data directory's `lifecycle/` subdirectory.
The existing cancellation output directories receive `distribution-by-lifecycle-state.png`,
`distribution-by-lifecycle-state.md` and `orders-by-lifecycle-state.md`.
Cached rendering rejects changed cohort/query fingerprints. Duplicate upload or
prescription source records stop publication.

The lifecycle target also extracts current `STATE_CHANGE_REASON` and writes
`state-change-reasons.md` (order counts, percentages, exact reason combinations),
`orders-by-state-change-reason.md`, and `prescription-state-change-reasons.md`.
It preserves one count per order, grouping differing reasons as `[Mixed reasons]`.
NULL/blank reasons are grouped together; missing sources remain explicit.
These are latest prescription reasons, not historical reasons at cancellation.
Refresh without `CACHED=1` once when upgrading an older lifecycle extract.

## CMPU vet-diet prescription matches to upload events

Run the read-only summary query:

```bash
.venv/bin/python .agents/skills/rxp-sql/scripts/run_snowflake_query.py src/sql/cmpu_upload_event_matches.sql --output-parquet data/cmpu-upload-event-matches/2026-09-01_2026-09-16/summary.parquet --sql-log-dir data/cmpu-upload-event-matches/2026-09-01_2026-09-16/sql
```

Events are read from `EDLDB.SEGMENT.SEGMENT_HITS_PRODUCTS_UNION`.
The event filters come from the supplied `src/ignore/rxp` query, with its
undefined `c` reference removed. The query's `date_window` CTE sets both cohorts
to September 1–15, 2026, inclusive: start `2026-09-01`, exclusive end
`2026-09-16`. Events use `SESSION_DATE_EST`;
prescriptions use `RX_CREATION_DATETIME` without a timezone conversion.
Only `PRESCRIPTION_SOURCE = 'CMPU'` and `IS_VET_DIET_FLAG = TRUE` prescriptions
qualify. No status or deletion filters are added.

Match on customer and product IDs without timestamp ordering. Repeated events
cannot inflate the distinct-prescription count. The summary includes missing
keys, duplicate prescription IDs, and repeated customer/product pairs; those
pairs indicate association, not proof that an upload created a prescription.
The reviewed Markdown summary belongs under
`outputs/tables/2026-09-01_2026-09-15/cmpu-upload-event-matches_summary.md`.
The previous October rolling-window summaries use `outputs/tables/2026-10-09_onward/`.

### Match the prescription ID recorded in event properties

```bash
.venv/bin/python .agents/skills/rxp-sql/scripts/run_snowflake_query.py src/sql/cmpu_upload_prescription_id_matches.sql --output-parquet data/cmpu-upload-event-matches/2026-09-01_2026-09-16/prescription-id/matches.parquet --sql-log-dir data/cmpu-upload-event-matches/2026-09-01_2026-09-16/prescription-id/sql
.venv/bin/python -m src.python.summarize_cmpu_prescription_id_matches
```

Uses the same September dates and upload-event filters. Extracts
`properties:eventData:prescriptionId` and `properties:prescriptionId`, preferring
the nested value when both are filled. Blank/JSON-null IDs are missing;
conflicting values are audited. Joins the selected ID directly to `RX_ID`
without requiring event customer or product IDs. The full outer join retains
all cohort prescriptions and events for completeness checks and comparison
with the original customer/product association method.

The source extract and summary metadata are under the dated `prescription-id/`
data directory. Markdown summary and event-type field coverage are under
`outputs/tables/2026-09-01_2026-09-15/`.
Rerun only the summarizer to use the existing extract.

## Later canceled orders for September CMPU vet-diet prescriptions

```bash
.venv/bin/python .agents/skills/rxp-sql/scripts/run_snowflake_query.py src/sql/cmpu_later_cancelled_orders.sql --output-parquet data/cmpu-later-cancelled-orders/2026-09-01_2026-09-16/links.parquet --sql-log-dir data/cmpu-later-cancelled-orders/2026-09-01_2026-09-16/sql
.venv/bin/python -m src.python.summarize_cmpu_later_cancelled_orders
```

The cohort is CMPU vet-diet prescriptions created September 1–15, 2026,
inclusive. Links combine FIRST_ORDER_ID with all available prescription usage
action history, reduced to distinct prescription/order pairs. A qualifying
order was placed strictly after prescription creation and has latest status
Canceled. Orders and cancellations may occur after September 15. Cancellation
reasons are not filtered; missing reasons remain explicit. Cancellation
timestamps are checked against order placement, and order UTC/Eastern timestamp
companions must agree where available. RX_CREATION_DATETIME is interpreted as UTC.

Source SQL, Parquet and SHA-256 metadata are under
`data/cmpu-later-cancelled-orders/2026-09-01_2026-09-16/`.
Summary, cancellation-reason and qualifying-link Markdown tables are under
`outputs/tables/2026-09-01_2026-09-15/`.
Each prescription counts once in the headline; reason-specific prescription
counts may overlap. The summarizer reuses the cached extract without connecting.

### Actual prescription-item shipments

```bash
.venv/bin/python .agents/skills/rxp-sql/scripts/run_snowflake_query.py src/sql/cmpu_prescription_shipments.sql --output-parquet data/cmpu-later-cancelled-orders/2026-09-01_2026-09-16/shipments.parquet --sql-log-dir data/cmpu-later-cancelled-orders/2026-09-01_2026-09-16/sql
.venv/bin/python -m src.python.summarize_cmpu_prescription_shipments
```

Requires the cancellation analysis extract above. Uses a non-null
ORDER_LINE_SHIPPED_DTTM in ORDER_LINE_COST_MEASURES_RXP as shipment evidence,
joined directly by RX_ID. Counts distinct prescriptions, separating any shipped
order, shipped orders placed after prescription creation, the canceled-order
prescription subset, and shipping on the same canceled order. Current order
status alone is not used to determine shipping. Missing order-line coverage is
audited. The summary is `shipments.md` in the same table directory; source data
and SHA-256 metadata remain in the cancellation analysis data directory.

## First order to first-usage approval distributions

```bash
make cmpu-order-to-approval-distributions
make cmpu-order-to-approval-distributions START_DATE=2026-08-15 END_DATE=2026-10-15 UPLOAD_START_DATE=2026-08-01
make cmpu-order-to-approval-distributions CACHED=1
make cmpu-order-to-approval-distributions PRINT_SQL=1
.venv/bin/python -m pytest -q tests/test_cmpu_order_to_approval_distributions.py
```

Select CMPU vet-diet prescriptions with approval channel CUSTOMER_UPLOAD. Defaults
cover prescription creation August 15–October 14 and uploads August 1–October 14,
2026 (UTC, end date exclusive). Match DIET_PRESCRIPTION upload entities using
expanded RX_ID and numeric CUSTOMER_ID; repeated uploads cannot multiply rows.
Only FIRST_ORDER_ID is used. Require a matched order with known status other
than X and both timestamps; duration is FIRST_USAGE_APPROVED_DATETIME minus
ORDER_PLACED_DTTM in hours. There is no approval-date, prescription-status or
deletion filter. Negative values and the entire observed range are retained.
Order status reflects the extraction snapshot. Upload presence does not require
upload before approval and does not establish a causal effect.

Two stacked histograms use prescription counts, shared axes, and integer-aligned
one-hour intervals [lower, upper). A separate PNG table gives N, minimum, 25th,
median, 75th and 95th percentiles in hours, using unbinned linear interpolation.
Empty groups are labeled; an entirely empty eligible cohort produces no figures.

Outputs use `cmpu-order-to-approval-distributions/<start>_<exclusive-end>_uploads-from-<upload-start>/`
(the suffix is omitted when upload and prescription starts coincide):
- `data/`: prescription-level Parquet, executed SQL/history, extraction metadata,
  warehouse and SQL/Parquet fingerprints; cached mode requires unchanged inputs.
- `outputs/charts/`: transparent `distributions.png`, `statistics.png`, README.
- `outputs/tables/`: Markdown prescription details, one-hour bins, statistics,
  eligibility by upload group and upload-source audits. Eligibility exclusions
  are mutually exclusive; negative and over-24-hour durations are audit subsets.

The script rejects duplicate source keys and UTC/Eastern order timestamp
inconsistencies above one second. It checks missing Eastern companions separately.
Missing approval is excluded and never counted as a zero-hour approval.

## First-order-line timing distributions (REFNUM 16)

```bash
make cmpu-first-order-line-approval-distribution
make cmpu-first-order-line-approval-distribution WITH_UPLOAD=1
make cmpu-first-order-line-upload-distribution CACHED=1
make cmpu-upload-to-approval-distribution CACHED=1
make cmpu-upload-to-approval-distribution PRINT_SQL=1
```

Defaults select CMPU vet-diet CUSTOMER_UPLOAD prescriptions created August 15
through October 14, 2026 UTC. `START_DATE` is inclusive and `END_DATE=2026-10-15`
is exclusive. Upload-matched analyses search DIET_PRESCRIPTION upload entities
in `[UPLOAD_START_DATE, END_DATE + 11 days)`, defaulting to August 1 through
October 25 inclusive. Approval timestamps have no date limit. The overall
approval analysis does not require a matching upload.

Join the certified `ORDER_LINE_COST_MEASURES_RXP` view on both
`FIRST_ORDER_ID = ORDER_ID` and numeric `FIRST_ORDERITEM_ID = ORDER_LINE_ID`.
Count each distinct matched order/line pair once, requiring current
`ORDER_ORDER_LINE_STATUS = 'D'`. Collapse shipment rows using the latest populated
approval; conflicting statuses or creation timestamps reject the extract,
including missing/populated mixtures. UTC/Eastern creation companions must
agree within one second where populated. Missing companions are audited.

The three targets calculate hours as follows:

| Target | Timing difference | Negative durations |
| --- | --- | --- |
| `cmpu-first-order-line-approval-distribution` | Latest approval minus line creation | Retained |
| `cmpu-first-order-line-upload-distribution` | Earliest matching upload entity creation minus line creation | Excluded |
| `cmpu-upload-to-approval-distribution` | Latest approval minus earliest matching upload entity creation | Excluded |

Upload entities match by expanded RX_ID and numeric CUSTOMER_ID; the earliest
matching entity within the upload search window supplies the upload time.
Multiple uploads cannot multiply lines. Matching does not establish file
presence and need not precede approval or follow line creation. Both timing
endpoints are required; the upload-minus-line calculation does not require
approval. Excluded negatives remain in details and eligibility audits. Zero
and all nonnegative outliers are retained.

Every target produces a transparent Altair count histogram with integer-aligned
one-hour bins `[lower, upper)` and an exact empirical cumulative distribution
with labeled verticals at 24, 72, 144 and 240 hours. The full observed eligible
range is shown. Empty populations produce tables and remove stale figures.
Statistics use unbinned durations and linear interpolation: N, minimum, p25,
median, p75 and p95. Histogram and cumulative totals reconcile to eligible
unique lines. Missing keys, unmatched lines, status exclusions, missing timing
endpoints and upload-source identifier quality are audited at explicit grains.

Charts live directly in `outputs/charts/<start>_<last-prescription-day>/`, using
inclusive dates. For the default run this is `outputs/charts/2026-08-15_2026-10-14/`.
Filenames identify the measure, upload window, negative filter and figure type:

- `cmpu-d-lines_line-creation-to-upload_uploads-2026-08-01_2026-10-25_nonnegative_histogram.png`
- `cmpu-d-lines_line-creation-to-upload_uploads-2026-08-01_2026-10-25_nonnegative_cumulative.png`

Each analysis has matching Markdown notes, and the target prints their path.
Markdown associations, unique lines, eligibility, hourly counts, cumulative
counts/fractions and statistics go under `outputs/tables/<start>_<last-prescription-day>/`.
Descriptive filename prefixes distinguish measures, upload windows and filters.

SQL templates live in `src/sql/`: `cmpu_first_order_line_approval_distribution.sql`
and `cmpu_upload_to_max_approval_extract.sql`. Rendered queries and execution
history live under `src/autogenerated/cmpu-first-order-line-approval-distribution/`.
The complete dated query is named `cmpu_upload_to_max_approval_extract.sql` for
upload-matched extracts. SQL-only mode validates dates and prints SQL without
creating files. Fresh execution uses the read-only Snowflake runner with SSO.

Source Parquet, extraction metadata and SQL/Parquet SHA-256 fingerprints remain
under `data/cmpu-first-order-line-approval-distribution/`. Upload variants include
`_uploads-end-2026-10-26` in their identity to distinguish the extended window.
The three upload-matched measures share the same source extract. `CACHED=1`
verifies SQL, dates and the extract fingerprint without querying Snowflake.
`START_DATE`, exclusive `END_DATE` and `UPLOAD_START_DATE` are supported overrides.

The corrected cohort retains 104,307 prescriptions, of which 33,220 have uploads.
There are 24,944 D-status lines with uploads: the upload-to-approval analysis
includes 24,938 after six missing-approval exclusions (median about 49 seconds,
p75 4.77 hours, p95 25.07 hours). The upload-minus-line analysis includes 24,701
after excluding 243 negative durations (median 22.76 hours). Rendered figures
and notes using uploads only through October 14 were removed at user request;
underlying data, tables and source files remain available.

## Sankeys with the extended upload window

```bash
make cmpu-first-order-line-status
make cmpu-first-order-line-status CACHED=1
make cmpu-first-order-line-status PRINT_SQL=1
.venv/bin/python -m pytest -q tests/test_cmpu_first_order_line_status.py
```

This is the default CMPU first-order-line Sankey run (REFNUM 14/17).
`cmpu-prescription-first-order-status` remains an alias to this same extended run.
Override `START_DATE`, exclusive prescription `END_DATE`, and `UPLOAD_START_DATE`
as needed. Prescriptions use `[START_DATE, END_DATE)` and uploads use
`[UPLOAD_START_DATE, END_DATE + 11 days)`, all UTC. Defaults are prescriptions
August 15–October 14, 2026, and uploads August 1–October 25 inclusive
(exclusive ends October 15 and October 26). Upload start must not exceed
prescription start. No prescription-status, deletion or order-placement-date
filter is applied.

### Source, joins and counting

Use `src/sql/cmpu_first_order_line_status.sql` and the certified
`EDLDB.BT_HCA_HCDM.ORDER_LINE_COST_MEASURES_RXP` view. Join on both
**FIRST_ORDER_ID = ORDER_ID AND numeric FIRST_ORDERITEM_ID = ORDER_LINE_ID**;
there is no RX_ID join to the line view or dependency on ECOM.ORDERS.

Count each matched **(ORDER_ID, ORDER_LINE_ID) once**, collapsing shipment rows
before prescription associations. Multiple prescriptions sharing a line count
once. Missing first-order keys, invalid item IDs and unmatched lines are retained
in association details and audits, outside the Sankey denominator. Conflicting
shared-line channel/upload classifications, shipment statuses, cancellation
reasons or block reasons, and duplicate shipment/line source keys fail validation.

### Three views and their stages

The all-channel and CUSTOMER_UPLOAD views show **approval channel → first-order
cancel reason → line status → item block reason → matching upload**.
Cancellation reason is trimmed `ORDER_CANCEL_REASON`, with blank/null values
shown as `[No cancellation reason recorded]`; this does not imply an uncanceled
order. Line status uses raw `ORDER_ORDER_LINE_STATUS` codes (including C/D/R/S/X),
with blank/null codes shown as `[Unknown line status]`. This analysis has no
separate line-cancellation-reason field.

Actual `ORDER_ITEM_BLOCK_REASON` is shown only for known non-D statuses. D lines
use `[Not applicable: status D]`; unknown statuses use an explicit not-applicable
node. Blank/null actual reasons appear as `[No block reason recorded]`, which
alone does not establish an unblocked item. Block and upload nodes retain their
line-status identity so different statuses keep separate endpoints.

The third view contains only CUSTOMER_UPLOAD lines with a known non-D status,
including C/R/S/X rather than X alone. It omits the explicit line-status column:
**approval channel → cancel reason → item block reason → matching upload**.
Status labels remain on its separate block/upload paths. Column headings identify
the stages, and visible labels omit repeated prefixes; cancel reasons use purple
and item blocks light blue.

Every transition conserves that figure's distinct-line population. Full,
CUSTOMER_UPLOAD and non-D CUSTOMER_UPLOAD figures each use their own complete
population for node/flow percentages, rounded to two decimals, not the parent-node
or individual-status subtotal. Transition totals must not be added together.

### Matching upload entities

Match `DIET_PRESCRIPTION` entities on expanded RX_ID and numeric CUSTOMER_ID
within the extended upload window; deduplicate repeated uploads. No uploaded-file
or association-flag filter, or upload-after-prescription-creation requirement,
is applied. Matching entity presence does not independently verify a file.
Upload-source audits cover the entire search window.

### Outputs and reproducibility

Mermaid sources live directly in `src/diagrams/<start>_<last-prescription-day>/`,
with inclusive folder dates. Their descriptive basenames are
`cmpu-first-order-lines_<scope>_uploads-<upload-start>_<last-upload-day>_sankey`,
where scope is `all`, `customer-upload` or `non-d`. Transparent PNGs, titled SVGs
and companion notes use the same dated folder under `outputs/diagrams/`.
Titles and table notes show both prescription and upload ranges.

Dated `outputs/tables/` folders contain distributions/flows for all three views,
block-reason counts, association and line-detail previews, eligibility/source
audits and the order-vs-line-status comparison. Markdown exports obey the 1 MB
limit; complete source records remain in Parquet under
`data/cmpu-first-order-line-status/`. Cache identity includes prescription/upload
dates and the exclusive upload end, plus SQL/data fingerprints. Rendered SQL and
execution history use `src/autogenerated/cmpu-first-order-line-status/`.
Generated data, Mermaid sources and figures remain ignored by Git.

`CACHED=1` verifies the source and regenerates outputs without querying Snowflake.
`PRINT_SQL=1` validates dates and prints SQL without creating files. Fresh runs
use the read-only rxp-sql runner with browser SSO. Both Make names above select
this extended window automatically; no shorter-window flag is needed.

The existing extended-window extract contains 113,608 prescriptions and 103,514
matched unique lines, including 95,071 CUSTOMER_UPLOAD lines. Its 24,944
CUSTOMER_UPLOAD D-status lines with uploads reconcile to the timing analysis
before missing-approval exclusions. Historical shorter-window source extracts
remain available; their superseded diagrams and Markdown exports are removed.

## Upload time as a share of approval time (REFNUM 18)

```bash
make cmpu-upload-time-ratio-distribution CACHED=1
make cmpu-upload-time-ratio-distribution PRINT_SQL=1
# Optional fresh read-only extraction using the shared timing source:
make cmpu-upload-time-ratio-distribution
```

For CMPU vet-diet CUSTOMER_UPLOAD D-status first-order lines, compute
`(earliest matching upload entity creation − line creation) /
(latest populated approval − line creation)`. A ratio of 0.75 is 75%: upload
occurred three-quarters of the way from line creation to approval. Use the
established two-key first-order-line join, shipment collapse, upload matching,
source audits and UTC/Eastern checks. Each distinct order/line pair counts once.

Defaults select prescriptions in `[2026-08-15, 2026-10-15)` UTC and upload
entities in `[2026-08-01, 2026-10-26)` UTC. Override with `START_DATE`, exclusive
`END_DATE` and `UPLOAD_START_DATE`; uploads end 11 days after `END_DATE`. Approval
timestamps have no date limit. All three timestamps are required. Exclude
negative upload-minus-line durations and zero/negative approval-minus-line
durations, retaining excluded rows and separate reasons in details/audits. Keep
zero ratios, ratios above one and all outliers; do not cap the ratio at 100%.

The target shares SQL/extraction/fingerprint validation with REFNUM 16 and
reuses its upload-matched cache with `CACHED=1`. No duplicate extract or new SQL
template is created. SQL templates remain under `src/sql`, rendered queries
and execution history under `src/autogenerated`, and the shared source
Parquet/metadata under `data/cmpu-first-order-line-approval-distribution/`.
`PRINT_SQL=1` prints the source SQL without creating files or querying Snowflake.

Transparent histogram and exact empirical CDF PNGs live directly in
`outputs/charts/2026-08-15_2026-10-14/`. Both use percentage-formatted ratio axes,
both date windows and eligible N; the CDF also uses a percentage y axis.
Histogram bins have width 0.01 (one percentage point), are `[lower, upper)`,
and use exact integer timestamp differences to assign boundaries. A ratio of
1 starts the `[1, 1.01)` bin. Empty bins are omitted from the bin table and
have zero count. Charts show the full observed range, with no hour-reference
verticals. Filenames begin
`cmpu-d-lines_upload-time-share_uploads-2026-08-01_2026-10-25_nonnegative`
and end in `_histogram.png`, `_cumulative.png` or `.md` for companion notes. Table filenames use the same prefix followed by the table kind.
The target prints the notes path. Empty populations remove only their own
stale figures and still produce details/audits/tables.

Markdown association/line details, eligibility audits, ratio bins, cumulative
counts/fractions and unbinned N/mean/minimum/p25/median/p75/p95/maximum statistics
are under `outputs/tables/<start>_<last-prescription-day>/`.
Ratios in tables are dimensionless (multiply by 100 for percent). Details
include all timestamps, upload/approval durations in hours, ratio and eligibility.
An `analysis.json` under `data/cmpu-upload-time-ratio-distribution/<source-period>/`
records the formula, exclusions, bin width, dates, source path/fingerprints,
extraction/generation timestamps and eligible count without copying source data.

The validated cached run has 24,695 eligible lines after six missing approvals
and 243 negative upload durations. No zero/negative approval durations occur.
The median ratio is 0.992258 (99.23%); p25 is 68.62%, p75 99.97% and p95 99.99%.
No eligible ratios exceed one in this snapshot.

The REFNUM 18 target also plots the two elapsed times and fits a line using
exactly the same eligible unique lines. The scatter x axis is line creation
to latest approval in hours; the y axis is line creation to earliest matching
upload in hours. All points and outliers are retained. Unweighted ordinary
least squares estimates an intercept and slope; the line is shown over the
observed x range. The equation, R² and N appear on the figure and in
`linear-fit.md` alongside the other ratio tables. A negative fitted intercept
is allowed; this is an unconstrained descriptive fit between intervals sharing
a start time. Fewer than two points or constant x values produce a scatter
without a regression; R² is undefined for constant y values.

The scatter is named
`cmpu-d-lines_upload-vs-approval-times_uploads-2026-08-01_2026-10-25_nonnegative_linear-fit.png`
in the same flat chart folder. The cached cohort gives
`upload_hours = -3.072068 + 0.960573 × approval_hours`, R²=0.952879, N=24,695.
Regenerate with `make cmpu-upload-time-ratio-distribution CACHED=1`.

The same target also fits natural logs of both elapsed times and saves a
log–log scatter as
`cmpu-d-lines_upload-vs-approval-times_uploads-2026-08-01_2026-10-25_nonnegative_log-log-fit.png`.
The axes show hours on logarithmic scales. Fit
`ln(upload_hours) = intercept_log_hours + slope × ln(approval_hours)`
with unweighted OLS and an intercept. The equivalent curve is
`upload_hours = exp(intercept_log_hours) × approval_hours^slope`; it is the
direct back-transformation of the log-space fit, without a mean-response bias
correction. R² is computed in log space. Only strictly positive time pairs
from the ratio-eligible cohort enter this fit; no pseudocount is added.
Zero/nonpositive exclusions and the fit N are exported in `log-log-fit.md`.
Zero-ratio observations still belong to the original ratio and linear analyses.
The cached snapshot has no additional log exclusions: N=24,695, log slope
1.028342, log intercept -0.774953, power multiplier 0.460725, R²(log)=0.741830.
Both original and log–log fit figures are linked from the chart notes and
regenerate with `make cmpu-upload-time-ratio-distribution CACHED=1`.

## Flat date-based table layout

All generated Markdown tables live directly in `outputs/tables/<start>_<last-day>/`,
using inclusive dates and no analysis/variant subdirectories. Analysis names,
upload windows, filters and table kinds are part of the filename, preventing
collisions when multiple analyses share a date folder. All existing 207 tables
were moved without changing their contents. Empty old directories were removed.

For the current ratio analysis, use `outputs/tables/2026-08-15_2026-10-14/`:

- `cmpu-d-lines_upload-time-share_uploads-2026-08-01_2026-10-25_nonnegative_statistics.md`
- `cmpu-d-lines_upload-time-share_uploads-2026-08-01_2026-10-25_nonnegative_order-lines.md`
- `cmpu-d-lines_upload-vs-approval-times_uploads-2026-08-01_2026-10-25_nonnegative_linear-fit.md`
- `cmpu-d-lines_upload-vs-approval-times_uploads-2026-08-01_2026-10-25_nonnegative_log-log-fit.md`

Timing table prefixes match their corresponding chart prefixes. Other analyses
use `<analysis>_<run-variant>_<table-kind>.md`; run variants preserve independent
upload dates and Sankey status/block-reason variants. Lifecycle and cancellation
commands sharing a date folder use distinct table kinds. Existing explicit
`--output-dir` overrides on the September summary commands remain supported.
Data/cache, SQL, chart and diagram locations are unchanged. Updated commands
write tables directly to this layout; the timing and ratio targets print the
folder after running.

Two older rolling-window event-match summaries had a documented October 9
lower bound with no upper-bound filter. They use `2026-10-09_onward/` rather
than implying a bounded cohort, with `snapshot-2026-10-23` in their filenames.
Other folders use the source window's inclusive end (exclusive end minus one
day). Historical October 14-upload tables remain available as data; their
previously removed figures/companion chart notes are not recreated.

## First-order-line event-time dataset (REFNUM 20)

```bash
make cmpu-first-order-line-event-times
make cmpu-first-order-line-event-times CACHED=1
make cmpu-first-order-line-event-times PRINT_SQL=1
make cmpu-first-order-line-event-times START_DATE=2026-08-15 END_DATE=2026-10-15 UPLOAD_START_DATE=2026-08-01
```

`END_DATE` is exclusive. Defaults select CMPU vet-diet CUSTOMER_UPLOAD
prescriptions August 15–October 14, 2026 UTC, and search DIET_PRESCRIPTION
upload entities August 1–October 25 inclusive (exclusive end = `END_DATE + 11 days`).
Expanded RX_ID and numeric customer ID must both match. All first-order-line
statuses and nullable IS_DELETED/IS_REFILL flags remain; this command assigns
no survival outcomes or censoring rules.

The complete calculation is in `src/sql/cmpu_first_order_line_event_times.sql`.
It joins both FIRST_ORDER_ID and numeric FIRST_ORDERITEM_ID, collapses shipment
rows per order/line pair, and uses the earliest populated
MIN_APPROVED_DENIED_DATETIME. Conflicting statuses, flags, creation timestamps
(including null versus populated) or populated cancellation timestamps stop
exports. Multiple prescriptions referencing one line contribute their earliest
matching upload. Missing/invalid keys and unmatched prescriptions remain in a
separate association table.

Estimated upload = line creation + 0.96 × (approval/denial minimum − creation),
without an intercept. SQL uses decimal arithmetic and rounds the offset to the
nearest nanosecond; timestamp strings preserve nine fractional digits through
extraction. Python independently checks the estimate using integer nanoseconds
and Decimal. The estimate is retained even when actual upload exists. Candidate
upload uses actual upload first, then the estimate; event time is the earliest
populated candidate/cancellation timestamp. A populated cancellation always
caps the event, regardless of line status. Equal times produce `tie` while
retaining the candidate source. Sources are `actual_upload`, `estimated_upload`,
`order_cancellation`, `tie`, or `missing`.

Unsuffixed timestamps are interpreted as UTC. Creation is checked against its
Eastern companion where present. ORDER_CANCEL_DTTM uses the established UTC
interpretation checked against ORDER_CANCEL_DTTM_EST in REFNUM 5; the certified
line view has no cancellation Eastern companion. Missing creation or event
produces null elapsed hours. Null and negative durations remain exported with
quality flags and audit counts; missing estimate inputs leave the estimate null.

Extract, SQL/date fingerprints, provenance, validated line/association/audit
Parquets and export fingerprints live under
`data/cmpu-first-order-line-event-times/<start>_<exclusive-end>_uploads-<upload-start>_<exclusive-upload-end>/`.
Rendered SQL/history use the same variant under
`src/autogenerated/cmpu-first-order-line-event-times/`.
Descriptive `cmpu-first-order-line-event-times_uploads-<upload-start>_<exclusive-upload-end>_{lines,associations,audit}.md`
files live directly in `outputs/tables/<start>_<inclusive-last-day>/`.
Generated artifacts are ignored by Git. Cached mode verifies SQL, dates and the
extract fingerprint and repeats the independent audit without connecting;
SQL-only mode prints the query without writing files or connecting.

## First-order-line survival curve (REFNUM 21)

```bash
# Reuse the audited REFNUM 20 extract; no Snowflake connection is made.
make cmpu-first-order-line-survival
make cmpu-first-order-line-survival START_DATE=2026-08-15 END_DATE=2026-10-15 UPLOAD_START_DATE=2026-08-01
```

Run `make cmpu-first-order-line-event-times` first if its matching extract is
missing. The survival command verifies that extract's SQL, dates and fingerprint
and repeats its source audit before deriving outcomes. It uses the same
prescription/upload windows, all statuses and nullable flags, and one observation
per distinct order/order-line pair. No new dependency is required.

Default interpretation: the event is REFNUM 20's earlier actual/estimated upload
or order cancellation, including ties. The curve estimates the probability of
still awaiting either upload or cancellation after elapsed days from line
creation. It does not estimate upload completion alone. Estimated upload times
use REFNUM 20's fixed 0.96 rule and are treated as event times.

Right-censor missing events and events later than the exclusive upload end
(`END_DATE + 11 days`; October 26, 2026 at 00:00 UTC by default) at that cutoff.
An event exactly at the cutoff is observed. The source must have been extracted
at or after the cutoff. Exclude negative event durations, missing creation and
creation after cutoff from the curve, retaining every line in the detail export.
Zero durations remain. No 12-day truncation or outlier removal is applied.

The Kaplan–Meier calculation groups exact integer nanosecond durations; tied
events use the risk set before censoring at the same duration. Every event-time
risk set and survival probability is checked against the installed statsmodels
SurvfuncRight estimator. Shading shows pointwise 95% log-log Greenwood confidence
intervals conditional on the supplied event times; it does not include uncertainty
from the upload-estimation rule. Independent right censoring is assumed.

Transparent PNG and companion notes use descriptive
`cmpu-first-order-line-survival_uploads-<upload-start>_<exclusive-upload-end>`
filenames directly under `outputs/charts/<start>_<inclusive-last-day>/`.
Line details, the full exact curve (including events, censoring and numbers at
risk), selected-day risk table and audit Markdown files use the matching dated
`outputs/tables/` folder. For PNG rendering only, the first and last exact step
within each horizontal output-pixel bin are retained to bound renderer memory;
the curve tables retain every step. The PNG displays days 0–13 with labeled vertical markers at days 3, 6, 10 and 11;
horizontal guides label the survival probabilities at days 3, 6 and 10.
The curve tables retain the full observed follow-up.
Derived Parquets and a manifest recording source/export fingerprints, endpoint,
cutoff and exclusion/interval rules live under
`data/cmpu-first-order-line-survival/<same-run-variant-as-REFNUM-20>/`.
Generated outputs stay ignored by Git.

## Same-product reorders within seven days of aged cancellation (REFNUM 22)

```bash
make aged-order-same-product-reorders AS_OF_DATE=2026-10-27
make aged-order-same-product-reorders AS_OF_DATE=2026-10-27 CACHED=1
make aged-order-same-product-reorders AS_OF_DATE=2026-10-27 PRINT_SQL=1
# Optional broader original prescription cohort:
make aged-order-same-product-reorders AS_OF_DATE=2026-10-27 APPROVAL_CHANNEL=ALL
```

Defaults select CMPU vet-diet CUSTOMER_UPLOAD prescriptions created
August 15–October 14, 2026 UTC. `START_DATE` is inclusive, `END_DATE` exclusive;
`APPROVAL_CHANNEL=ALL` includes every approval channel. `AS_OF_DATE` defaults to
today's UTC date at 00:00, and must be at or after `END_DATE` and not in the
future. Supply it explicitly when reproducing a saved snapshot.

The cohort uses prescription-referenced first-order lines, joined on both
FIRST_ORDER_ID and numeric FIRST_ORDERITEM_ID. Recorded cancellation reason,
trimmed and case-normalized, must be Aged Order; a canceled line status alone
does not establish that reason. An order cancellation is the timestamped event
for every associated original line. Shipment rows and repeated prescription
associations are collapsed before counting. All original associations and line
eligibility states remain available, including non-aged lines and missing keys.

Reorder attempts require the same CUSTOMER_ID and exact PRODUCT_ID on a
*different* order whose ORDER_PLACED_DTTM lies strictly after cancellation and
at or before cancellation + 168 hours, and no later than `AS_OF_DATE` at 00:00 UTC.
No reorder approval-channel, prescription-source or terminal-status filter is
applied. Later lines are searched in the certified RxP order-line view; this does
not search purchases outside that view. The line view supplies
PRODUCT_PART_NUMBER, which maps to PRODUCT_ID through the latest PDM.PRODUCT
snapshot and last-update timestamp; ambiguous tied mappings stop validation.
Customer mismatches or product mismatches between a prescription and an aged
original line also stop validation. Product mismatches outside the aged cohort
are audited separately, because those lines do not enter reorder rates.

Only cancellations with a complete seven-day follow-up window and usable
customer/product/cancellation keys enter rate denominators. Incomplete follow-up
and cancellations after as-of are reported separately. Customers and
customer/product pairs enter the denominator if they have at least one eligible
cancellation; only matches from eligible cancellations enter their numerators.
Repeated cancellations retain their matches in details; customers and
customer/product pairs each count once in their respective summaries.

Placed attempts include reorders later canceled. The separate shipped result
requires ORDER_LINE_SHIPPED_DTTM at or before as-of; shipping may occur more than
seven days after the original cancellation, provided the reorder was placed
within seven days. This is evidence of some shipment, not proof of delivery or
full-quantity fulfillment. A separate detail flag records shipment within seven
days of cancellation. Raw line statuses are current extraction-time snapshots,
not reconstructed historical as-of statuses. UTC placement and shipment times
are checked against available Eastern companions; cancellation follows the UTC
interpretation established in REFNUM 5. Timestamps retain nanosecond precision.

The complete extraction SQL is
`src/sql/aged_order_same_product_reorders.sql`. Fresh mode uses the read-only
Snowflake runner and browser SSO. `PRINT_SQL=1` prints without connecting or
writing; `CACHED=1` verifies SQL, dates, channel and extract fingerprints and
reruns validation without connecting. Fresh validation must pass before a source
manifest is written.

Extract, provenance, validated Parquets and fingerprints live under
`data/aged-order-same-product-reorders/<start>_<exclusive-end>_<channel>_reorders-7d_as-of-<date>/`.
Rendered SQL/history use the matching variant under
`src/autogenerated/aged-order-same-product-reorders/`.
Five descriptive Markdown exports—prescription associations, original line
eligibility/details, reorder matches, summary and audit—live directly under
`outputs/tables/<start>_<inclusive-last-day>/`, with filenames identifying channel,
seven-day window and as-of date. These generated artifacts are ignored by Git.

### Prescription reuse on seven-day reorders (REFNUM 22 follow-up)

```bash
make aged-order-reorder-prescriptions
make aged-order-reorder-prescriptions CACHED=1
make aged-order-reorder-prescriptions PRINT_SQL=1
```

This command uses the fingerprint-checked REFNUM 22 cache for CUSTOMER_UPLOAD,
with the same default prescription dates and `AS_OF_DATE=2026-10-27` (explicitly
configurable). It revalidates the baseline and selects only eligible, complete
seven-day cancellation/reorder-line matches. It does not refresh the baseline or
change its customer denominator. SQL-only mode reads that local cache to obtain
the frozen keys, then prints without connecting or writing files.

The read-only enrichment fetches RX_ID and RX_USAGE_ID for the exact original
and reorder order/line keys. RX_ID defines prescription identity; different
RX_USAGE_IDs do not imply different prescriptions. One populated RX_ID on each
side gives Same prescription or Different prescription. Multiple IDs are a
separate category; any missing or partially missing ID evidence gives Unknown.
No arbitrary MIN(RX_ID) or missing-ID fallback is used. The comparison reflects
line associations at enrichment extraction, not guaranteed historical assignment
at order placement. Original cohort prescription references and their agreement
with line RX_ID sets remain visible for auditing.

Customers or reordered lines associated with several cancellations can have
multiple comparison types. Summary categories are mutually exclusive combinations
of the observed types. Customer details also provide nonexclusive any-same,
any-different and unresolved flags. The summary includes all reorder attempts
and the subset with shipment evidence by the baseline as-of cutoff.

Four descriptive Markdown line-pair/customer/summary/audit tables live directly
in the dated `outputs/tables/` folder. The matching variant under
`data/aged-order-reorder-prescriptions/` retains source/derived Parquets and
baseline, SQL and enrichment fingerprints; generated SQL/history uses
`src/autogenerated/aged-order-reorder-prescriptions/`. Cached mode verifies the
frozen baseline and enrichment identity before repeating the comparison.

### Approval channels on reordered prescriptions (REFNUM 22 follow-up)

```bash
make aged-order-reorder-approval-channels
make aged-order-reorder-approval-channels CACHED=1
make aged-order-reorder-approval-channels PRINT_SQL=1
```

Uses the frozen REFNUM 22 baseline and prescription-ID enrichment caches, with
the same default dates and `AS_OF_DATE=2026-10-27`. It repeats both source audits,
then joins the RX_IDs on eligible reordered lines to RXP_PRESCRIPTIONS for
APPROVAL_CHANNEL, without filtering the reordered prescription's channel. It
preserves the prior prescription/line/customer populations. Channel values are
current lookup-time values, not a historical reconstruction at order placement.

The summary distinguishes unique prescriptions, unique reordered order/line
pairs, mutually exclusive customer channel combinations, and nonexclusive
customers with any use of each channel. Customers with several channels can
appear in several any-channel rows; those counts must not be added. All reorder
attempts and the shipped-by-as-of subset are reported separately. Missing RX_ID,
unmatched prescriptions and missing approval channels remain separate categories;
duplicate prescription source rows stop validation.

Four descriptive Markdown line-detail/prescription/summary/audit files are saved
directly in the dated `outputs/tables/` folder. Lookup/derived Parquets and
fingerprints use the matching variant under
`data/aged-order-reorder-approval-channels/`; SQL/history use
`src/autogenerated/aged-order-reorder-approval-channels/`. The SQL template is
`src/sql/aged_order_reorder_approval_channels.sql`. SQL-only mode reads the frozen
local caches but does not connect or write files. Cached mode validates frozen
prescription evidence, SQL and lookup fingerprints and regenerates the tables.

### Upload entities for different reorder prescriptions (REFNUM 22 follow-up)

```bash
make aged-order-reorder-uploads
make aged-order-reorder-uploads CACHED=1
make aged-order-reorder-uploads PRINT_SQL=1
```

Uses the frozen reorder, prescription-ID and approval-channel caches with their
fingerprints and original dates (`AS_OF_DATE=2026-10-27` by default). Selects only
Different prescription line pairs; a different RX_ID is not necessarily a
prescription newly created after cancellation. The default population is 2,139
distinct RX_ID/customer pairs on eligible seven-day reorders; original
same-prescription reuse is excluded.

The read-only query searches RXP_UPLOAD_ENTITY for DIET_PRESCRIPTION entities
across all available history through as-of midnight UTC inclusive, with no lower
upload-date bound. Undated records are retained separately. It expands the
brace/comma RX_ID list, matches RX_ID and numeric CUSTOMER_ID, and deduplicates
repeated RX tokens. Repeated uploads do not multiply prescription counts; one
entity may legitimately reference several prescriptions. Other-customer and
invalid/missing customer associations are audited. Missing or duplicate related
upload IDs stop validation. Prescription ownership is checked against the registry.

Matching upload entity presence is separate from HAS_UPLOADED_FILE=true. No
uploaded-file, association, deletion or order-ID predicate restricts the search.
The summary reports dated matching uploads by as-of, undated-only evidence, no
matching upload and the separate recorded-file-upload count, overall and by the
previously frozen approval channel. All different prescriptions and those linked
to shipped reorders are reported separately. No matching entity does not establish
that the customer never uploaded through another record type or after as-of.

Entity links and HAS_UPLOADED_FILE flags reflect lookup-time state; the as-of
cutoff filters entity creation time and does not reconstruct historical file
attachment or RX-link changes.

Upload presence does not require a new upload after cancellation. Line-pair
details retain the original cancellation and prescription creation time, first
and last upload times, and counts of uploads before/at and after cancellation.
A different RX_ID may be associated with several cancellations; temporal evidence
is evaluated against each cancellation independently. Datetimes preserve
nanosecond precision, and unknown file flags/undated uploads remain audited.

Five descriptive dated Markdown prescription/line-pair/upload-association/summary/
audit files use `outputs/tables/<start>_<last-day>/`. Extract/derived Parquets and
all frozen-input/source/export fingerprints use the matching run variant under
`data/aged-order-reorder-uploads/`. SQL template:
`src/sql/aged_order_reorder_uploads.sql`; generated SQL/history:
`src/autogenerated/aged-order-reorder-uploads/`. SQL-only mode reads the frozen
local caches but does not connect or write; cached mode verifies all inputs and
regenerates the exports without connecting.

## Seven- and fourteen-day reorder customer populations (REFNUM 23)

```bash
make aged-order-reorder-windows AS_OF_DATE=2026-10-27
make aged-order-reorder-windows AS_OF_DATE=2026-10-27 CACHED=1
make aged-order-reorder-windows AS_OF_DATE=2026-10-27 PRINT_SQL=1
```

This standalone target calculates both horizons in one source snapshot.
It now requires the same CUSTOMER_ID, PRODUCT_ID and PET_ID by default.
Use MATCH_PET=0 to reproduce the earlier customer/product-only definition. The
original prescription cohort remains CMPU vet diet, CUSTOMER_UPLOAD, created
August 15–October 14, 2026 UTC, using first-order Aged Order cancellations.
`START_DATE` and exclusive `END_DATE` are configurable. `AS_OF_DATE` defaults to
2026-10-27 at 00:00 UTC, preserving the agreed data cutoff; it must be at or after
`END_DATE` and no later than the current UTC date. The existing seven-day target,
extracts and subsequent prescription/channel/upload analyses remain separate.

Each horizon uses its own complete-follow-up population:

| Horizon | Latest eligible cancellation with the default cutoff | Reorder placement window |
| --- | --- | --- |
| 7 days | October 20, 2026 at 00:00 UTC | Strictly after cancellation through cancellation + 168 hours, inclusive |
| 14 days | October 13, 2026 at 00:00 UTC | Strictly after cancellation through cancellation + 336 hours, inclusive |

The denominator is distinct customers with at least one eligible cancellation
and usable customer/product/pet keys. The numerator is customers placing an order
for the exact same PRODUCT_ID and PET_ID on a different order within that eligible
cancellation's window. Count customers once per horizon across repeated products,
orders, prescription associations and cancellations. Fourteen days is cumulative,
including days 1–7. All placed statuses count, even if the reorder later cancels;
shipment/approval is not required. Reorders tied to immature cancellations cannot
enter either numerator, even if that customer has another mature cancellation.
The populations differ, so the raw 14-day reordered count is not required to
exceed the 7-day count. Within the common 14-day-mature cancellation population,
all seven-day evidence must remain present in the fourteen-day result.

Same-pet SQL lives in `src/sql/aged_order_reorder_windows_same_pet.sql`;
`src/sql/aged_order_reorder_windows.sql` retains the customer/product-only query. It retains the established
both-key first-order join, certified order-line shipment collapse, latest
PDM.PRODUCT exact PRODUCT_ID mapping, conflict indicators and UTC timestamps.
Both horizons are explicit in SQL, including follow-up end/maturity and matching
boundaries. Python independently validates SQL maturity, source associations,
matching keys/timestamps, customer aggregation and population containment.
The shared REFNUM 22 validation function accepts a keyword-only followup_days
argument of 7 or 14; its default and original target remain seven days.

Fresh mode queries read-only Snowflake via browser SSO. SQL-only mode prints
without connecting or writing. Cached mode verifies SQL, dates, both horizons and
extract fingerprints and repeats validation without connecting.

The two-row summary reports horizon, latest eligible cancellation UTC, eligible
customers, reordered customers and reorder percentage. Customer flags,
association details, cancellation eligibility/details, reorder matches and audits
are exported alongside it. All six Markdown files live directly under
`outputs/tables/<start>_<inclusive-last-day>/`, with analysis/channel/7d-14d/as-of
filenames. Extract/derived Parquets and fingerprints use the matching variant
under `data/aged-order-reorder-windows/`; rendered SQL/history use
`src/autogenerated/aged-order-reorder-windows/`. Generated artifacts remain ignored.

### Customers by reorder day for the fourteen-day population (REFNUM 23)

```bash
make aged-order-reorder-daily-customers
```

Reads the fingerprint-checked `aged-order-reorder-windows` source cache and
repeats its audit without connecting to Snowflake. Supports the same START_DATE,
exclusive END_DATE and AS_OF_DATE defaults. Run the windows target first if its
matching source cache is missing.

Each customer is counted exactly once, at their shortest exact elapsed time
across eligible fourteen-day same-product cancellation/reorder matches. This is
the customer's minimum observed qualifying delay, rather than necessarily their
chronologically first order. Equal delays choose the earlier reorder timestamp,
then reorder/original order-line IDs for deterministic detail exports.
Day 1 covers (0,24] hours, day 2 (24,48], through day 14 (312,336]. All fourteen
bins are shown, including zeros. Daily counts sum to the 3,286 same-pet reordered
customers, drawn from the 17,501-customer fourteen-day complete-follow-up
population in the default snapshot. MATCH_PET=0 retains the earlier 3,383 count. Customers without reorders are excluded
from the histogram, and placed attempts do not require shipment/approval.

The transparent PNG and companion notes live directly in the matching dated
`outputs/charts/` folder with the windows run prefix plus
`14d-customers-by-reorder-day`. Daily-count and selected-customer Markdown tables
use the matching flat dated `outputs/tables/` folder. Selected-customer and bin
Parquets plus source/export/chart fingerprints are saved under
`data/aged-order-reorder-daily-customers/<windows-run-variant>/`.


### Pet-identity rule and preserved comparisons

```bash
make aged-order-reorder-windows MATCH_PET=1
make aged-order-reorder-windows MATCH_PET=1 CACHED=1
make aged-order-reorder-windows MATCH_PET=1 PRINT_SQL=1
make aged-order-reorder-daily-customers MATCH_PET=1
# Prior definition and frozen output variant:
make aged-order-reorder-windows MATCH_PET=0 CACHED=1
```

MATCH_PET defaults to 1 on these two Make targets. The Python CLI's `--same-pet`
flag selects the new mode; programmatic defaults remain compatible with existing
REFNUM 22 callers. The certified order-line view supplies PET_ID directly; no
pet-name/profile join or fallback to prescription identity is used. Collapse
shipment rows before comparing known, unambiguous original/reorder PET_IDs.
Null pet IDs do not equal one another. Missing/ambiguous original pets are
excluded from population rates and audited; candidate reorder lines with missing
or ambiguous pets cannot qualify. Candidate-pool pet audit counts cover both
horizons and are repeated in each horizon's audit, so do not sum them across
horizons. The pet IDs are current line associations at extraction time.

The same-pet run uses a separate `customer_upload_same-pet_reorders-7d-14d_as-of-...`
variant across data, generated SQL, Markdown tables and plots. Earlier two-key
results and the frozen REFNUM 22 prescription/channel/upload follow-ups are
retained and are not silently reinterpreted as same-pet results. Fresh matching
validates all three identities independently in Python as well as SQL.

With the October 27 cutoff, the same-pet results are 1,773/19,131 customers at
seven days (9.27%) and 3,286/17,501 at fourteen days (18.78%). Original eligible
lines and the shared customer/product candidate reorder pool have no missing or
ambiguous pet identities in this snapshot. The fourteen-day plot counts each
customer once at their shortest qualifying same-customer/product/pet delay.

### Twenty-one-day same-customer/product/pet reorders (REFNUM 23)

```bash
make aged-order-reorder-windows INCLUDE_21_DAYS=1
make aged-order-reorder-windows INCLUDE_21_DAYS=1 CACHED=1
make aged-order-reorder-windows INCLUDE_21_DAYS=1 PRINT_SQL=1
make aged-order-reorder-daily-customers FOLLOWUP_DAYS=21
```

INCLUDE_21_DAYS=1 adds the cumulative 21-day horizon alongside seven and fourteen
days in one fresh snapshot. It requires same-pet matching (MATCH_PET=1, the Make
default). The original prescription cohort, exact customer/product/pet matching,
different-order rule and cutoff remain unchanged. With AS_OF_DATE=2026-10-27,
the 21-day population requires cancellation at or before October 6 at 00:00 UTC;
placements must be strictly after cancellation and at or before cancellation +
504 hours. Customers count once, and immature cancellations cannot contribute.
Each horizon uses its own denominator; the 21-day population must be contained
in the 14-day population, with outcome monotonicity checked only within the
common mature cancellation population.

This mode uses a separate same-pet `reorders-7d-14d-21d` variant for data, SQL,
metadata and six dated Markdown exports, preserving previous 7/14-day snapshots.
The template is `src/sql/aged_order_reorder_windows_same_pet_21_days.sql`; rendered
SQL/history use the matching `src/autogenerated/aged-order-reorder-windows/`
variant. The summary has three rows and states each latest eligible cancellation
time. Fresh, cached and SQL-only controls follow the existing windows target.

FOLLOWUP_DAYS=21 creates the daily plot from that fingerprint-checked local source
cache without querying Snowflake. Each customer counts once at their shortest
qualifying same-customer/product/pet delay. Day 1 is (0,24] hours and day 21 is
(480,504]; all 21 bins are shown. The PNG, companion notes and count/customer
Markdown tables use the new run variant plus `21d-customers-by-reorder-day`;
selected-customer/bin Parquets and fingerprints use the corresponding variant
under `data/aged-order-reorder-daily-customers/`. The fourteen-day plot remains
available with FOLLOWUP_DAYS=14 and the existing 7/14 source cache.

### Reorder prescription identity and approval-channel Sankeys (REFNUM 24)

```sh
# Prerequisite: frozen exact-customer/product/pet 7/14/21-day matches.
make aged-order-reorder-windows INCLUDE_21_DAYS=1
# Inspect the read-only enrichment SQL without querying or writing outputs.
make aged-order-reorder-prescription-sankeys PRINT_SQL=1
# Fresh prescription/channel enrichment and three transparent Mermaid Sankeys.
make aged-order-reorder-prescription-sankeys
# Revalidate the frozen cohort and enrichment fingerprints, then regenerate outputs.
make aged-order-reorder-prescription-sankeys CACHED=1
```

Optional `START_DATE=2026-08-15 END_DATE=2026-10-15 AS_OF_DATE=2026-10-27` uses an exclusive prescription end and an as-of cutoff at 00:00 UTC. The prerequisite cache must use the same dates and `INCLUDE_21_DAYS=1` with same-pet matching. Docker must already be running for Mermaid rendering.

Each horizon counts a reordered customer once, selecting the cancellation/reorder pair with the shortest exact delay. Ties use earlier reorder placement, reorder order/line IDs, then original order/line IDs. Original and reordered lines must have the same customer, product and populated unambiguous pet. This selection matches the daily plot and is not necessarily the customer's chronologically first reorder. Separate complete-follow-up populations apply to each horizon; placed attempts count regardless of shipment or later status.

The diagrams show reordered customers → prescription identity → approval channel **only for Different prescription**. Compare actual line `RX_ID` evidence; `RX_USAGE_ID` does not define identity. Missing/partial IDs are Unknown, and multiple IDs remain separate. Same prescription and unresolved categories terminate at the identity stage. Diagram percentages use all reordered customers in that horizon; channel tables also show the percentage within Different prescription customers. Customers without reorders remain outside the diagrams. Current line associations and registry approval channels do not establish historical assignment/channel at placement.

Extracts, validated details/distributions/flows/audits and SHA-256 manifests are under `data/aged-order-reorder-prescription-sankeys/<period>/`. SQL and query history are under `src/autogenerated/aged-order-reorder-prescription-sankeys/<period>/aged_order_reorder_prescription_sankeys.sql`. Descriptive Markdown tables are directly under `outputs/tables/<inclusive-date-range>/`; PNG/SVG diagrams and notes are under `outputs/diagrams/<inclusive-date-range>/`, with Mermaid sources under `src/diagrams/<inclusive-date-range>/`. Names retain the horizon, same-pet variant and cutoff. Previous REFNUM 22 enrichments and diagrams are preserved.

### Upload and approval/denial evidence for different reorder prescriptions

```sh
# Requires the frozen REFNUM 24 prescription/channel enrichment above.
make aged-order-reorder-upload-approval-evidence PRINT_SQL=1
make aged-order-reorder-upload-approval-evidence
make aged-order-reorder-upload-approval-evidence CACHED=1
```

Supports the same `START_DATE`, exclusive `END_DATE` and `AS_OF_DATE` as the Sankeys. Revalidates the 7/14/21-day same-customer/product/pet cache and REFNUM 24 enrichment, selecting one shortest-delay pair per customer/horizon. Counts **distinct different RX_IDs within each horizon**; the horizons overlap and must not be added together. Approval channel is the frozen REFNUM 24 value.

Entity uploads follow the established REFNUM 22 rules: `DIET_PRESCRIPTION`, expanded RX_ID plus exact numeric customer ID, all history through the as-of date at 00:00 UTC inclusive. The main overlap counts require a dated entity by cutoff; undated entity records and `HAS_UPLOADED_FILE=true` evidence are separate measures. No after-cancellation upload requirement is imposed. An entity record alone does not prove an uploaded file.

The approval/rejection field used is the certified line view's `MIN_APPROVED_DENIED_DATETIME`, interpreted as UTC as in REFNUM 20. Take the earliest populated minimum across shipment rows of each selected reordered line. Check whether any selected line for that prescription **within that horizon** has a non-null minimum. This is current non-null evidence and is not restricted to decision timestamps before cutoff; after-cutoff minima are reported separately. A different line selected for the same prescription in another horizon cannot supply its timestamp. Current line RX_IDs must agree with the frozen selection.

Four mutually exclusive categories are Both upload and decision timestamp, Upload only, Decision timestamp only and Neither. Additional upload, decision and union totals overlap. Summary tables include All channels and individual approval channels. Dated Markdown summary/prescription/customer/upload-association/line-evidence/audit tables are under `outputs/tables/<inclusive-date-range>/`; extracts/Parquets/fingerprints are under `data/aged-order-reorder-upload-approval-evidence/<period>/`; generated SQL/history under `src/autogenerated/aged-order-reorder-upload-approval-evidence/<period>/`.

To add the upload/decision evidence as a fourth stage to all three REFNUM 24 Sankeys:

```sh
make aged-order-reorder-prescription-sankeys WITH_EVIDENCE=1 CACHED=1
```

`WITH_EVIDENCE=1` (`--with-evidence`) always reads and revalidates the frozen prescription/channel and upload/decision caches; it runs no Snowflake query. Refresh those prerequisite analyses separately when needed. Each approval-channel node splits into **Both upload and decision time**, **Upload only**, **Decision time only**, or **Neither**, retaining channel-specific terminal nodes. Decision time is the current non-null `MIN_APPROVED_DENIED_DATETIME` check, including after-cutoff minima; uploads retain the existing dated-entity cutoff. Same prescription and unresolved identity categories terminate before the channel stage. Each customer counts once per horizon and all node percentages use the full reordered-customer denominator. These diagrams count customers; the preceding upload/decision analysis counts distinct prescriptions (the counts coincide for the current per-horizon selections).

Four-stage PNG/SVG/Mermaid sources and Markdown tables have `with-upload-decision-evidence` in their filenames; derived Parquets and manifests use a separate `<period>_with-upload-decision-evidence` directory under `data/aged-order-reorder-prescription-sankeys/`. The original three-stage outputs are preserved. Export manifests record both prescription/channel and upload/decision source fingerprints.

Sankey subtitles show the inclusive maximum eligible order-line cancellation timestamp (`AS_OF_DATE` at 00:00 UTC minus the horizon). With the October 27 cutoff, these limits are October 20, October 13 and October 6 at 00:00 UTC for 7, 14 and 21 days. These are eligibility limits, not the latest observed cancellation times.

### WISMO after aged cancellation and before reorder (REFNUM 25)

The user confirmed that `FCT_CONTACTS_BRD.SESSION_START_DTTM` is **UTC** on October 27, 2026. Use `CONTACT_TIMEZONE=UTC` for this analysis. The Snowflake type is `TIMESTAMP_NTZ(9)`, so the workflow still requires an explicit timezone rather than inferring one from the type. `America/New_York` remains available only for a separately confirmed Eastern source.

```sh
make aged-order-reorder-wismo CONTACT_TIMEZONE=UTC PRINT_SQL=1
make aged-order-reorder-wismo CONTACT_TIMEZONE=UTC
make aged-order-reorder-wismo CONTACT_TIMEZONE=UTC CACHED=1
# Add WISMO as a fifth categorical stage to the active 7/14/21-day Sankeys.
make aged-order-reorder-prescription-sankeys WITH_WISMO=1 CONTACT_TIMEZONE=UTC CACHED=1
```

The contact extraction revalidates the frozen REFNUM 24 selection; supports the same `START_DATE`, exclusive `END_DATE` and midnight-UTC `AS_OF_DATE`; and retains all selected reordered customers, including same-prescription reuse. Match `EDLDB.BT_CUSTOMER_CARE.FCT_CONTACTS_BRD.ORDER_ID` to the **original aged order**, never the reordered order. Require both `CATEGORY_WISMO_FLAG=TRUE` and `HANDLED_FLAG=TRUE`, and strictly:

```text
original cancellation time < contact SESSION_START_DTTM converted to UTC < selected reorder placement
```

Contacts exactly at cancellation or reorder are excluded, as are missing contact timestamps. An agent leg starting later does not qualify a session that started before cancellation. `wismo_contact_count` follows the supplied `COUNT(*)` over matching contact legs; distinct sessions, earliest/latest qualifying session start, sorted distinct channels, source/interval audits and individual contact/interval associations are also exported. A handled contact can contain several legs; no silent session deduplication changes the requested count. Deduplicate order/time lookup intervals before querying, then map back to the existing one-customer-per-horizon selection. Horizon and interval contact totals can overlap; they are not unique global contacts. Contact evidence is order-level, not proof about a specific item or pet.

WISMO outputs are under `data/aged-order-reorder-wismo/<period>/<timezone>/`, generated SQL/history under `src/autogenerated/aged-order-reorder-wismo/<period>/<timezone>/`, and descriptive Markdown summary/customer/interval/contact/audit tables directly under the dated `outputs/tables/` folder. Timezone, SQL, frozen dependencies and Parquet/export hashes must agree for cached runs.

`WITH_WISMO=1` implies the existing upload/decision evidence stage and reads only validated caches. The final WISMO stage counts **customers**, splitting all previous terminal paths into Handled contact before reorder versus No dated matching contact. Same/unresolved prescription categories also flow into this stage. A no-match label is limited to the strict interval; undated source contacts are audited separately. The diagram is a categorical breakdown, not a chronological ordering of the stages. New diagram/table/data names include `with-wismo-<timezone>` and preserve all previous variants.

To remove the WISMO category restriction while retaining the strict cancellation-to-reorder contact window, use `ALL_CONTACTS=1` on the contact and Sankey targets. To remove the contact time restriction too, use **`ALL_ORDER_HISTORY=1`**, which implies all handled contact categories:

```sh
make aged-order-reorder-wismo CONTACT_TIMEZONE=UTC ALL_ORDER_HISTORY=1 PRINT_SQL=1
make aged-order-reorder-wismo CONTACT_TIMEZONE=UTC ALL_ORDER_HISTORY=1
make aged-order-reorder-wismo CONTACT_TIMEZONE=UTC ALL_ORDER_HISTORY=1 CACHED=1
make aged-order-reorder-prescription-sankeys CONTACT_TIMEZONE=UTC ALL_ORDER_HISTORY=1 CACHED=1
```

The all-history mode keeps `HANDLED_FLAG=TRUE` and joins only the original aged order. There is **no `CATEGORY_WISMO_FLAG` predicate and no contact timestamp predicate**. True, false and null categories, contacts before cancellation, exact boundaries, after reorder, after the cohort cutoff and missing contact timestamps are included. The reorder cohort and its 7/14/21-day maturity rules remain unchanged. Contact history reflects the available data at lookup time, not presence as of the cohort cutoff or before reorder. Distinct sessions and earliest/latest populated timestamps remain separate from `COUNT(*)` contact-leg totals; undated contacts count as present.

Each mode has separate SQL/extract/cache/export/diagram variants: WISMO-only strict, all handled categories strict, and all handled order history. All-history source paths append `_all-handled-contacts_all-order-history`; diagram/data variants include `with-all-handled-contacts-all-history-UTC`. Metadata fingerprints bind both category scope and time scope. Neutral exported fields include `contact_count`, `has_handled_contact`, `first_contact_dttm`, `last_contact_dttm`, `customers_with_contact` and `customers_without_contact`. The source's actual `category_wismo_flag` is retained in contact evidence. The all-history Sankey stage is labeled Contacts on aged order / all history; earlier variants are preserved.

For the all-handled-contact diagrams, contact presence appears **immediately after Reordered customers**: Reordered customers → Contacts on aged order → Prescription identity → Approval channel → Upload/decision evidence. Counts and the all-history contact definition are unchanged by this layout. Contact branches merge into prescription identity; subsequent channel/evidence nodes show overall totals.

### Contact timing around aged-order cancellation (REFNUM 26)

```sh
make aged-order-contact-cancellation-distribution
# Optional cohort parameters must match the existing all-history contact cache.
make aged-order-contact-cancellation-distribution START_DATE=2026-08-15 END_DATE=2026-10-15 AS_OF_DATE=2026-10-27
```

Reads and revalidates the frozen 7/14/21-day same-customer/product/pet reorder sources and the **all-category, all-history handled-contact cache** from REFNUM 25 (`CONTACT_TIMEZONE=UTC ALL_ORDER_HISTORY=1`). No Snowflake query runs. Each customer retains their selected shortest-delay original cancellation/reorder pair, but every handled contact leg on that aged order contributes to the distribution. A customer can contribute several contact legs and several bins. Cohorts overlap, so their contact totals must not be summed as globally unique contacts.

Lag is UTC contact `SESSION_START_DTTM` minus the original aged-order cancellation time. Signed 24-hour bins use exact integer nanosecond floor division and intervals `[day,day+1)`: e.g. `[-2,-1)` is 24–48 hours before cancellation and `[4,5)` is 96–120 hours after. Day 0 covers `[0,24)` hours starting at cancellation. Exact-cancellation contacts are also counted separately in the summary. Missing contact times remain in contact details and summaries and are excluded only from the dated histogram denominator.

Generates three transparent Altair PNG histograms with identical day and percentage axes, a vertical day-0 cancellation marker, before/at-after colors, contact totals and top-bin count labels. Y is share of dated contact legs within each horizon; counts and per-bin distinct customers/sessions are in the exported tables. All zeros and tails are retained. Files are under dated `outputs/charts/` and `outputs/tables/`; bins, summaries, contact details and dependency/source/export/figure fingerprints are under `data/aged-order-contact-cancellation-distribution/<period>_all-handled-contacts_all-order-history_UTC/`. The source SQL remains the REFNUM 25 all-order-history query; no new warehouse SQL is required.

### Markdown export size limit

Every generated `.md` file is limited to **1,000,000 bytes (1 MB)**. Large tables produce an explicitly labeled preview of up to 25 rows; complete records remain in the analysis's `data/` Parquet extracts. A final file-level check also bounds reports containing several tables or long notes. Small Markdown exports and non-Markdown outputs retain their existing contents.

Python generators use `markdown_table(frame)` for bounded table formatting and `write_text(path, text)` from `src.python.markdown_tables` for text exports. The writer applies the size cap only to `.md` files; SQL, JSON, Mermaid, SVG and other text exports pass through unchanged. Keep these helpers when adding generators. Existing large Markdown files were removed; Parquet data, figures and compact summaries are retained. Regenerating an analysis now produces only size-limited Markdown previews and summaries.
