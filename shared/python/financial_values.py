"""Exact identifiers, money and dates for financial analyses."""

from datetime import date
from decimal import Decimal, InvalidOperation, localcontext

import pandas as pd

SCALE = Decimal("0.00001")
ZERO = Decimal("0.00000")


def parameters(start, end, date_basis="placed"):
    start, end = date.fromisoformat(start), date.fromisoformat(end)
    if start >= end:
        raise ValueError("start date must precede exclusive end date")
    if date_basis not in ["placed", "shipped-or-cancelled"]:
        raise ValueError("invalid date basis")
    result = {"start_date": str(start), "end_date": str(end)}
    if date_basis != "placed":
        result["date_basis"] = date_basis
    return result


def identifier(value):
    if pd.isna(value):
        return None
    try:
        number = Decimal(str(value))
        if (
            not number.is_finite()
            or number != number.to_integral_value()
            or number < 0
        ):
            raise ValueError("invalid numeric identifier")
        return str(int(number))
    except InvalidOperation as error:
        raise ValueError("invalid numeric identifier") from error


def money(value):
    if pd.isna(value):
        return None
    if isinstance(value, float):
        raise ValueError(  # noqa: TRY004 -- Preserve the validation API.
            "floating-point sales amounts are not supported; extract "
            "exact strings"
        )
    try:
        amount = Decimal(str(value))
        with localcontext() as context:
            context.prec = 50
            scaled = amount.quantize(SCALE)
        if (
            not amount.is_finite()
            or amount != scaled
            or abs(scaled) >= Decimal("1e33")
        ):
            raise ValueError("invalid sales precision or range")
        return scaled
    except InvalidOperation as error:
        raise ValueError("invalid sales amount") from error


def decimal_sum(values):
    with localcontext() as context:
        context.prec = 50
        return sum(
            (v for v in values if v is not None and not pd.isna(v)), ZERO
        )
