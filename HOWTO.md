# Setup

## VDAM upload distribution (REFNUM 1)

Generate the distribution for uploads dated July 30 through October 20, 2026,
inclusive in UTC:

```sh
make create-vdam-upload-distribution START_DATE=2026-07-30 END_DATE=2026-10-21
```

Both dates are required; `END_DATE` is exclusive. The dates filter uploads,
not order placement. Require `UPLOAD_TYPE = 'DIET_PRESCRIPTION'`,
`ASSOCIATED_RESOURCE_TYPE = 'DIET_PRESCRIPTION'`, `HAS_ASSOCIATED_RX = TRUE`,
and `HAS_UPLOADED_FILE = TRUE`. Expand the brace-delimited `RX_ID` list and
deduplicate IDs within each upload; do not use `ASSOCIATED_RX_CNT` as a weight.
Each distinct prescription contributes its earliest qualifying order-linked
upload within the window, joined using the upload table's order ID directly.
For prescriptions linked to multiple orders, use the order on that earliest
matched upload; break timestamp ties by upload ID, then order ID.
`ORDER_PLACED_DTTM` is interpreted as UTC based on its four/five-hour offset
from the Eastern companion column; this is an inference, not a documented
timezone guarantee. No additional timezone shift is applied. Negative elapsed
hours and all outliers remain in the 50 equal-width bins.

The read-only runner uses browser SSO and a local ignored `.env` containing
`RXP_SNOWFLAKE_ACCOUNT`, `RXP_SNOWFLAKE_USER`, `RXP_SNOWFLAKE_DATABASE`,
`RXP_SNOWFLAKE_WAREHOUSE`, `RXP_SNOWFLAKE_SCHEMA`, and optionally
`RXP_SNOWFLAKE_ROLE`. Run `make setup` if dependencies are missing.

Add `PRINT_SQL=1` to print SQL without accessing Snowflake or writing files.
Add `CACHED=1` to redraw from a completed extract with matching dates and SQL.
Downloaded Parquet, executed SQL, and extraction provenance are saved under
`data/vdam-upload-distribution/<start>_<end>/`. The transparent PNG is under
`outputs/charts/vdam-upload-distribution/<start>_<end>/distribution.png`;
the 50-bin Markdown table and reconciliation counts are under
`outputs/tables/vdam-upload-distribution/<start>_<end>/distribution.md`.
All generated outputs are ignored by Git.

The same target also exports `distribution-by-cancel-reason.png` and
`distribution-by-cancel-reason.md` alongside those files. This five-panel chart
uses the same 50 bin boundaries for every group, with independent count scales
and the prescription total in each panel title. The Markdown table includes
group totals and 250 bin rows; bin percentages are within each group.
Five separate transparent figures are also exported to the same chart directory:
`distribution-not-cancelled.png`, `distribution-aged-orders.png`,
`distribution-customer-initiated.png`, `distribution-customer-requested.png`,
and `distribution-other.png`. They retain the shared bin boundaries and use
count scales appropriate to each group. Regenerate them from the existing
extract by adding `CACHED=1` to the Make command.
`ORDER_CANCEL_REASON` is taken from the selected upload's order at extraction
time, not reconstructed as of the upload date. Groups are:

- NULL: Not cancelled.
- `Aged Order`: Aged orders.
- `Customer Initiated Cancellation`: Customer initiated.
- `Customer Request`: Customer requested.
- Every other non-null value: Other.

Reason matching ignores case and leading/trailing whitespace. Prescription
deduplication happens before grouping, so every prescription belongs to exactly
one group. Existing caches without the cancellation-reason column require a
fresh run without `CACHED=1`.

Missing prescription IDs, missing/invalid order IDs, unmatched orders, and
missing order timestamps are reported separately at prescription-upload grain.
Repeated matched uploads are reduced to one observation per prescription.
Duplicate upload/prescription pairs or duplicate order-source rows fail validation
instead of silently multiplying observations. Uploads with missing timestamps
cannot be assigned to a date cohort. Empty results produce a table explaining
the result and no chart; a constant duration uses a one-hour plotting range.

Run the focused checks with:

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_vdam_upload_distribution.py'
```

## Aged-order lifecycle-state distribution (REFNUM 4)

Keep the existing upload cohort and fetch only its latest prescription states:

```sh
make create-aged-upload-lifecycle-distribution START_DATE=2026-07-30 END_DATE=2026-10-21
```

This requires the completed REFNUM 1 upload cache for those dates. It does not
refresh uploads or orders. The current cohort contains 2,220 aged-order
prescriptions, selected after deduplicating prescriptions across all orders.
Both dates are required; the end is exclusive. `PRINT_SQL=1` reads the existing
cohort and prints the lifecycle-state query without querying or writing files.
`CACHED=1` renders saved states without contacting Snowflake; a cohort or SQL
mismatch requires a fresh state lookup. The cohort fingerprint covers selected
prescriptions, their upload/order IDs and delays, and all 50 global bin edges.

States are read from `EDLDB.BT_HCA_HCDM.RXP_PRESCRIPTIONS` by individual `RX_ID`.
The chart shows the latest available state at extraction time, including
nonterminal states; it does not reconstruct the state at upload or cancellation.
Duplicate source IDs stop the run. Unmatched prescriptions and null states are
retained as separate categories. Every stack sums to the existing aged-order
bin count; negative durations and outliers remain included.

The executed SQL, state Parquet, timestamps, and provenance are stored under
`data/vdam-upload-distribution/<start>_<end>/aged-lifecycle/`. The transparent
`distribution-aged-orders-by-lifecycle-state.png` goes in the dated chart
directory. The identically named `.md` file in the dated table directory contains
state totals, cohort percentages, and all bin-by-state counts. Existing figures
are preserved. An empty aged cohort produces an explanatory table and no PNG.

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_aged_upload_lifecycle_distribution.py'
```

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
