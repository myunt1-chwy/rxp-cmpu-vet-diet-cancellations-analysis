"""Adapt warehouse SQL to DuckDB fixtures without depending on formatting."""

import re


def _arguments(text, opening):
    depth = 0
    quoted = False
    parts = []
    start = opening + 1
    for i in range(opening + 1, len(text)):
        char = text[i]
        if char == "'":
            quoted = not quoted
        if quoted:
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                return [*parts, text[start:i].strip()], i + 1
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:i].strip())
            start = i + 1
    raise ValueError("Unclosed SQL function in fixture")


def fixture_sql(sql):
    """Keep matching logic while translating supported warehouse functions."""
    sql = re.sub(
        r"\bedldb(?:\.\w+)+", lambda m: m[0].upper(), sql, flags=re.IGNORECASE
    )
    sql = re.sub(
        r"\),\s+(\w+)\s+AS\s+\(", r"), \1 AS (", sql, flags=re.IGNORECASE
    )
    sql = re.sub(r"\bNUMBER\s*\(", "DECIMAL(", sql, flags=re.IGNORECASE)
    functions = list(
        re.finditer(r"\b(DATEADD|DATEDIFF|TO_CHAR)\s*\(", sql, re.IGNORECASE)
    )
    for match in reversed(functions):
        args, end = _arguments(sql, match.end() - 1)
        name = match[1].upper()
        if name == "TO_CHAR":
            replacement = f"CAST({args[0]} AS VARCHAR)"
        elif name == "DATEDIFF":
            unit, start, finish = args
            if unit.lower() == "nanosecond":
                replacement = f"(epoch_ns({finish}) - epoch_ns({start}))"
            else:
                replacement = f"date_diff('{unit.lower()}', {start}, {finish})"
        else:
            unit, amount, origin = args
            scale = {
                "day": 86400000000000,
                "hour": 3600000000000,
                "nanosecond": 1,
            }[unit.lower()]
            replacement = (
                f"make_timestamp_ns(epoch_ns({origin}) + "
                f"CAST({amount} AS BIGINT) * {scale})"
            )
        sql = sql[: match.start()] + replacement + sql[end:]
    # The extraction expands comma-separated RX IDs with an outer lateral join.
    flatten = re.search(r"LATERAL\s+FLATTEN\s*\(", sql, re.IGNORECASE)
    while flatten:
        args, end = _arguments(sql, flatten.end() - 1)
        expression = re.sub(
            r"^INPUT\s*=>\s*", "", args[0], flags=re.IGNORECASE
        )
        expression = re.sub(
            r"\bSPLIT\s*\(", "string_split(", expression, flags=re.IGNORECASE
        )
        alias = re.match(r"\s+(?:AS\s+)?(\w+)", sql[end:], re.IGNORECASE)
        if alias is None:
            raise ValueError("Missing lateral fixture alias")
        replacement = f"LATERAL UNNEST({expression}) AS {alias[1]}(value)"
        sql = sql[: flatten.start()] + replacement + sql[end + alias.end() :]
        flatten = re.search(r"LATERAL\s+FLATTEN\s*\(", sql, re.IGNORECASE)
    return sql


def sql_contains(sql, fragment):
    """Check SQL fragments independently of whitespace and keyword casing."""
    return (
        re.sub(r"\s+", "", fragment).upper() in re.sub(r"\s+", "", sql).upper()
    )
