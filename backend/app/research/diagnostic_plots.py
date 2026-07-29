"""Deterministic dependency-free SVG plots for residual diagnostics."""

from dataclasses import dataclass
from hashlib import sha256
from html import escape
from typing import Iterable

import numpy as np
from scipy import stats


SVG_WIDTH = 800
SVG_HEIGHT = 520
PLOT_LEFT = 78
PLOT_RIGHT = 24
PLOT_TOP = 48
PLOT_BOTTOM = 68
TICK_COUNT = 5


@dataclass(frozen=True, slots=True)
class DiagnosticPlot:
    plot_type: str
    mime_type: str
    content: str
    content_hash: str


def residual_histogram(
    residuals: np.ndarray,
    *,
    title: str,
    bin_count: int,
) -> DiagnosticPlot:
    counts, edges = np.histogram(residuals, bins=bin_count)
    maximum = max(int(np.max(counts)), 1)
    x_min, x_max = _expanded_range(float(edges[0]), float(edges[-1]))
    y_min, y_max = 0.0, float(maximum)
    bars: list[str] = []
    for index, count in enumerate(counts):
        x1 = _scale(float(edges[index]), x_min, x_max, PLOT_LEFT, _right())
        x2 = _scale(
            float(edges[index + 1]),
            x_min,
            x_max,
            PLOT_LEFT,
            _right(),
        )
        y = _scale(float(count), y_min, y_max, _bottom(), PLOT_TOP)
        bars.append(
            f'<rect x="{x1:.3f}" y="{y:.3f}" '
            f'width="{max(x2 - x1 - 1.0, 0.5):.3f}" '
            f'height="{_bottom() - y:.3f}" fill="#2563eb" '
            'fill-opacity="0.72"/>'
        )
    content = _svg_document(
        title=title,
        x_label="Residual (actual - predicted)",
        y_label="Count",
        x_range=(x_min, x_max),
        y_range=(y_min, y_max),
        elements=bars,
    )
    return _plot("residual_histogram", content)


def residual_qq_plot(
    residuals: np.ndarray,
    *,
    title: str,
) -> DiagnosticPlot:
    ordered = np.sort(residuals)
    probabilities = (
        np.arange(len(ordered), dtype=np.float64) + 0.5
    ) / len(ordered)
    theoretical = stats.norm.ppf(probabilities)
    slope, intercept = np.polyfit(theoretical, ordered, 1)
    x_min, x_max = _array_range(theoretical)
    reference_x = np.asarray((x_min, x_max), dtype=np.float64)
    reference_y = intercept + slope * reference_x
    content = _scatter_svg(
        theoretical,
        ordered,
        title=title,
        x_label="Theoretical normal quantile",
        y_label="Ordered residual",
        extra_elements=_line_elements(
            reference_x,
            reference_y,
            x_range=(x_min, x_max),
            y_range=_combined_range(ordered, reference_y),
        ),
        fixed_x_range=(x_min, x_max),
        fixed_y_range=_combined_range(ordered, reference_y),
    )
    return _plot("residual_qq", content)


def residual_vs_predicted(
    predicted: np.ndarray,
    residuals: np.ndarray,
    *,
    title: str,
) -> DiagnosticPlot:
    content = _scatter_svg(
        predicted,
        residuals,
        title=title,
        x_label="Predicted forward log return",
        y_label="Residual (actual - predicted)",
        horizontal_zero=True,
    )
    return _plot("residual_vs_predicted", content)


def residual_vs_actual(
    actual: np.ndarray,
    residuals: np.ndarray,
    *,
    title: str,
) -> DiagnosticPlot:
    content = _scatter_svg(
        actual,
        residuals,
        title=title,
        x_label="Actual forward log return",
        y_label="Residual (actual - predicted)",
        horizontal_zero=True,
    )
    return _plot("residual_vs_actual", content)


def _scatter_svg(
    x_values: np.ndarray,
    y_values: np.ndarray,
    *,
    title: str,
    x_label: str,
    y_label: str,
    horizontal_zero: bool = False,
    extra_elements: Iterable[str] = (),
    fixed_x_range: tuple[float, float] | None = None,
    fixed_y_range: tuple[float, float] | None = None,
) -> str:
    x_range = fixed_x_range or _array_range(x_values)
    y_range = fixed_y_range or _array_range(y_values)
    elements = list(extra_elements)
    if horizontal_zero and y_range[0] <= 0 <= y_range[1]:
        y = _scale(0.0, *y_range, _bottom(), PLOT_TOP)
        elements.append(
            f'<line x1="{PLOT_LEFT}" y1="{y:.3f}" '
            f'x2="{_right()}" y2="{y:.3f}" '
            'stroke="#6b7280" stroke-width="1" stroke-dasharray="5 4"/>'
        )
    for x_value, y_value in zip(x_values, y_values, strict=True):
        x = _scale(float(x_value), *x_range, PLOT_LEFT, _right())
        y = _scale(float(y_value), *y_range, _bottom(), PLOT_TOP)
        elements.append(
            f'<circle cx="{x:.3f}" cy="{y:.3f}" r="2.1" '
            'fill="#1d4ed8" fill-opacity="0.58"/>'
        )
    return _svg_document(
        title=title,
        x_label=x_label,
        y_label=y_label,
        x_range=x_range,
        y_range=y_range,
        elements=elements,
    )


def _line_elements(
    x_values: np.ndarray,
    y_values: np.ndarray,
    *,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
) -> tuple[str, ...]:
    points = " ".join(
        (
            f"{_scale(float(x), *x_range, PLOT_LEFT, _right()):.3f},"
            f"{_scale(float(y), *y_range, _bottom(), PLOT_TOP):.3f}"
        )
        for x, y in zip(x_values, y_values, strict=True)
    )
    return (
        f'<polyline points="{points}" fill="none" stroke="#dc2626" '
        'stroke-width="1.5"/>',
    )


def _svg_document(
    *,
    title: str,
    x_label: str,
    y_label: str,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
    elements: Iterable[str],
) -> str:
    body = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{SVG_WIDTH}" height="{SVG_HEIGHT}" '
            f'viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}">'
        ),
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        (
            f'<text x="{SVG_WIDTH / 2:.1f}" y="27" '
            'text-anchor="middle" font-family="sans-serif" '
            f'font-size="17">{escape(title)}</text>'
        ),
        (
            f'<line x1="{PLOT_LEFT}" y1="{_bottom()}" '
            f'x2="{_right()}" y2="{_bottom()}" '
            'stroke="#111827" stroke-width="1"/>'
        ),
        (
            f'<line x1="{PLOT_LEFT}" y1="{PLOT_TOP}" '
            f'x2="{PLOT_LEFT}" y2="{_bottom()}" '
            'stroke="#111827" stroke-width="1"/>'
        ),
    ]
    for index in range(TICK_COUNT):
        fraction = index / (TICK_COUNT - 1)
        x = PLOT_LEFT + fraction * (_right() - PLOT_LEFT)
        x_value = x_range[0] + fraction * (x_range[1] - x_range[0])
        y = _bottom() - fraction * (_bottom() - PLOT_TOP)
        y_value = y_range[0] + fraction * (y_range[1] - y_range[0])
        body.extend(
            (
                (
                    f'<line x1="{x:.3f}" y1="{_bottom()}" '
                    f'x2="{x:.3f}" y2="{_bottom() + 5}" '
                    'stroke="#111827"/>'
                ),
                (
                    f'<text x="{x:.3f}" y="{_bottom() + 21}" '
                    'text-anchor="middle" font-family="monospace" '
                    f'font-size="10">{_tick(x_value)}</text>'
                ),
                (
                    f'<line x1="{PLOT_LEFT - 5}" y1="{y:.3f}" '
                    f'x2="{PLOT_LEFT}" y2="{y:.3f}" '
                    'stroke="#111827"/>'
                ),
                (
                    f'<text x="{PLOT_LEFT - 9}" y="{y + 3.5:.3f}" '
                    'text-anchor="end" font-family="monospace" '
                    f'font-size="10">{_tick(y_value)}</text>'
                ),
            )
        )
    body.extend(elements)
    body.extend(
        (
            (
                f'<text x="{(PLOT_LEFT + _right()) / 2:.3f}" '
                f'y="{SVG_HEIGHT - 16}" text-anchor="middle" '
                f'font-family="sans-serif" font-size="12">'
                f"{escape(x_label)}</text>"
            ),
            (
                f'<text x="17" y="{(PLOT_TOP + _bottom()) / 2:.3f}" '
                'text-anchor="middle" font-family="sans-serif" '
                f'font-size="12" transform="rotate(-90 17 '
                f'{(PLOT_TOP + _bottom()) / 2:.3f})">'
                f"{escape(y_label)}</text>"
            ),
            "</svg>",
        )
    )
    return "".join(body)


def _plot(plot_type: str, content: str) -> DiagnosticPlot:
    return DiagnosticPlot(
        plot_type=plot_type,
        mime_type="image/svg+xml",
        content=content,
        content_hash=sha256(content.encode()).hexdigest(),
    )


def _array_range(values: np.ndarray) -> tuple[float, float]:
    return _expanded_range(float(np.min(values)), float(np.max(values)))


def _combined_range(
    first: np.ndarray,
    second: np.ndarray,
) -> tuple[float, float]:
    return _expanded_range(
        min(float(np.min(first)), float(np.min(second))),
        max(float(np.max(first)), float(np.max(second))),
    )


def _expanded_range(minimum: float, maximum: float) -> tuple[float, float]:
    if minimum == maximum:
        padding = max(abs(minimum) * 0.05, 1e-9)
    else:
        padding = (maximum - minimum) * 0.05
    return minimum - padding, maximum + padding


def _scale(
    value: float,
    source_min: float,
    source_max: float,
    target_min: float,
    target_max: float,
) -> float:
    return target_min + (
        (value - source_min) / (source_max - source_min)
    ) * (target_max - target_min)


def _tick(value: float) -> str:
    return format(value, ".4g")


def _right() -> float:
    return float(SVG_WIDTH - PLOT_RIGHT)


def _bottom() -> float:
    return float(SVG_HEIGHT - PLOT_BOTTOM)
