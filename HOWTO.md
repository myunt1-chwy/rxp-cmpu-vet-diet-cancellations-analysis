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

## Build the LaTeX report

```bash
make report
# If latexmk is not on PATH:
make report LATEXMK=/Library/TeX/texbin/latexmk
```

Requires a TeX distribution providing `latexmk`, `pdflatex` and the packages used by the report (for example MacTeX). The target compiles `src/latex/main.tex` from its source directory so the local style and appendix inputs resolve. `latexmk` runs the passes needed for references and the appendix contents. Intermediate files and the compiler log stay under ignored `build/latex/`; the successfully built PDF is copied to **`outputs/pdf/cmpu-aged-order-analysis.pdf`**. A failed compile leaves the previous published PDF in place. This target does not run the data analyses or access Snowflake.

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

## Accepted-entity timing from order placement (REFNUM 49)

All current CMPU timing targets use **ORDER_PLACED_DTTM (UTC)** as time zero.
Upload evidence requires a `DIET_PRESCRIPTION` entity currently in
`STATE_NAME = 'ACCEPTED'`, matching expanded RX_ID and numeric CUSTOMER_ID.
The current state is not a historical state at cancellation, and entity acceptance
is separate from prescription approval.

Keep each target's existing **CREATED_TS_UTC discovery window**. Select the earliest
accepted entity by CREATED_TS_UTC, breaking ties by UPLOAD_ID, then use that
same entity's **STATE_CHANGED_TS_UTC** for the observed endpoint. State changes
may occur beyond the discovery window or after cancellation. Retain selected ID,
creation/state-change timestamps and current state. An accepted entity with no
state-change timestamp still counts as present; its duration is missing. There
is no fallback to CREATED_TS_UTC for elapsed time.

- Acceptance elapsed time = STATE_CHANGED_TS_UTC − ORDER_PLACED_DTTM.
- Approval elapsed time = the target's approval endpoint − ORDER_PLACED_DTTM.
- Upload-to-approval gap = approval elapsed time − acceptance elapsed time.
- Ratio = acceptance elapsed time / approval elapsed time.
- Event estimate = ORDER_PLACED_DTTM + 0.96 × (MIN_APPROVED_DENIED_DATETIME − ORDER_PLACED_DTTM), rounded to nanoseconds, without an intercept.

The fixed **0.96** coefficient is retained pending a later update; regenerated
descriptive fits do not change it. Observed accepted-state timing takes precedence
over estimates. Cancellation caps event time; the existing observation cutoff,
censoring rules, ties and day-13 survival display remain. Keep missing/negative
values in details and audits; each distribution retains its documented exclusions.
UTC/Eastern placement companions are checked within one second where available.
Line-creation timestamps remain in source evidence but are not timing origins.

Caches and outputs include **accepted-state-change_order-placed**. Old caches
cannot satisfy the new SQL/definition fingerprints. Full derived datasets stay
in Parquet under data/; Markdown tables remain bounded to 1 MB. The Sankey target
also exports placement-to-state-change hours and quality flags in its line and
association data. Legacy first_upload_at_utc remains the selected entity's
creation timestamp for discovery validation; upload_state_changed_at_utc is the
new timing endpoint. Event extracts retain corresponding association/actual
creation, state-change and entity-ID fields.

Fresh execution order (the upload measures share one validated extract):

```sh
make cmpu-first-order-line-status
make cmpu-first-order-line-approval-distribution
make cmpu-first-order-line-upload-distribution
make cmpu-upload-to-approval-distribution CACHED=1
make cmpu-first-order-line-approval-distribution WITH_UPLOAD=1 CACHED=1
make cmpu-upload-time-ratio-distribution CACHED=1
make cmpu-order-to-approval-distributions
make cmpu-first-order-line-event-times
make cmpu-first-order-line-survival
make report
```

The extraction targets retain CACHED=1 and PRINT_SQL=1; survival validates its
frozen event-time prerequisite. Targets retain their existing counting grains
and eligibility restrictions, including D-status requirements where applicable.
The approval-only target still does not require upload presence unless
WITH_UPLOAD=1. Separate reorder/contact/history analyses and the archived
approval_time_analysis.sql queries retain their established definitions.

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
approval; conflicting statuses or placement timestamps reject the extract,
including missing/populated mixtures. UTC/Eastern placement companions must
agree within one second where populated. Missing companions are audited.

The three targets calculate hours as follows:

| Target | Timing difference | Negative durations |
| --- | --- | --- |
| `cmpu-first-order-line-approval-distribution` | Latest approval minus order placement | Retained |
| `cmpu-first-order-line-upload-distribution` | Selected accepted entity state change minus order placement | Excluded |
| `cmpu-upload-to-approval-distribution` | Latest approval minus selected accepted entity state change | Excluded |

The upload-to-approval target plots only **0 through 60 seconds inclusive**, with
one-second histogram bins and a CDF normalized to those displayed lines. Exactly
60 seconds is retained in the final histogram bin. Captions and the plot-counts
table report displayed and omitted counts. Full-range statistics, hourly bins,
CDF and Parquet details remain exported; other timing targets keep their full range.


Upload entities match by expanded RX_ID and numeric CUSTOMER_ID; the earliest
matching entity within the upload search window supplies the upload time.
Multiple uploads cannot multiply lines. Matching does not establish file
presence and need not precede approval or follow order placement. Both timing
endpoints are required; the upload-minus-line calculation does not require
approval. Excluded negatives remain in details and eligibility audits. Zero
and all nonnegative outliers are retained.

Timing targets normally produce a transparent Altair count histogram with integer-aligned
one-hour bins `[lower, upper)` and an exact empirical cumulative distribution
with labeled verticals at 24, 72, 144 and 240 hours. The full observed eligible
range is shown except for the upload-to-approval plots, which show 0–60 seconds. Empty populations produce tables and remove stale figures.
Statistics use unbinned durations and linear interpolation: N, minimum, p25,
median, p75 and p95. Histogram and cumulative totals reconcile to eligible
unique lines. Missing keys, unmatched lines, status exclusions, missing timing
endpoints and upload-source identifier quality are audited at explicit grains.

Charts live directly in `outputs/charts/<start>_<last-prescription-day>/`, using
inclusive dates. For the default run this is `outputs/charts/2026-08-15_2026-10-14/`.
Filenames identify the measure, upload window, negative filter and figure type:

- `cmpu-d-lines_order-placement-to-accepted-state-change_uploads-2026-08-01_2026-10-25_nonnegative_accepted-state-change_order-placed_histogram.png`
- `cmpu-d-lines_order-placement-to-accepted-state-change_uploads-2026-08-01_2026-10-25_nonnegative_accepted-state-change_order-placed_cumulative.png`

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

Rerun the accepted-state-change variants for current counts and timing statistics; earlier creation-time summaries are superseded.

## Sankeys with the extended upload window

```bash
make cmpu-first-order-line-status
make cmpu-first-order-line-status CACHED=1
make cmpu-first-order-line-status PRINT_SQL=1
.venv/bin/python -m pytest -q tests/test_cmpu_first_order_line_status.py
```

Sankey exports use a wide layout for landscape PDF pages, with wrapped category labels, separate counts/percentages and larger text. Titles/date notes and column headings wrap. Transparent PNG and SVG outputs retain the same populations, flow weights and percentages. Re-render with `CACHED=1`; no warehouse refresh is needed. The report includes only the CMPU vet-diet first-order-line Sankey for the `CUSTOMER_UPLOAD` approval channel, on one portrait page, scaled to the available text width and height. The entire report uses portrait pages. Generate its input with the cached first-order-line target before `make report`:

```sh
make cmpu-first-order-line-status CACHED=1
make report
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

All three views show **approval channel → order line status →
cancellation reason → matching upload**. Column headers identify stages; visible
node labels omit repeated prefixes such as `Channel:` and `First order cancel reason:`.

Line status uses raw `ORDER_ORDER_LINE_STATUS` codes (including C/D/R/S/X),
with blank/null codes shown as `[Unknown line status]`. Order status remains in
the data and comparison tables, but is omitted from the diagrams.
Cancellation reason is trimmed `ORDER_CANCEL_REASON`; blank/null values appear
as `[No cancellation reason recorded]`, which does not imply an uncanceled order.
This analysis has no separate line-cancellation-reason field.

`ORDER_ITEM_BLOCK_REASON` remains in extracts, line/association details, grouped
distributions and block-reason tables, but is omitted from Sankey diagrams.
Known non-D classifications retain actual reasons or `[No block reason recorded]`;
D/unknown classifications retain explicit not-applicable values in the data.
Upload endpoints use two groups: **With cancellation reason** and **No cancellation
reason**, each split into **Has matching upload** and **No matching upload**.
Null, blank and whitespace-only reasons belong to the no-reason group. All
recorded reason values contribute to the with-reason group. These stages describe a
categorical breakdown, not a chronological journey.

The third view contains only CUSTOMER_UPLOAD lines with a known non-D status,
including C/R/S/X rather than X alone. It includes the same four columns as the
other views. Cancellation reasons use purple consistently across all views.

Every transition conserves that figure's distinct-line population. Full,
CUSTOMER_UPLOAD and non-D CUSTOMER_UPLOAD figures each use their own complete
population for node/flow percentages, rounded to two decimals, not the parent-node
or individual-status subtotal. Transition totals must not be added together.

### Matching upload entities

Match `DIET_PRESCRIPTION` entities on expanded RX_ID and numeric CUSTOMER_ID
within the creation-based extended upload window. Require current `STATE_NAME = 'ACCEPTED'`; select earliest `CREATED_TS_UTC`, breaking ties by `UPLOAD_ID`. Use that selected entity's `STATE_CHANGED_TS_UTC` for elapsed-time endpoints, without a state-change-date filter. No uploaded-file
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

The prescription/line population is independent of accepted-entity presence. Audit tables reconcile unmatched prescriptions, distinct lines and accepted-entity counts for each refreshed snapshot.

## Upload time as a share of approval time (REFNUM 18)

```bash
make cmpu-upload-time-ratio-distribution CACHED=1
make cmpu-upload-time-ratio-distribution PRINT_SQL=1
# Optional fresh read-only extraction using the shared timing source:
make cmpu-upload-time-ratio-distribution
```

For CMPU vet-diet CUSTOMER_UPLOAD D-status first-order lines, compute
`(selected accepted entity state change − order placement) /
(latest populated approval − order placement)`. A ratio of 0.75 is 75%: upload
occurred three-quarters of the way from order placement to approval. Use the
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

The ratio target regenerates descriptive linear/log fits for the accepted state-change endpoint. These fits do not replace the fixed 0.96 event-time coefficient.

The REFNUM 18 target also plots the two elapsed times and fits a line using
exactly the same eligible unique lines. The scatter x axis is order placement
to latest approval in hours; the y axis is order placement to earliest matching
upload in hours. All points and outliers are retained. Unweighted ordinary
least squares estimates an intercept and slope; the line is shown over the
observed x range. The equation, R² and N appear on the figure and in
`linear-fit.md` alongside the other ratio tables. A negative fitted intercept
is allowed; this is an unconstrained descriptive fit between intervals sharing
a start time. Fewer than two points or constant x values produce a scatter
without a regression; R² is undefined for constant y values.

The scatter is named
`cmpu-d-lines_upload-vs-approval-times_uploads-2026-08-01_2026-10-25_nonnegative_accepted-state-change_order-placed_linear-fit.png`
in the same flat chart folder. Inspect the newly generated linear-fit table for the current coefficients and population.
Regenerate with `make cmpu-upload-time-ratio-distribution CACHED=1`.

The same target also fits natural logs of both elapsed times and saves a
log–log scatter as
`cmpu-d-lines_upload-vs-approval-times_uploads-2026-08-01_2026-10-25_nonnegative_accepted-state-change_order-placed_log-log-fit.png`.
The axes show hours on logarithmic scales. Fit
`ln(upload_hours) = intercept_log_hours + slope × ln(approval_hours)`
with unweighted OLS and an intercept. The equivalent curve is
`upload_hours = exp(intercept_log_hours) × approval_hours^slope`; it is the
direct back-transformation of the log-space fit, without a mean-response bias
correction. R² is computed in log space. Only strictly positive time pairs
from the ratio-eligible cohort enter this fit; no pseudocount is added.
Zero/nonpositive exclusions and the fit N are exported in `log-log-fit.md`.
Zero-ratio observations still belong to the original ratio and linear analyses.
Inspect the new log-log-fit table for its current eligible population and coefficients.
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
- `cmpu-d-lines_upload-vs-approval-times_uploads-2026-08-01_2026-10-25_nonnegative_accepted-state-change_order-placed_linear-fit.md`
- `cmpu-d-lines_upload-vs-approval-times_uploads-2026-08-01_2026-10-25_nonnegative_accepted-state-change_order-placed_log-log-fit.md`

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
MIN_APPROVED_DENIED_DATETIME. Conflicting statuses, flags, order-placement timestamps
(including null versus populated) or populated cancellation timestamps stop
exports. Multiple prescriptions referencing one line contribute their earliest
matching upload. Missing/invalid keys and unmatched prescriptions remain in a
separate association table.

Estimated acceptance = order placement + 0.96 × (approval/denial minimum − order placement),
without an intercept. SQL uses decimal arithmetic and rounds the offset to the
nearest nanosecond; timestamp strings preserve nine fractional digits through
extraction. Python independently checks the estimate using integer nanoseconds
and Decimal. The estimate is retained even when actual upload exists. Candidate
upload uses actual upload first, then the estimate; event time is the earliest
populated candidate/cancellation timestamp. A populated cancellation always
caps the event, regardless of line status. Equal times produce `tie` while
retaining the candidate source. Sources are `actual_upload`, `estimated_upload`,
`order_cancellation`, `tie`, or `missing`.

Unsuffixed timestamps are interpreted as UTC. Order placement is checked against its
Eastern companion where present. ORDER_CANCEL_DTTM uses the established UTC
interpretation checked against ORDER_CANCEL_DTTM_EST in REFNUM 5; the certified
line view has no cancellation Eastern companion. Missing placement or event
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
still awaiting either upload or cancellation after elapsed days from order
placement. It does not estimate upload completion alone. Estimated upload times
use REFNUM 20's fixed 0.96 rule and are treated as event times.

Right-censor missing events and events later than the exclusive upload end
(`END_DATE + 11 days`; October 26, 2026 at 00:00 UTC by default) at that cutoff.
An event exactly at the cutoff is observed. The source must have been extracted
at or after the cutoff. Exclude negative event durations, missing placement and
placement after cutoff from the curve, retaining every line in the detail export.
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

The reorder diagrams use the same wide landscape layout as the first-order-line Sankeys.

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

## Shipment history before aged cancellation (REFNUM 35)

```bash
make aged-customer-prior-shipped-prescriptions
make aged-customer-prior-shipped-prescriptions CACHED=1
make aged-customer-prior-shipped-prescriptions PRINT_SQL=1
make aged-customer-prior-shipped-prescriptions START_DATE=2026-08-15 END_DATE=2026-10-15 AS_OF_DATE=2026-10-27
```

Uses the same aged-order cohort as REFNUM 32: CMPU vet-diet CUSTOMER_UPLOAD prescriptions created in the start-inclusive/end-exclusive UTC window, linked by both first-order keys to recorded Aged Order cancellations on or before AS_OF_DATE at 00:00 UTC. Collapse shipment rows and repeated associations, then count each known customer once. The frozen reference population contains 20,587 customers; a comparison table reports customer additions/removals when the matching REFNUM 32 snapshot is available. Missing customer IDs remain in order/association audits, outside customer denominators.

For each customer, use the earliest qualifying cancellation and exclude every qualifying aged-cancelled ORDER_ID in the cohort, including all tied reference orders and all lines on those orders. A partially shipped line on an aged-cancelled order cannot count as prior shipment experience, even if another line was cancelled or the shipment predates the reference cancellation. Search all available prior shipment history; require ORDER_LINE_SHIPPED_DTTM strictly before cancellation and match both RX_ID and customer ID between ORDER_LINE_COST_MEASURES_RXP and RXP_PRESCRIPTIONS. No restriction on historical approval channel, prescription creation date, product or pet is added. A shipped line is sufficient evidence: delivery and full-order fulfillment are not required, and current order/prescription status does not override a shipment timestamp. All times are UTC.

The headline counts and percentages use the complete aged-customer denominator:

- **Prior inclusive pharmacy shipment:** IS_VET_DIET_FLAG=TRUE, or MERCH_CLASS2 Pharmacy, Compound or Over the Counter.
- **Prior vet-diet shipment:** IS_VET_DIET_FLAG=TRUE, any prescription source.
- **Prior CMPU vet-diet shipment:** vet diet with PRESCRIPTION_SOURCE=CMPU, any approval channel.

These measures are nested, not additive. Exclusive groups reconcile the denominator: no qualifying inclusive-pharmacy history; inclusive pharmacy without vet diet; vet diet without CMPU vet diet; and CMPU vet diet. Category details include Pharmacy, Compound, Over the Counter, Vet diet and Other/unclassified, with distinct customers/orders/lines/prescriptions. The vet-diet flag takes precedence for category detail when merchandise classification disagrees; those disagreements are audited. Unmatched prescriptions, missing RX IDs and customer mismatches remain in shipment evidence/audits but cannot supply qualifying history. Conflicting source customers and duplicate historical RX identities stop publication.

October 27, 2026 extraction: the same 20,587 customers as REFNUM 32, with no customer additions/removals. Prior inclusive-pharmacy shipments: 17,360 customers (84.33%); prior vet-diet shipments: 16,589 (80.58%); prior CMPU vet-diet shipments: 7,942 (38.58%). Exclusive groups: 3,227 without qualifying history, 771 with inclusive pharmacy but no vet diet, 8,647 with vet diet but no CMPU vet diet, and 7,942 with CMPU vet diet. Evidence includes 554,877 eligible order/line/RX records; 1,511,099 records missing RX_ID and 220 RX/customer mismatches are retained in audits and excluded from qualifying history. No eligible category was unclassified. Observed candidate shipment dates span September 27, 2011 through October 25, 2026; this is not a guarantee of complete historical coverage.

The SQL template is `src/sql/aged_customer_prior_shipped_prescriptions.sql`. Generated SQL/history live under `src/autogenerated/aged-customer-prior-shipped-prescriptions/` per repository instructions. Full source, customer flags, reference orders, shipment evidence, association/category/group/audit/coverage exports and fingerprint manifests live under the matching `data/` directory. Descriptive Markdown tables are directly under dated `outputs/tables/` folders and obey the 1 MB limit. Cached mode verifies SQL/date/source fingerprints; SQL-only mode does not connect or export files. History coverage reports observed candidate shipment dates for these customers, not the source's retention boundary. No chart is generated.

## Shipment history before the full CMPU order cohort (REFNUM 38)

```bash
make cmpu-customer-prior-shipped-prescriptions
make cmpu-customer-prior-shipped-prescriptions CACHED=1
make cmpu-customer-prior-shipped-prescriptions PRINT_SQL=1
make cmpu-customer-prior-shipped-prescriptions APPROVAL_CHANNEL=CUSTOMER_UPLOAD
make cmpu-customer-prior-shipped-prescriptions START_DATE=2026-08-15 END_DATE=2026-10-15 AS_OF_DATE=2026-10-27
```

Uses the full CMPU vet-diet prescription cohort, all approval channels by default (`APPROVAL_CHANNEL=ALL`), with no order-status, cancellation-reason or reorder restriction. The UTC prescription-creation window is start inclusive and end exclusive. Count each known prescription customer once. Match first-order lines by both FIRST_ORDER_ID and numeric FIRST_ORDERITEM_ID, collapse shipment rows and validate customer IDs and UTC/Eastern order-placement companions where populated. Conflicting source identities or timestamps stop publication. The earliest matched cohort order placement is the customer's reference, requiring complete matched order/customer/placement information for every associated cohort prescription. Missing/invalid/unmatched order keys, missing placement, customer disagreement or placement after AS_OF_DATE at 00:00 UTC make the reference unknown; do not call those customers new/no-history customers. Summaries expose both all-cohort and assessable denominators, and unknown references are an explicit exclusive group.

Require a historical ORDER_LINE_SHIPPED_DTTM strictly before reference placement and matching RX_ID/customer ID across the two certified views. Exclude every FIRST_ORDER_ID in the analysed prescription set and all its lines, even if an older shipment on that same order exists. No approval-channel/product/pet/prescription-date filter restricts historical shipments. Use the same nested categories as REFNUM 35: inclusive pharmacy (Pharmacy + Compound + Over the Counter + vet diet), vet diet, and CMPU vet diet. One shipped line suffices; neither full-order fulfillment nor delivery is required. Current statuses do not replace shipment evidence. Existing aged-cancellation targets retain their cancellation-based reference and counts.

SQL: `src/sql/cmpu_customer_prior_shipped_prescriptions.sql`. Generated SQL/history are under `src/autogenerated/cmpu-customer-prior-shipped-prescriptions/`. Full source and association/order/customer/history/category/group/audit/coverage Parquet exports and fingerprints are under `data/cmpu-customer-prior-shipped-prescriptions/<dates>_as-of-<date>_channel-<channel>/`. Bounded descriptive Markdown tables go directly under dated `outputs/tables/` folders. Cached mode verifies SQL/date/channel/source fingerprints; SQL-only mode does not connect or export. Historical records without RX_ID cannot establish matched prescription shipment experience and are omitted from candidate discovery; extracted unmatched RX/customer records remain audited. No chart is generated.

October 27, 2026 all-channel snapshot: 113,608 prescriptions and 84,425 distinct customers. Complete matched order references are available for 75,553 customers; 8,872 remain unknown (10,095 prescription associations lack FIRST_ORDER_ID). Before earliest cohort order placement, 59,554 assessable customers had prior inclusive-pharmacy shipments (78.82% of assessable; 70.54% of all cohort customers), 55,184 had prior vet-diet shipments (73.04%; 65.36%), and 25,671 had prior CMPU vet-diet shipments (33.98%; 30.41%). Unknown-reference customers are not classified as having no prior history. There are 1,957,984 eligible shipment records and 1,049 excluded RX/customer mismatches; no eligible shipment references a cohort ORDER_ID. REFNUM 35's aged-order customer counts remain unchanged.

## Prior same-clinic shipment experience for aged customers (REFNUM 42)

```bash
make aged-customer-prior-same-clinic-shipments
make aged-customer-prior-same-clinic-shipments CACHED=1
make aged-customer-prior-same-clinic-shipments PRINT_SQL=1
make aged-customer-prior-same-clinic-shipments START_DATE=2026-08-15 END_DATE=2026-10-15 AS_OF_DATE=2026-10-27
```

Uses CMPU vet-diet CUSTOMER_UPLOAD prescriptions created in the UTC start-inclusive/end-exclusive window, joined by both first-order keys to recorded Aged Order cancellations on or before AS_OF_DATE at 00:00 UTC. The baseline contains 20,587 known customers. Compare ORDER_LINE_COST_MEASURES_RXP.CLINIC_ID on both aged and historical shipped lines, requiring shipment strictly before that aged order placement. Exclude every qualifying aged-cancelled ORDER_ID and all its lines. Collapse shipment rows and preserve all clinic associations before unique-customer counting; validate UTC/Eastern placement companions where populated. Prescription clinic IDs are comparison fields only; there is no fallback. Historical RX_ID/customer validation and unrestricted historical source/channel/product/pet rules remain unchanged. Count each customer once if a prior shipped prescription from any aged-order clinic is observed. The four exclusive groups are observed prior same-clinic shipment, only other recorded clinics, no qualifying prior prescription shipments, and Unknown, with positive-match precedence: an observed match counts even if another reference is incomplete; otherwise missing clinic/placement or unresolved prior RX/customer/clinic records make the customer Unknown. Null clinic IDs never match. Conflicting populated shipment-row clinic IDs stop publication. Unknown-reason counts can overlap. Clinic familiarity is distinct from an individual-vet match.

Live aged-side coverage is 26,443/26,443 lines and all 20,587 customers, with zero populated clinic conflicts. SQL is in `src/sql/aged_customer_prior_same_clinic_shipments.sql`. The dedicated target uses separate data/SQL-history roots named `aged-customer-prior-same-clinic-shipments` and an `_order-line-clinic` variant. Generated SQL/history remain under `src/autogenerated/`, complete extracts/evidence/customer/clinic/coverage/audit tables and fingerprints under `data/`, and bounded descriptive Markdown under dated `outputs/tables/` folders. Source metadata and cache validation explicitly identify CLINIC_ID; clinic outputs use clinic field names/labels and retain the original vet-diet product flag. No chart is generated.

The fresh snapshot contains the same 20,587 customers: prior same-clinic shipments 15,974 (77.59% of all customers; 77.69% of assessable customers); prior shipments with other recorded clinics only 1,335 (6.48% / 6.49%); no qualifying prior prescription shipments 3,253 (15.80% / 15.82%); Unknown 25 (0.12%). The assessable denominator is 20,562. Unknown reasons are historical RX/customer mismatches for 24 customers and missing historical clinic ID for one customer. Historical line/prescription clinic IDs disagree on 3,712 populated records; comparisons use the line field throughout. All 6,436 aged-side clinic IDs are retained, and cohort membership matches the frozen aged population exactly.

## Clinic history among 21-day reordered customers (REFNUM 43)

```bash
make aged-customer-21d-reorder-clinic-history
make aged-customer-21d-reorder-clinic-history CACHED=1
make aged-customer-21d-reorder-clinic-history PRINT_SQL=1
make aged-customer-21d-reorder-clinic-history START_DATE=2026-08-15 END_DATE=2026-10-15 AS_OF_DATE=2026-10-27
```

Uses validated saved outputs from `make aged-order-reorder-windows MATCH_PET=1 INCLUDE_21_DAYS=1` and `make aged-customer-prior-same-clinic-shipments`, using identical date options. Both normal and CACHED=1 runs regenerate this distribution from frozen inputs without querying Snowflake; missing/stale inputs require refreshing the prerequisite targets. PRINT_SQL=1 prints the two prerequisite extraction queries without reading caches or exporting files; there is no new warehouse query for this subgroup calculation.

Select customers with a same-customer/product/pet reorder placed strictly after cancellation and within 21 days, inclusive of the upper boundary. Require complete 21-day follow-up at AS_OF_DATE 00:00 UTC (default cancellation cutoff October 6, 2026 at 00:00 UTC). Count each reordered customer once; retain the established shortest-delay representative pair in customer detail. Clinic classifications are unchanged from REFNUM 42 and consider all of each customer's qualifying aged-order clinics and placement cutoffs, including aged orders other than the representative reorder anchor. This is a customer-population subset, not a recalculation restricted to the one order that led to the selected reorder. Unknown remains distinct from no qualifying prior shipments.

Exports contain the four-group distribution with all-reordered and assessable-reordered percentages, a comparison with all aged customers, individual reordered customer/reference details, and denominator audits. Source SQL/options, raw-source and exported-input fingerprints are validated before joining; missing clinic customers or duplicate classifications stop publication. Source/output hashes and complete Parquet files live under `data/aged-customer-21d-reorder-clinic-history/`; bounded descriptive Markdown tables go directly under dated `outputs/tables/` folders. No chart is generated.

Default snapshot: 5,382 reordered customers among 15,544 eligible complete-follow-up customers. Prior same-clinic shipments: 4,244 (78.86% of reordered customers); other-clinic-only: 306 (5.69%); no qualifying prior prescription shipments: 829 (15.40%); Unknown: 3 (0.06%). The assessable reordered denominator is 5,379. Each customer appears once, and the distribution sums to 5,382.

### Markdown export size limit

Every generated `.md` file is limited to **1,000,000 bytes (1 MB)**. Large tables produce an explicitly labeled preview of up to 25 rows; complete records remain in the analysis's `data/` Parquet extracts. A final file-level check also bounds reports containing several tables or long notes. Small Markdown exports and non-Markdown outputs retain their existing contents.

Python generators use `markdown_table(frame)` for bounded table formatting and `write_text(path, text)` from `src.python.markdown_tables` for text exports. The writer applies the size cap only to `.md` files; SQL, JSON, Mermaid, SVG and other text exports pass through unchanged. Keep these helpers when adding generators. Existing large Markdown files were removed; Parquet data, figures and compact summaries are retained. Regenerating an analysis now produces only size-limited Markdown previews and summaries.

## REFNUM 51: upload-entity state-change distributions

```bash
make cmpu-upload-entity-state-change-distributions
make cmpu-upload-entity-state-change-distributions CACHED=1
make cmpu-upload-entity-state-change-distributions PRINT_SQL=1
# Optional window overrides (END_DATE is exclusive):
make cmpu-upload-entity-state-change-distributions START_DATE=2026-08-15 END_DATE=2026-10-15 UPLOAD_START_DATE=2026-08-01 AS_OF_DATE=2026-10-27
```

Counts each distinct `UPLOAD_ID` once in each of two populations: all entities linked by expanded RX_ID and numeric customer ID to CMPU vet-diet CUSTOMER_UPLOAD prescriptions, and entities with any matched prescription whose first-order line has an Aged Order cancellation at/before AS_OF_DATE 00:00 UTC. Both first-order keys must match. No line-status condition is added. Defaults cover Rx creation August 15–October 14 inclusive and upload creation August 1–October 25 inclusive (exclusive END_DATE + 11 days). Null upload creation dates are retained and explicitly marked as having unknown discovery-window membership.

Elapsed time is current `STATE_CHANGED_TS_UTC − CREATED_TS_UTC`, in hours. Every current state and every matching upload is retained, without the ACCEPTED filter, earliest-upload selection, 60-second chart restriction, or censoring state changes at cancellation/cutoff. Exact duplicates collapse; conflicting entity states/timestamps/customers or prescription/cancellation evidence fail validation. Missing timestamps remain in exports/audits and are omitted from duration marks; negative durations remain in the plots with flags in data.

Two transparent Altair PNGs under `outputs/charts/<dated-window>/cmpu-upload-entity-state-change-distributions/` show horizontal box plots with a shared state order, palette, and full-range symmetric-log hours axis (one-second linear-region constant). State names are JSON-quoted to distinguish literal values from `[NULL state]`. Medians, linearly interpolated quartiles, observed Tukey whiskers (1.5×IQR), all outliers, and usable/total counts are shown. Empty state groups remain visible with zero counts.

Complete source expansions, matched prescription/line associations, both entity populations, state statistics and audits are Parquet files under `data/cmpu-upload-entity-state-change-distributions/<period>/`. Bounded Markdown statistics, summary previews and audits are under the matching dated `outputs/tables/` folder. Source manifests validate dates, cutoff, population definitions, implementation/SQL fingerprints, and source Parquet SHA-256; analysis manifests fingerprint all exported Parquets. Changes to the query or implementation create a distinct cache identity. `CACHED=1` requires that exact extract; `PRINT_SQL=1` performs no extraction or output writes, even with `CACHED=1`. This target does not regenerate other analyses.

REFNUM 51 x-axis labels use 1, 5 and 30 minutes; 1, 6, 24, 48, 72, 120 and 240 hours. Both plots retain their shared symmetric-log scale and full observed range; horizontal two-line labels show the requested time intervals directly.

REFNUM 51 overwrites `all-study-linked.png` and `aged-order.png` in that stable chart folder on every run. Markdown summaries likewise overwrite files under `outputs/tables/<dated-window>/cmpu-upload-entity-state-change-distributions/`. Checksums remain in the data-cache paths and metadata only.

## REFNUM 52: upload creation relative to order creation

```bash
make cmpu-upload-entity-order-creation-distributions
make cmpu-upload-entity-order-creation-distributions CACHED=1
make cmpu-upload-entity-order-creation-distributions PRINT_SQL=1
```

Accepts START_DATE, exclusive END_DATE, UPLOAD_START_DATE and AS_OF_DATE with the REFNUM 51 defaults. One transparent figure contains two horizontal boxplots: Overall and Aged orders. Elapsed hours = upload CREATED_TS_UTC − order ORDER_PLACED_DTTM; positive means upload after order, negative means upload before order. The study uses order placement, rather than order-line creation, as order creation. Every matching current upload state is retained.

Each UPLOAD_ID counts once per population, using its earliest populated matched first-order placement; multiple-order entities are flagged. Aged entities qualify through any aged first-order association at/before AS_OF_DATE 00:00 UTC, and use the same entity-level reference as overall. All entity/prescription/line associations remain in Parquet. Missing timestamps remain in details/audits and are excluded only from plotted durations; negative durations and all outliers remain plotted. Shipment placement conflicts fail validation. Quartiles use linear interpolation and whiskers use observed values within 1.5×IQR fences. Signed minute/hour ticks use a shared symmetric-log scale with a one-second linear region.

Stable figure: `outputs/charts/<dated-window>/cmpu-upload-entity-order-creation-distributions/overall-and-aged-orders.png`. Complete source/associations/entities/population rows/statistics/audits are under `data/cmpu-upload-entity-order-creation-distributions/<dated-parameters>/`, with bounded Markdown under the matching dated `outputs/tables/` analysis folder. Reruns overwrite outputs. Cache manifests check dates, SQL, version and source SHA-256; analysis metadata fingerprints exported data. This independent target preserves existing REFNUM 51 figures.

## Study-population table: uploaded documents (REFNUM 54)

The two document columns in `tab:study-population-counts` count distinct linked DIET_PRESCRIPTION UPLOAD_IDs for each row's matched first-order-line population. The Total column includes every current state; Accepted requires current STATE_NAME = ACCEPTED. Prescriptions are created August 15–October 14, 2026, uploads August 1–October 25, 2026, UTC; aged cancellations are at/before October 27, 2026, 00:00 UTC. Entities shared by prescriptions count once per row. Counts differ from REFNUM 51 overall, which also retains entities without matched first-order lines.

Read-only extraction and independent aggregation checks:

```bash
.venv/bin/python .agents/skills/rxp-sql/scripts/run_snowflake_query.py src/sql/cmpu_study_population_uploaded_documents.sql --output-parquet data/cmpu-study-population-uploaded-documents/source.parquet --sql-log-dir src/autogenerated/cmpu-study-population-uploaded-documents/sql-history
.venv/bin/python scripts/summarize_study_population_uploaded_documents.py --export
make report
```

The summary script validates the source fingerprint in `data/cmpu-study-population-uploaded-documents/source.json`, checks matched prescription/order/line membership against the report's baseline extract, and independently reconciles Pandas and DuckDB distinct counts. Source metadata records SQL, query ID, extraction time and Parquet fingerprint; update that metadata after any fresh extraction. Derived associations, counts and audits remain in that data folder, with bounded Markdown under `outputs/tables/2026-08-15_2026-10-14/study-population-uploaded-documents.md`. Current counts are all channels 30,735 total / 26,254 accepted; CUSTOMER_UPLOAD 29,715 / 25,606; aged subset 782 / 52.

## Prescription outcome table (REFNUM 55)

`tab:study-population-prescription-decisions` uses the same frozen matched-first-order prescription membership as `tab:study-population-counts`. Current approval/denial evidence is extracted with `src/sql/cmpu_study_population_prescription_decisions.sql`; the baseline is the October 28 REFNUM 14 line-source extract. The summary validates first-order pairs, channels, source fingerprints, shipment flag/reason consistency, distinct prescription identity and registry/line approval agreement. One newly linked current prescription is excluded and audited to retain the existing table populations.

Approved means registry APPROVED_NUMERATOR TRUE, which the certified line-view metadata defines as the source of PRESCRIPTION_APPROVED. Rejected means current RX_STATUS DENIED without an approval flag. Unknown is the remainder, including cancelled and pending prescriptions. A false approval flag alone does not establish rejection. Historical denial timestamps do not override a current approved or pending status. Approval takes precedence when an approval flag and DENIED status coexist. Dedicated timestamps and lifecycle labels remain in the full exports for auditing. Decisions use the current source snapshot, without an approval/denial-date cutoff; only aged cohort cancellation uses the October 27, 2026, 00:00 UTC cutoff.

After extraction, preserve the SQL, query ID, timestamp and source SHA-256 in `data/cmpu-study-population-prescription-decisions/source.json`. To summarize the fingerprint-verified extract and validate the existing cohort:

```bash
.venv/bin/python scripts/summarize_study_population_prescription_decisions.py
make report
```

The script independently reconciles Pandas and DuckDB distinct counts, exports `prescriptions.parquet`, `summary.parquet`, `unknown-status-audit.parquet`, and `excluded-newly-linked-prescriptions.parquet`, and fingerprints these in `analysis.json`. A bounded Markdown summary/audit is saved as `outputs/tables/2026-08-15_2026-10-14/study-population-prescription-decisions.md`. Table categories are mutually exclusive and exhaustive within each row. Current Approved / Unknown / Rejected counts: all channels 36,874 / 66,595 / 47; CUSTOMER_UPLOAD 30,504 / 64,569 / 0; aged subset 6 / 26,437 / 0.

The report includes both REFNUM 51 upload-entity state-change figures via `src/latex/appendix/entity_upload_analysis.tex`, under the placeholder subsection `Bogus`. Figures have captions and labels `fig:entity-upload-state-time-overall` and `fig:entity-upload-state-time-aged`; the executive-summary references point to these labels. Regenerate the stable PNGs with `make cmpu-upload-entity-state-change-distributions CACHED=1` and rebuild with `make report`.

The same appendix file also includes the REFNUM 52 overall/aged-order comparison PNG with label `fig:entity-upload-vs-order-creation`. Its source is the stable `overall-and-aged-orders.png` from `make cmpu-upload-entity-order-creation-distributions CACHED=1`.

`src/latex/appendix/approval_analysis.tex` contains the Approval Analysis subsection and the cumulative accepted-upload-to-approval figure, labelled `fig:accepted-upload-to-approval-cumulative`. It uses the existing `accepted-state-change_order-placed_cumulative.png` output of `make cmpu-upload-to-approval-distribution CACHED=1`. The caption documents the conditional 0–60-second display and omission of longer gaps. Rebuild the report with `make report`.

## Oppurtunity Analysis

### Orders, line items and actual revenue by cancellation reason

```bash
# Fresh read-only extraction and standalone table generation:
make opportunity-order-cancellation-summary
# Reuse the validated extract and overwrite the same table/detail files:
make opportunity-order-cancellation-summary CACHED=1
# Override the UTC order-placement window; END_DATE is exclusive:
make opportunity-order-cancellation-summary START_DATE=2026-06-01 END_DATE=2026-09-01
# Print SQL only, without extracting or writing outputs:
make opportunity-order-cancellation-summary PRINT_SQL=1
```

The defaults include orders placed June 1 through August 31, 2026. Select every physical vet-diet order line with any RX_ID and numeric-customer-ID match to a vet-diet RXP_PRESCRIPTIONS record whose approval channel is CUSTOMER_UPLOAD and prescription source is CMPU. The registry supplies the eligibility fields; line-view channel/status and source-match evidence are retained for audit. Include subsequent orders and prescriptions created outside the placement window. Order status, prescription creation, and cancellation dates impose no additional filter. Only qualifying lines contribute revenue, including on orders containing other products. Other-channel, other-source, unmatched-prescription and customer-mismatched lines remain in the raw extract/audit, outside qualifying totals.

The summary contains Order cancellation reason, distinct Orders, distinct physical Line items, and Net sales, plus a global TOTAL. Reasons are trimmed and grouped case-insensitively. Blank/null reasons form [No recorded cancellation reason], which does not by itself establish an uncancelled order. An order can appear in several reason rows if its qualifying lines have different reasons; group order counts can then overlap, while TOTAL always counts the order once. Each physical line belongs to one reason, so line and revenue totals remain additive. Conflicting reasons, customer IDs or placement timestamps within a physical line fail validation.

**Revenue grain:** sum ORDER_LINE_NET_SALES once per shipment/order-line source record. A split shipment carries a separate contribution, even when two shipment amounts are equal. Repeated financial keys with identical amounts collapse; conflicting amounts for the same key fail validation. Prescription joins cannot multiply money. The source field is NUMBER(28,5); extraction preserves its exact decimal representation and exported monetary columns use DECIMAL(38,5). Only display is rounded to two decimal places. Net sales are reported as supplied, without an assumed currency symbol. Site, legal-company and transaction context are retained in the source and a site-context audit. Negative/refund and zero amounts remain included. A missing sales amount makes the affected line, reason subtotal and global revenue total incomplete; exact known subtotals and missing counts remain exported. This table is the actual-sales baseline for later financial opportunity sizing.

Stable outputs, overwritten on rerun:

- Summary: `outputs/tables/opportunity/<start>_<last-inclusive-day>/order-cancellation-summary.md`.
- Audit and explicitly bounded line preview: the same table folder.
- Source, query/history, source manifest, associations, unique shipment records, physical order lines, summary and audit Parquets: `data/opportunity/order-cancellation-summary/<start>_<exclusive-end>/`.
- Analysis metadata includes extraction provenance, source and export SHA-256 fingerprints, and the SQL/parameters used for independent verification.

`CACHED=1` validates dates, fixed eligibility criteria, definition version, SQL and source fingerprint. Presentation-only edits do not invalidate an otherwise identical raw extract. A failed validation leaves the fresh source without a valid cache manifest. `PRINT_SQL=1` is read-only even when combined with `CACHED=1`. The existing repository Snowflake runner is used; an expired cached ADBC ID token can be refreshed through the installed Snowflake browser-SSO connector using the same account, role and SQL.

Related future charts belong under `outputs/charts/opportunity/`, and diagrams under `outputs/diagrams/opportunity/`, with stable descriptive filenames. This target creates only tables and data and does not modify the existing report or regenerate earlier analyses.

Verification:

```bash
.venv/bin/python -m pytest tests/test_opportunity_order_cancellation_summary.py -q
```

Every fresh or cached run independently recomputes distinct counts and exact revenue from the raw extract in DuckDB before publishing the table. Tests cover date boundaries, all-order membership, eligibility and customer matching, split shipments with equal/unequal amounts, duplicate registry/association/source records, null shipment keys, missing/negative/zero revenue, decimal precision, blank/case-varied/conflicting reasons, mixed-reason order totals, empty cohorts, stable exports, cache rejection and SQL-only mode.

Default June–August 2026 snapshot: 508,075 distinct orders, 569,872 qualifying line items and 46,719,345.94 in net sales. The Aged order row contains 40,014 orders, 43,660 lines and 3,633,444.49. All 15 reason/total rows reconcile independently; no missing sales or overlapping reason-group orders were found in this snapshot. Negative and zero sales remain included.

For the all-orders comparison using prescriptions created August 15–October 14, retain the original inclusive aged-cancellation cutoff of October 27, 2026, 00:00 UTC. The saved comparison is `outputs/tables/opportunity/2026-08-15_2026-10-14/prescription-cohort-order-cancellations.md`, with source, line details, cutoff membership and fingerprints under `data/opportunity/prescription-cohort-orders/2026-08-15_2026-10-15/`. Qualifying aged counts are 24,409 orders and 26,445 lines (21.18%). Current aged reasons outside the cutoff remain a separate audit row and are excluded from qualifying aged counts. All-order totals remain 111,137 orders and 124,886 lines; this is an aged-membership cutoff, not a historical-status reconstruction or order-placement cutoff. Compared with first orders at the same cutoff, the increase is one aged order and two aged lines.

To regenerate the appendix comparison by cancellation reason (first-order and all-order counts, physical lines and net sales), use the fingerprint-verified Aug 15–Oct 14 prescription cohort and the same inclusive Oct 27, 2026, 00:00 UTC aged cutoff:

```bash
make prescription-cohort-order-comparison
make report
```

Use `make prescription-cohort-order-comparison CACHED=1` to validate and reuse cached financial data. The target updates the appendix table, Parquet exports and Markdown summary; run `make report` afterward to rebuild the PDF. This target uses the fixed, fingerprint-verified cohort and cutoff described above. For exports without changing the appendix, run `.venv/bin/python scripts/summarize_prescription_cohort_order_comparison.py` (add `--refresh` for fresh sales). Read-only SQL is in `src/sql/prescription_cohort_order_sales.sql`; frozen-key requests, source fingerprints, shipment details, exact-decimal line/summary Parquet, and independent DuckDB verification are under `data/opportunity/prescription-cohort-order-comparison/2026-08-15_2026-10-15_as-of-2026-10-27/`. The Markdown table is `outputs/tables/opportunity/2026-08-15_2026-10-14/first-all-order-cancellation-comparison.md`. The PDF table is labelled `tab:first-all-order-cancellations`.

Net sales sum unique shipment-and-line contributions for qualifying lines, preserving negative/zero values and five-decimal precision. Missing sales are shown as incomplete; they are never silently treated as zero. Independent source-based SQL verifies every reason and both totals. The comparison snapshot contains 87,725 first orders / 95,074 first lines (one additional matched line/order versus the earlier frozen study table), and 111,137 all orders / 124,886 lines. Net sales are refreshed from `ORDER_LINE_NET_SALES` (see the exported summary for current totals). First orders are included in all orders; do not add the columns together.

To insert the opportunity order-cancellation summary into the report's Financial Opportunity Analysis appendix:

```bash
make opportunity-order-cancellation-summary CACHED=1 WRITE_LATEX=1
make report
```

Omit `CACHED=1` to refresh data first. `START_DATE` and exclusive `END_DATE` control the UTC order-placement window (defaults June 1–August 31, 2026 inclusive). `WRITE_LATEX=1` overwrites `src/latex/appendix/financial_opportunity.tex` from the verified summary, including the dates, CMPU prescription source, CUSTOMER_UPLOAD approval channel, vet-diet criteria, caption and label `tab:financial-opportunity-cancellations`. The file is included in the report. This all-orders baseline has no prescription-creation or cancellation-date cutoff; its population differs from the August–October prescription cohort. Sales use `ORDER_LINE_NET_SALES`, preserving the shipment-and-line financial grain.
