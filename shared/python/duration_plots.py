"""Shared duration summaries and explicit Tukey boxplot rendering."""

import json

import altair as alt
import pandas as pd

PALETTE = [
    "#4E79A7",
    "#F28E2C",
    "#E15759",
    "#76B7B2",
    "#59A14F",
    "#B07AA1",
    "#9C755F",
    "#EDC948",
    "#FF9DA7",
    "#BAB0AC",
]


def statistics(entities, states):
    rows = []
    for state in states:
        group = entities.loc[entities.state_label.eq(state)]
        values = group.loc[group.usable_duration, "elapsed_hours"]
        q1, median, q3 = values.quantile(
            [0.25, 0.5, 0.75], interpolation="linear"
        )
        iqr = q3 - q1
        inside = values.loc[values.between(q1 - 1.5 * iqr, q3 + 1.5 * iqr)]
        low, high = inside.min(), inside.max()
        rows.append(
            {
                "state_label": state,
                "entities": len(group),
                "usable": len(values),
                "missing_creation": int(group.missing_creation.sum()),
                "missing_state_change": int(group.missing_state_change.sum()),
                "missing_duration": int((~group.usable_duration).sum()),
                "negative": int(group.negative_duration.sum()),
                "mean": values.mean(),
                "minimum": values.min(),
                "q1": q1,
                "median": median,
                "q3": q3,
                "maximum": values.max(),
                "lower_fence": q1 - 1.5 * iqr,
                "upper_fence": q3 + 1.5 * iqr,
                "lower_whisker": low,
                "upper_whisker": high,
                "outliers": int((values.lt(low) | values.gt(high)).sum()),
            }
        )
    return pd.DataFrame(rows)


def boxplot(entities, stats, states, domain, title, subtitle):
    """Use exported linear quantiles and observed Tukey whiskers."""
    s = stats.copy()
    s["count_label"] = s.apply(
        lambda r: f"n={r.usable:,} / {r.entities:,}", axis=1
    )
    colors = alt.Scale(
        domain=states,
        range=[PALETTE[i % len(PALETTE)] for i in range(len(states))],
    )
    base = alt.Chart(
        alt.Data(values=json.loads(s.to_json(orient="records")))
    ).encode(
        y=alt.Y(
            "state_label:N",
            sort=states,
            title="Final state",
            axis=alt.Axis(labelLimit=260),
        ),
        color=alt.Color("state_label:N", scale=colors, legend=None),
    )
    scale = alt.Scale(
        type="symlog", constant=1 / 3600, domain=domain, nice=False
    )
    tick_hours = [1 / 60, 5 / 60, 30 / 60, 1, 6, 24, 48, 72, 120, 240]
    axis = alt.Axis(
        values=[
            value for value in tick_hours if domain[0] <= value <= domain[1]
        ],
        labelExpr=(
            "datum.value < 1 ? [format(datum.value * 60, '.0f'), datum.value "
            "== 1/60 ? 'minute' : 'minutes'] : [format(datum.value, '.0f'), "
            "datum.value == 1 ? 'hour' : 'hours']"
        ),
        labelAngle=0,
        labelOverlap=False,
        labelLineHeight=16,
        labelPadding=8,
    )

    def x(field):
        return alt.X(
            field + ":Q",
            title="Time from entity creation to current state change",
            scale=scale,
            axis=axis,
        )

    whisker = base.mark_rule(strokeWidth=2).encode(
        x=x("lower_whisker"), x2="upper_whisker:Q"
    )
    caps = [
        base.mark_tick(orient="vertical", size=16, thickness=2).encode(
            x=x(field)
        )
        for field in ["lower_whisker", "upper_whisker"]
    ]
    box = base.mark_bar(size=28, opacity=0.65).encode(x=x("q1"), x2="q3:Q")
    median = base.mark_tick(orient="vertical", size=30, thickness=3).encode(
        x=x("median"), color=alt.value("#222222")
    )
    usable = entities.loc[entities.usable_duration].merge(
        stats[["state_label", "lower_whisker", "upper_whisker"]],
        on="state_label",
    )
    outliers = usable.loc[
        usable.elapsed_hours.lt(usable.lower_whisker)
        | usable.elapsed_hours.gt(usable.upper_whisker)
    ]
    points = (
        alt.Chart(
            alt.Data(
                values=outliers[["state_label", "elapsed_hours"]].to_dict(
                    "records"
                )
            )
        )
        .mark_circle(size=20, opacity=0.35)
        .encode(
            x=x("elapsed_hours"),
            y=alt.Y("state_label:N", sort=states),
            color=alt.Color("state_label:N", scale=colors, legend=None),
        )
    )
    counts = base.mark_text(
        align="left", dx=12, color="#333333", fontSize=13
    ).encode(
        x=alt.value(1500), text="count_label:N", color=alt.value("#333333")
    )
    zero = (
        alt.Chart(pd.DataFrame({"zero": [0]}))
        .mark_rule(color="#888888", strokeDash=[3, 3])
        .encode(x=x("zero"))
    )
    return (
        (zero + whisker + caps[0] + caps[1] + box + median + points + counts)
        .properties(
            width=1500,
            height=max(200, len(states) * 56),
            padding={"left": 10, "right": 160, "top": 10, "bottom": 10},
            title=alt.Title(
                title,
                subtitle=subtitle,
                anchor="start",
                fontSize=23,
                subtitleFontSize=14,
                offset=18,
            ),
        )
        .configure(
            background="transparent",
            font="Arial",
            axis=alt.AxisConfig(
                labelFontSize=13, titleFontSize=16, titlePadding=14
            ),
        )
        .configure_view(stroke=None)
    )
