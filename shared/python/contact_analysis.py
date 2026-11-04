"""Reusable contact analysis helpers; no analysis CLI."""

import duckdb
import pandas as pd
from jinja2 import Environment, StrictUndefined

from shared.paths import canonical_sql_path
from shared.python import financial_values as base
from shared.sql_templates import module_sql

MIN_DAY = -13


MAX_DAY = 3


DAY_NS = 86_400_000_000_000


ORDER_COLUMNS = [
    "order_id",
    "customer_id",
    "cancelled_at_utc",
    "registry_variants",
    "qualifying_lines",
    "customer_variants",
    "cancellation_variants",
]


def render_sql(start, end):
    return (
        Environment(undefined=StrictUndefined)
        .from_string(
            (
                canonical_sql_path("opportunity_aged_customer_contacts.sql")
            ).read_text()
        )
        .render(
            **base.parameters(start, end), min_day=MIN_DAY, end_day=MAX_DAY + 1
        )
    )


def analyze(raw, start, end, handled_only=False):
    f = raw.rename(columns=str.lower).copy()
    for col in [
        "order_id",
        "customer_id",
        "contact_order_id",
        "contact_customer_id",
    ]:
        f[col] = f[col].map(base.identifier)
    for col in ["cancelled_at_utc", "contact_at_utc"]:
        f[col] = pd.to_datetime(f[col], utc=True, format="mixed").astype(
            "datetime64[ns, UTC]"
        )
    if f[["order_id", "customer_id", "cancelled_at_utc"]].isna().any().any():
        raise ValueError("missing aged-order keys/timestamps")
    if (
        f[["registry_variants", "customer_variants", "cancellation_variants"]]
        .ne(1)
        .any()
        .any()
    ):
        raise ValueError("conflicting aged source values")
    if not f.cancelled_at_utc.between(
        pd.Timestamp(start, tz="UTC"),
        pd.Timestamp(end, tz="UTC"),
        inclusive="left",
    ).all():
        raise ValueError("cancellation outside requested window")
    if (
        f.groupby("order_id")[ORDER_COLUMNS[1:]]
        .nunique(dropna=False)
        .gt(1)
        .any()
        .any()
    ):
        raise ValueError("conflicting aged order evidence")
    orders = f[ORDER_COLUMNS].drop_duplicates("order_id").copy()
    contacts = f.loc[f.contact_order_id.notna()].copy()
    if not contacts.contact_order_id.eq(contacts.order_id).all():
        raise ValueError("contact order ID differs")
    contacts["direction"] = (
        contacts.session_initial_direction.astype("string")
        .str.strip()
        .str.lower()
    )
    known = contacts.loc[contacts.leg_id.notna() & contacts.session_id.notna()]
    source_fields = [
        "session_id",
        "contact_customer_id",
        "contact_at_utc",
        "direction",
        "handled_flag",
        "session_channel",
        "session_ingress_point",
    ]
    if (
        known.groupby(["contact_order_id", "session_id", "leg_id"])[
            source_fields
        ]
        .nunique(dropna=False)
        .gt(1)
        .any()
        .any()
    ):
        raise ValueError("conflicting contact leg evidence")
    duplicates = int(contacts.duplicated().sum())
    contacts = contacts.drop_duplicates().copy()
    elapsed = (
        (contacts.contact_at_utc - contacts.cancelled_at_utc)
        .astype("int64")
        .astype("Int64")
    )
    elapsed.loc[contacts.contact_at_utc.isna()] = pd.NA
    contacts["elapsed_ns"] = elapsed
    contacts["relative_day"] = elapsed // DAY_NS
    dated = contacts.contact_at_utc.notna()
    if not contacts.loc[dated, "relative_day"].between(MIN_DAY, MAX_DAY).all():
        raise ValueError("contact outside extracted day window")
    contacts["customer_identity"] = pd.Series(
        "Matching customer", index=contacts.index, dtype="str"
    )
    contacts.loc[contacts.contact_customer_id.isna(), "customer_identity"] = (
        "Missing contact customer"
    )
    contacts.loc[
        contacts.contact_customer_id.notna()
        & contacts.contact_customer_id.ne(contacts.customer_id),
        "customer_identity",
    ] = "Different contact customer"
    contacts["included"] = (
        contacts.direction.eq("inbound").fillna(False)
        & contacts.customer_identity.eq("Matching customer")
        & dated
    )
    if handled_only:
        contacts["included"] = contacts.included & contacts.handled_flag.eq(
            True
        ).fillna(False)
    selected = contacts.loc[contacts.included]
    counts = selected.groupby("relative_day").agg(
        distinct_customers=("customer_id", "nunique"),
        distinct_aged_orders=("order_id", "nunique"),
    )
    daily = (
        pd.DataFrame({"relative_day": range(MIN_DAY, MAX_DAY + 1)})
        .merge(counts, on="relative_day", how="left")
        .fillna(0)
    )
    for col in ["distinct_customers", "distinct_aged_orders"]:
        daily[col] = daily[col].astype("int64")
    per_customer = (
        orders[["customer_id"]]
        .drop_duplicates()
        .merge(
            selected.groupby("customer_id")
            .relative_day.nunique()
            .rename("days_contacted"),
            on="customer_id",
            how="left",
        )
        .fillna({"days_contacted": 0})
    )
    per_customer.days_contacted = per_customer.days_contacted.astype("int64")
    frequency = (
        pd.DataFrame({"days_contacted": range(MAX_DAY - MIN_DAY + 2)})
        .merge(
            per_customer.groupby("days_contacted")
            .size()
            .rename("distinct_customers"),
            on="days_contacted",
            how="left",
        )
        .fillna(0)
    )
    frequency.distinct_customers = frequency.distinct_customers.astype("int64")
    verify = module_sql(
        __file__,
        "create_opportunity_aged_customer_contacts-query-1.sql.j2",
        min_day=MIN_DAY,
        end_day=MAX_DAY + 1,
        handled_only=handled_only,
    )
    independent = contacts.copy()
    independent["contact_time_sql"] = (
        independent.contact_at_utc.dt.tz_localize(None)
    )
    independent["cancellation_time_sql"] = (
        independent.cancelled_at_utc.dt.tz_localize(None)
    )
    with duckdb.connect() as c:
        c.execute("SET TimeZone='UTC'")
        c.register("contacts", independent)
        expected = c.execute(verify).df()
        c.register("aged_orders", orders)
        frequency_expected = c.execute(
            module_sql(
                __file__,
                "create_opportunity_aged_customer_contacts-query-2.sql.j2",
                end_count=MAX_DAY - MIN_DAY + 2,
                handled_only=handled_only,
            )
        ).df()
    pd.testing.assert_frame_equal(daily, expected, check_dtype=False)
    pd.testing.assert_frame_equal(
        frequency, frequency_expected, check_dtype=False
    )
    assert frequency.distinct_customers.sum() == orders.customer_id.nunique()
    assert (
        frequency.loc[
            frequency.days_contacted.gt(0), "distinct_customers"
        ].sum()
        == selected.customer_id.nunique()
    )
    direction = (
        contacts.assign(
            direction=contacts.direction.fillna("[Missing direction]")
        )
        .groupby(["direction", "handled_flag"], dropna=False)
        .agg(
            contact_rows=("order_id", "size"),
            distinct_customers=("customer_id", "nunique"),
            distinct_aged_orders=("order_id", "nunique"),
        )
        .reset_index()
    )
    identity = (
        contacts.groupby("customer_identity")
        .size()
        .rename("contact_rows")
        .reset_index()
    )
    channels = (
        selected.groupby(
            ["session_channel", "session_ingress_point"], dropna=False
        )
        .agg(
            contact_rows=("order_id", "size"),
            distinct_customers=("customer_id", "nunique"),
            distinct_aged_orders=("order_id", "nunique"),
        )
        .reset_index()
    )
    audit = {
        "aged_customers": orders.customer_id.nunique(),
        "aged_orders": len(orders),
        "qualifying_lines": int(orders.qualifying_lines.sum()),
        "contact_rows_in_extracted_window": len(contacts),
        "identical_contact_duplicates_collapsed": duplicates,
        "inbound_rows": int(contacts.direction.eq("inbound").sum()),
        "outbound_rows": int(contacts.direction.eq("outbound").sum()),
        "unknown_direction_rows": int(
            (~contacts.direction.isin(["inbound", "outbound"])).sum()
        ),
        "missing_contact_customer_rows": int(
            contacts.customer_identity.eq("Missing contact customer").sum()
        ),
        "mismatched_contact_customer_rows": int(
            contacts.customer_identity.eq("Different contact customer").sum()
        ),
        "missing_contact_time_rows": int(contacts.contact_at_utc.isna().sum()),
        "included_contact_rows": len(selected),
        "distinct_customers_contacting": selected.customer_id.nunique(),
        "distinct_aged_orders_with_contacts": selected.order_id.nunique(),
        "handled_only": handled_only,
        "required_days": list(range(MIN_DAY, MAX_DAY + 1)),
        "independent_verification": (
            "DuckDB independently matches every UTC nanosecond-floor "
            "day/customer/order count, including zero rows"
        ),
    }
    return (
        {
            "aged_orders": orders,
            "contact_details": contacts,
            "customer_contact_days": per_customer,
            "contact_day_frequency": frequency,
            "daily_summary": daily,
            "direction_audit": direction,
            "customer_identity_audit": identity,
            "channel_audit": channels,
        },
        audit,
        verify,
    )


def frequency_verification_sql(handled_only):
    return module_sql(
        __file__,
        "create_opportunity_aged_customer_contacts-query-2.sql.j2",
        end_count=MAX_DAY - MIN_DAY + 2,
        handled_only=handled_only,
    )
