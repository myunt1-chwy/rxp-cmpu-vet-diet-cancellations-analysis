"""Reusable sql listing format helpers; no analysis CLI."""

import sqlparse


def format_sql(sql, source_name):
    """Format listings without changing SQL tokens."""
    formatted = (
        sqlparse.format(sql, keyword_case="upper", reindent=False).rstrip()
        + "\n"
    )

    def tokens(text):
        return [
            token.normalized
            for statement in sqlparse.parse(text)
            for token in statement.flatten()
            if not token.is_whitespace
        ]

    if tokens(sql) != tokens(formatted):
        raise ValueError(f"SQL formatting changed tokens in {source_name}")
    return formatted
