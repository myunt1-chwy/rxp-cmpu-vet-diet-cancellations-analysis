"""Reusable first order cohorts helpers; no analysis CLI."""

import hashlib

from jinja2 import Environment, StrictUndefined

from shared.python import financial_values as base
from shared.python.paths import canonical_sql_path

STATUSES = [
    "First order in observed ECOM history",
    "Existing customer",
    "Unknown",
]


SCOPE_LABELS = {
    "chewy": STATUSES[0],
    "vet-diet": "First order in observed vet-diet history",
    "vet-diet-customer-upload": (
        "First observed CMPU CUSTOMER_UPLOAD vet-diet order"
    ),
}


SCOPE_FOLDERS = {
    "chewy": "aged-first-order-customers",
    "vet-diet": "aged-first-vet-diet-order-customers",
    "vet-diet-customer-upload": (
        "aged-first-customer-upload-vet-diet-order-customers"
    ),
}


SCOPE_TEMPLATES = {
    "chewy": "opportunity_aged_first_order_customers.sql",
    "vet-diet": "opportunity_aged_first_vet_diet_order_customers.sql",
    "vet-diet-customer-upload": (
        "opportunity_aged_first_customer_upload_vet_diet_order_customers.sql"
    ),
}


def render_sql(start, end, scope="chewy"):
    return (
        Environment(undefined=StrictUndefined)
        .from_string((canonical_sql_path(SCOPE_TEMPLATES[scope])).read_text())
        .render(**base.parameters(start, end))
    )


def source_identity(params, sql, scope="chewy"):
    identity = dict(
        version=1,
        **params,
        definition="exact earliest placed ECOM order ID; all statuses",
        timezone="UTC",
        sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
    )
    if scope == "vet-diet":
        identity.update(
            scope=scope,
            definition=(
                "exact earliest placed vet-diet ECOM order ID; all statuses"
            ),
        )
    if scope == "vet-diet-customer-upload":
        identity.update(
            scope=scope,
            definition=(
                "exact earliest placed CMPU CUSTOMER_UPLOAD vet-diet order "
                "ID; all statuses"
            ),
        )
    return identity
