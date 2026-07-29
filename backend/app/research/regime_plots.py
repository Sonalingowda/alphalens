"""Deterministic SVG visualizations for market regime analysis."""

from html import escape
from typing import Any

from app.research.diagnostic_plots import DiagnosticPlot


WIDTH = 860
HEIGHT = 520
LEFT = 92
RIGHT = 28
TOP = 58
BOTTOM = 82
COLORS = ("#2563eb", "#dc2626", "#6b7280", "#f59e0b", "#06b6d4")


def performance_by_regime(
    model_family: str,
    regime_statistics: dict[str, dict[str, Any]],
    regime_order: tuple[str, ...],
) -> DiagnosticPlot:
    values = [
        float(regime_statistics[name]["directional_accuracy"])
        for name in regime_order
    ]
    elements = _bars(
        values,
        labels=regime_order,
        maximum=1.0,
        grouped=False,
    )
    content = _document(
        title=f"{_title(model_family)}: Directional Accuracy by Regime",
        y_label="Directional accuracy",
        y_min=0.0,
        y_max=1.0,
        x_labels=regime_order,
        elements=elements,
        legend=(),
    )
    return _artifact("performance_by_regime", content)


def error_by_regime(
    model_family: str,
    regime_statistics: dict[str, dict[str, Any]],
    regime_order: tuple[str, ...],
) -> DiagnosticPlot:
    mae = [float(regime_statistics[name]["mae"]) for name in regime_order]
    rmse = [float(regime_statistics[name]["rmse"]) for name in regime_order]
    maximum = max((*mae, *rmse, 1e-12)) * 1.08
    elements = _grouped_bars(
        mae,
        rmse,
        labels=regime_order,
        maximum=maximum,
    )
    content = _document(
        title=f"{_title(model_family)}: Error by Regime",
        y_label="Forward log-return error",
        y_min=0.0,
        y_max=maximum,
        x_labels=regime_order,
        elements=elements,
        legend=(("MAE", "#2563eb"), ("RMSE", "#dc2626")),
    )
    return _artifact("error_by_regime", content)


def residual_distribution_by_regime(
    model_family: str,
    regime_statistics: dict[str, dict[str, Any]],
    regime_order: tuple[str, ...],
) -> DiagnosticPlot:
    quantiles = [
        regime_statistics[name]["residual_distribution"]
        for name in regime_order
    ]
    minimum = min(float(item["p05"]) for item in quantiles)
    maximum = max(float(item["p95"]) for item in quantiles)
    padding = max((maximum - minimum) * 0.08, 1e-9)
    x_min, x_max = minimum - padding, maximum + padding
    plot_top = TOP + 10
    plot_bottom = HEIGHT - BOTTOM
    row_height = (plot_bottom - plot_top) / len(regime_order)
    elements: list[str] = []
    zero_x = _scale(0.0, x_min, x_max, LEFT, WIDTH - RIGHT)
    if LEFT <= zero_x <= WIDTH - RIGHT:
        elements.append(
            f'<line x1="{zero_x:.3f}" y1="{plot_top:.3f}" '
            f'x2="{zero_x:.3f}" y2="{plot_bottom:.3f}" '
            'stroke="#9ca3af" stroke-dasharray="4 4"/>'
        )
    for index, (name, item) in enumerate(
        zip(regime_order, quantiles, strict=True)
    ):
        center_y = plot_top + (index + 0.5) * row_height
        p05 = _scale(float(item["p05"]), x_min, x_max, LEFT, WIDTH - RIGHT)
        q1 = _scale(float(item["q1"]), x_min, x_max, LEFT, WIDTH - RIGHT)
        median = _scale(
            float(item["median"]),
            x_min,
            x_max,
            LEFT,
            WIDTH - RIGHT,
        )
        q3 = _scale(float(item["q3"]), x_min, x_max, LEFT, WIDTH - RIGHT)
        p95 = _scale(float(item["p95"]), x_min, x_max, LEFT, WIDTH - RIGHT)
        elements.extend(
            (
                (
                    f'<line x1="{p05:.3f}" y1="{center_y:.3f}" '
                    f'x2="{p95:.3f}" y2="{center_y:.3f}" '
                    'stroke="#374151" stroke-width="1.5"/>'
                ),
                (
                    f'<line x1="{p05:.3f}" y1="{center_y - 7:.3f}" '
                    f'x2="{p05:.3f}" y2="{center_y + 7:.3f}" '
                    'stroke="#374151"/>'
                ),
                (
                    f'<line x1="{p95:.3f}" y1="{center_y - 7:.3f}" '
                    f'x2="{p95:.3f}" y2="{center_y + 7:.3f}" '
                    'stroke="#374151"/>'
                ),
                (
                    f'<rect x="{q1:.3f}" y="{center_y - 12:.3f}" '
                    f'width="{max(q3 - q1, 0.5):.3f}" height="24" '
                    f'fill="{COLORS[index]}" fill-opacity="0.55" '
                    'stroke="#111827"/>'
                ),
                (
                    f'<line x1="{median:.3f}" y1="{center_y - 12:.3f}" '
                    f'x2="{median:.3f}" y2="{center_y + 12:.3f}" '
                    'stroke="#111827" stroke-width="2"/>'
                ),
                (
                    f'<text x="{LEFT - 10}" y="{center_y + 4:.3f}" '
                    'text-anchor="end" font-family="sans-serif" '
                    f'font-size="11">{escape(_label(name))}</text>'
                ),
            )
        )
    for index in range(5):
        fraction = index / 4
        x = LEFT + fraction * (WIDTH - RIGHT - LEFT)
        value = x_min + fraction * (x_max - x_min)
        elements.extend(
            (
                (
                    f'<line x1="{x:.3f}" y1="{plot_bottom}" '
                    f'x2="{x:.3f}" y2="{plot_bottom + 5}" '
                    'stroke="#111827"/>'
                ),
                (
                    f'<text x="{x:.3f}" y="{plot_bottom + 20}" '
                    'text-anchor="middle" font-family="monospace" '
                    f'font-size="10">{value:.4g}</text>'
                ),
            )
        )
    content = (
        _svg_start(
            f"{_title(model_family)}: Residual Distribution by Regime"
        )
        + (
            f'<line x1="{LEFT}" y1="{plot_bottom}" '
            f'x2="{WIDTH - RIGHT}" y2="{plot_bottom}" '
            'stroke="#111827"/>'
        )
        + "".join(elements)
        + (
            f'<text x="{(LEFT + WIDTH - RIGHT) / 2:.3f}" '
            f'y="{HEIGHT - 24}" text-anchor="middle" '
            'font-family="sans-serif" font-size="12">'
            "Residual (actual - predicted); whiskers p05-p95, box IQR"
            "</text></svg>"
        )
    )
    return _artifact("residual_distribution_by_regime", content)


def _bars(
    values: list[float],
    *,
    labels: tuple[str, ...],
    maximum: float,
    grouped: bool,
) -> list[str]:
    del grouped
    plot_bottom = HEIGHT - BOTTOM
    group_width = (WIDTH - RIGHT - LEFT) / len(labels)
    elements: list[str] = []
    for index, value in enumerate(values):
        bar_width = group_width * 0.52
        x = LEFT + index * group_width + (group_width - bar_width) / 2
        y = _scale(value, 0.0, maximum, plot_bottom, TOP)
        elements.append(
            f'<rect x="{x:.3f}" y="{y:.3f}" width="{bar_width:.3f}" '
            f'height="{plot_bottom - y:.3f}" fill="{COLORS[index]}" '
            'fill-opacity="0.75"/>'
        )
    return elements


def _grouped_bars(
    first: list[float],
    second: list[float],
    *,
    labels: tuple[str, ...],
    maximum: float,
) -> list[str]:
    plot_bottom = HEIGHT - BOTTOM
    group_width = (WIDTH - RIGHT - LEFT) / len(labels)
    bar_width = group_width * 0.28
    elements: list[str] = []
    for index, (left_value, right_value) in enumerate(
        zip(first, second, strict=True)
    ):
        center = LEFT + (index + 0.5) * group_width
        for value, x, color in (
            (left_value, center - bar_width, "#2563eb"),
            (right_value, center, "#dc2626"),
        ):
            y = _scale(value, 0.0, maximum, plot_bottom, TOP)
            elements.append(
                f'<rect x="{x:.3f}" y="{y:.3f}" '
                f'width="{bar_width:.3f}" '
                f'height="{plot_bottom - y:.3f}" fill="{color}" '
                'fill-opacity="0.72"/>'
            )
    return elements


def _document(
    *,
    title: str,
    y_label: str,
    y_min: float,
    y_max: float,
    x_labels: tuple[str, ...],
    elements: list[str],
    legend: tuple[tuple[str, str], ...],
) -> str:
    plot_bottom = HEIGHT - BOTTOM
    body = [
        _svg_start(title),
        (
            f'<line x1="{LEFT}" y1="{TOP}" x2="{LEFT}" '
            f'y2="{plot_bottom}" stroke="#111827"/>'
        ),
        (
            f'<line x1="{LEFT}" y1="{plot_bottom}" '
            f'x2="{WIDTH - RIGHT}" y2="{plot_bottom}" '
            'stroke="#111827"/>'
        ),
    ]
    for index in range(5):
        fraction = index / 4
        y = plot_bottom - fraction * (plot_bottom - TOP)
        value = y_min + fraction * (y_max - y_min)
        body.extend(
            (
                (
                    f'<line x1="{LEFT - 5}" y1="{y:.3f}" '
                    f'x2="{LEFT}" y2="{y:.3f}" stroke="#111827"/>'
                ),
                (
                    f'<text x="{LEFT - 9}" y="{y + 3.5:.3f}" '
                    'text-anchor="end" font-family="monospace" '
                    f'font-size="10">{value:.4g}</text>'
                ),
            )
        )
    group_width = (WIDTH - RIGHT - LEFT) / len(x_labels)
    for index, label in enumerate(x_labels):
        x = LEFT + (index + 0.5) * group_width
        body.append(
            f'<text x="{x:.3f}" y="{plot_bottom + 22}" '
            'text-anchor="middle" font-family="sans-serif" '
            f'font-size="10">{escape(_label(label))}</text>'
        )
    body.extend(elements)
    for index, (label, color) in enumerate(legend):
        x = WIDTH - RIGHT - 150 + index * 82
        body.extend(
            (
                (
                    f'<rect x="{x}" y="35" width="12" height="12" '
                    f'fill="{color}" fill-opacity="0.72"/>'
                ),
                (
                    f'<text x="{x + 17}" y="45" font-family="sans-serif" '
                    f'font-size="10">{escape(label)}</text>'
                ),
            )
        )
    body.extend(
        (
            (
                f'<text x="17" y="{(TOP + plot_bottom) / 2:.3f}" '
                'text-anchor="middle" font-family="sans-serif" '
                f'font-size="12" transform="rotate(-90 17 '
                f'{(TOP + plot_bottom) / 2:.3f})">'
                f"{escape(y_label)}</text>"
            ),
            "</svg>",
        )
    )
    return "".join(body)


def _svg_start(title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" '
        f'height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">'
        '<rect width="100%" height="100%" fill="#ffffff"/>'
        f'<text x="{WIDTH / 2:.1f}" y="28" text-anchor="middle" '
        f'font-family="sans-serif" font-size="17">{escape(title)}</text>'
    )


def _artifact(plot_type: str, content: str) -> DiagnosticPlot:
    from hashlib import sha256

    return DiagnosticPlot(
        plot_type=plot_type,
        mime_type="image/svg+xml",
        content=content,
        content_hash=sha256(content.encode()).hexdigest(),
    )


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


def _title(value: str) -> str:
    return value.replace("_", " ").title()


def _label(value: str) -> str:
    return value.replace("_", " ").title()
