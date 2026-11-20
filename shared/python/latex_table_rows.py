"""Reusable latex table rows helpers; no analysis CLI."""


def replace_rows(text, label, rows):
    """Replace computed rows, preserving captions, layout and notes."""
    start = text.index(
        r"\midrule", text.index(r"\label{" + label + "}")
    ) + len(r"\midrule")
    end = text.index(r"\bottomrule", start)
    return text[:start] + "\n" + "\n".join(rows) + "\n" + text[end:]
