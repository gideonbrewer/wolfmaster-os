"""Plotly chart builders with a consistent, accessible style.

Palette follows the validated defaults: categorical slot 1 blue #2a78d6,
diverging polarity pair blue #2a78d6 (positive) / red #e34948 (negative),
neutral gray midpoint. One axis per chart, recessive grid, thin marks.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

BLUE = "#2a78d6"
RED = "#e34948"
AQUA = "#1baf7a"
YELLOW = "#eda100"
VIOLET = "#4a3aa7"
GRAY_GRID = "#e8e7e3"
TEXT_SECONDARY = "#5f5e58"

CATEGORICAL = [BLUE, AQUA, YELLOW, "#008300", VIOLET, RED]

_LAYOUT = {
    "template": "plotly_white",
    "margin": {"l": 48, "r": 16, "t": 36, "b": 40},
    "height": 380,
    "font": {"size": 13, "color": "#33322e"},
    "hovermode": "closest",
    "xaxis": {"gridcolor": GRAY_GRID, "zerolinecolor": GRAY_GRID},
    "yaxis": {"gridcolor": GRAY_GRID, "zerolinecolor": "#c9c8c2"},
}


def _fig(title: str, **overrides: object) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(**{**_LAYOUT, "title": {"text": title, "font": {"size": 15}}})
    if overrides:
        fig.update_layout(**overrides)
    return fig


def polarity_colors(values: pd.Series) -> list[str]:
    """Blue for >= 0, red for < 0 (diverging polarity pair)."""
    return [BLUE if v >= 0 else RED for v in values]


def equity_curve_chart(curve: pd.DataFrame, title: str = "Equity curve") -> go.Figure:
    fig = _fig(title, hovermode="x unified")
    if not curve.empty:
        fig.add_scatter(
            x=curve["ts"],
            y=curve["equity"],
            mode="lines",
            name="Equity",
            line={"color": BLUE, "width": 2},
            hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>",
        )
        fig.add_scatter(
            x=curve["ts"],
            y=curve["peak"],
            mode="lines",
            name="Peak",
            line={"color": TEXT_SECONDARY, "width": 1, "dash": "dot"},
            hovertemplate="peak $%{y:,.0f}<extra></extra>",
        )
    fig.update_yaxes(title_text="Cumulative P&L ($)")
    return fig


def drawdown_chart(curve: pd.DataFrame) -> go.Figure:
    fig = _fig("Drawdown", hovermode="x unified")
    if not curve.empty:
        fig.add_scatter(
            x=curve["ts"],
            y=-curve["drawdown"],
            mode="lines",
            name="Drawdown",
            line={"color": RED, "width": 2},
            fill="tozeroy",
            fillcolor="rgba(227,73,72,0.15)",
            hovertemplate="%{x}<br>-$%{customdata:,.0f}<extra></extra>",
            customdata=curve["drawdown"],
        )
    fig.update_yaxes(title_text="Drawdown ($)")
    return fig


def bar_chart(
    data: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    y_title: str,
    polarity: bool = True,
    x_title: str = "",
) -> go.Figure:
    fig = _fig(title)
    if not data.empty:
        colors = polarity_colors(data[y]) if polarity else BLUE
        fig.add_bar(
            x=data[x].astype(str),
            y=data[y],
            marker={"color": colors, "line": {"width": 0}},
            hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>",
        )
        fig.update_layout(bargap=0.35)
    fig.update_yaxes(title_text=y_title)
    if x_title:
        fig.update_xaxes(title_text=x_title)
    return fig


def histogram_chart(values: pd.Series, title: str, x_title: str) -> go.Figure:
    fig = _fig(title)
    if len(values):
        fig.add_histogram(
            x=values,
            marker={"color": BLUE, "line": {"color": "#ffffff", "width": 1}},
            hovertemplate="%{x}<br>%{y} trades<extra></extra>",
        )
    fig.update_xaxes(title_text=x_title)
    fig.update_yaxes(title_text="Trades")
    return fig


def excursion_scatter(df: pd.DataFrame, excursion_col: str, title: str, x_title: str) -> go.Figure:
    """MFE/MAE (x) vs realized return (y), colored by outcome polarity."""
    fig = _fig(title)
    sub = df[[excursion_col, "return_pct", "underlying_symbol"]].dropna(
        subset=[excursion_col, "return_pct"]
    )
    if not sub.empty:
        fig.add_scatter(
            x=sub[excursion_col],
            y=sub["return_pct"],
            mode="markers",
            marker={
                "size": 9,
                "color": polarity_colors(sub["return_pct"]),
                "line": {"color": "#ffffff", "width": 1},
            },
            text=sub["underlying_symbol"],
            hovertemplate=f"%{{text}}<br>{x_title}: %{{x:.1f}}%<br>Realized: %{{y:.1f}}%<extra></extra>",
        )
        lo = float(min(sub[excursion_col].min(), sub["return_pct"].min(), 0))
        hi = float(max(sub[excursion_col].max(), sub["return_pct"].max(), 0))
        fig.add_scatter(
            x=[lo, hi],
            y=[lo, hi],
            mode="lines",
            name="1:1",
            line={"color": TEXT_SECONDARY, "width": 1, "dash": "dot"},
            hoverinfo="skip",
            showlegend=False,
        )
    fig.update_xaxes(title_text=f"{x_title} (%)")
    fig.update_yaxes(title_text="Realized return (%)")
    return fig
