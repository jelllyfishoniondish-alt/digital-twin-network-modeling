"""Plotting helpers for TER experiment outputs."""

from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = PROJECT_ROOT / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_DIR))
os.environ.setdefault("MPLCONFIGDIR", str(CACHE_DIR / "matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def load_experiment_rows(csv_path: Path) -> list[dict[str, str]]:
    """Load experiment rows from CSV."""

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _metric_fields(metric: str) -> tuple[str, str]:
    if metric == "detection":
        return "detection_delay", "detection_mean"
    if metric == "recovery":
        return "recovery_delay", "recovery_mean"
    if metric == "ground_truth_detection":
        return "ground_truth_detection_lag", "ground_truth_detection_lag_mean"
    if metric == "ground_truth_recovery":
        return "ground_truth_recovery_lag", "ground_truth_recovery_lag_mean"
    raise ValueError(f"Unsupported metric: {metric}")


def _metric_value(row: dict[str, Any], metric: str) -> float | None:
    raw_field, summary_field = _metric_fields(metric)
    raw_value = _coerce_float(row.get(raw_field))
    if raw_value is not None:
        return raw_value
    return _coerce_float(row.get(summary_field))


def _metric_label(metric: str) -> str:
    if metric == "detection":
        return "Detection"
    if metric == "recovery":
        return "Recovery"
    if metric == "ground_truth_detection":
        return "Ground-Truth Detection"
    if metric == "ground_truth_recovery":
        return "Ground-Truth Recovery"
    raise ValueError(f"Unsupported metric: {metric}")


def build_detection_delay_plot(rows: list[dict[str, str]], output_path: Path) -> Path:
    """Build a simple bar chart for detection delay."""

    traffic_labels = [row.get("background_traffic", "") for row in rows]
    topology_labels = [row.get("topology_name", "") for row in rows]
    controller_labels = [row.get("controller_app", "") for row in rows]
    poll_interval_labels = [row.get("poll_interval", "") for row in rows]
    include_topology = len({label for label in topology_labels if label}) > 1
    include_controller = len({label for label in controller_labels if label}) > 1
    include_poll_interval = len({label for label in poll_interval_labels if label}) > 1

    def _scenario_label(row: dict[str, str]) -> str:
        parts: list[str] = []
        if include_controller and row.get("controller_app"):
            parts.append(row["controller_app"].split(".")[-1])
        if include_topology and row.get("topology_name"):
            parts.append(row["topology_name"])
        if include_poll_interval and row.get("poll_interval"):
            parts.append(f"poll={row['poll_interval']}s")
        parts.append(row["scenario_name"])
        if row.get("background_traffic"):
            parts.append(row.get("background_traffic", "none"))
        return "\n".join(parts)

    if rows and "detection_mean" in rows[0]:
        scenarios = [_scenario_label(row) for row in rows]
        detection_delays = [float(row["detection_mean"] or 0.0) for row in rows]
        recovery_delays = [float(row["recovery_mean"] or 0.0) for row in rows]
        detection_p95 = [float(row["detection_p95"] or 0.0) for row in rows]
        detection_stddev = [float(row.get("detection_stddev", 0.0) or 0.0) for row in rows]
        recovery_stddev = [float(row.get("recovery_stddev", 0.0) or 0.0) for row in rows]
        title = "Twin Detection and Recovery Delays (Repeated Runs)"
    else:
        include_traffic = len(set(traffic_labels)) > 1
        scenarios = [
            _scenario_label(row)
            if include_traffic or include_topology or include_controller or include_poll_interval
            else row["scenario_name"]
            for row in rows
        ]
        detection_delays = [float(row["detection_delay"] or 0.0) for row in rows]
        recovery_delays = [float(row["recovery_delay"] or 0.0) for row in rows]
        detection_p95 = []
        detection_stddev = []
        recovery_stddev = []
        title = "Twin Detection and Recovery Delays"

    figure, axis = plt.subplots(figsize=(8, 4.5))
    x_positions = range(len(scenarios))
    axis.bar(
        x_positions,
        detection_delays,
        yerr=detection_stddev if detection_stddev else None,
        capsize=4 if detection_stddev else 0,
        color="#0d6e6e",
        label="Detection Delay",
    )
    axis.plot(
        list(x_positions),
        recovery_delays,
        color="#a6372b",
        marker="o",
        label="Recovery Delay",
    )
    if recovery_stddev:
        axis.errorbar(
            list(x_positions),
            recovery_delays,
            yerr=recovery_stddev,
            fmt="none",
            ecolor="#a6372b",
            elinewidth=1,
            capsize=4,
        )
    if detection_p95:
        axis.plot(list(x_positions), detection_p95, color="#245b91", marker="s", label="Detection P95")
    axis.set_xticks(list(x_positions), scenarios, rotation=15, ha="right")
    axis.set_ylabel("Delay (s)")
    axis.set_title(title)
    axis.legend()
    axis.grid(axis="y", alpha=0.25)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(output_path, dpi=180)
    plt.close(figure)
    return output_path


def build_scalability_plot(rows: list[dict[str, str | float | int | None]], output_path: Path) -> Path:
    """Build a dual-axis scalability plot for detection delay and sync cost."""

    ordered_rows = sorted(rows, key=lambda row: int(row.get("node_count") or 0))
    x_labels = [str(int(row.get("node_count") or 0)) for row in ordered_rows]
    detection_ms = [float(row.get("detection_delay") or 0.0) * 1000 for row in ordered_rows]
    sync_ms = [float(row.get("sync_duration_ms") or 0.0) for row in ordered_rows]

    figure, left_axis = plt.subplots(figsize=(8, 4.5))
    right_axis = left_axis.twinx()
    x_positions = range(len(ordered_rows))

    left_axis.plot(list(x_positions), detection_ms, color="#0d6e6e", marker="o", label="Detection Delay")
    right_axis.plot(list(x_positions), sync_ms, color="#a6372b", marker="s", label="Sync Duration")

    left_axis.set_xticks(list(x_positions), x_labels)
    left_axis.set_xlabel("Node Count")
    left_axis.set_ylabel("Detection Delay (ms)", color="#0d6e6e")
    right_axis.set_ylabel("Sync Duration (ms)", color="#a6372b")
    left_axis.set_title("Scalability: Detection Delay vs Sync Duration")
    left_axis.grid(axis="y", alpha=0.25)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(output_path, dpi=180)
    plt.close(figure)
    return output_path


def build_load_scatter_plot(
    rows: list[dict[str, str | float | int | None]],
    output_path: Path,
    metric: str = "detection",
) -> Path:
    """Build a raw-point scatter plot for delay under different background loads."""

    grouped: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        load_percent = _coerce_float(row.get("background_load_percent"))
        metric_value = _metric_value(row, metric)
        if load_percent is None or metric_value is None:
            continue
        grouped[int(load_percent)].append(metric_value)

    if not grouped:
        raise ValueError("No rows contain both background_load_percent and the requested metric.")

    ordered_loads = sorted(grouped)
    figure, axis = plt.subplots(figsize=(8, 4.5))
    for load_percent in ordered_loads:
        values = grouped[load_percent]
        center = (len(values) - 1) / 2
        x_positions = [load_percent + ((index - center) * 0.35) for index in range(len(values))]
        axis.scatter(
            x_positions,
            values,
            s=34,
            alpha=0.8,
            color="#0d6e6e",
            edgecolors="white",
            linewidths=0.5,
        )

    axis.set_xticks(ordered_loads)
    axis.set_xlabel("Background Load (%)")
    axis.set_ylabel(f"{_metric_label(metric)} Delay (s)")
    axis.set_title(f"{_metric_label(metric)} Delay vs Background Load")
    axis.grid(axis="both", alpha=0.25)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(output_path, dpi=180)
    plt.close(figure)
    return output_path


def build_delay_box_plot(
    rows: list[dict[str, str | float | int | None]],
    output_path: Path,
    metric: str = "detection",
) -> Path:
    """Build a box plot grouped by load percentage or background traffic profile."""

    grouped_by_load: dict[int, list[float]] = defaultdict(list)
    grouped_by_traffic: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        load_percent = _coerce_float(row.get("background_load_percent"))
        metric_value = _metric_value(row, metric)
        if metric_value is None:
            continue
        if load_percent is not None:
            grouped_by_load[int(load_percent)].append(metric_value)
            continue
        background_traffic = str(row.get("background_traffic") or "").strip()
        if background_traffic:
            grouped_by_traffic[background_traffic].append(metric_value)

    if grouped_by_load:
        ordered_labels = [f"{load_percent}%" for load_percent in sorted(grouped_by_load)]
        ordered_values = [grouped_by_load[load_percent] for load_percent in sorted(grouped_by_load)]
        x_label = "Background Load (%)"
        title_suffix = "by Background Load"
    elif grouped_by_traffic:
        traffic_order = ["none", "icmp", "iperf_tcp"]
        ordered_keys = sorted(
            grouped_by_traffic,
            key=lambda item: (traffic_order.index(item) if item in traffic_order else len(traffic_order), item),
        )
        ordered_labels = ordered_keys
        ordered_values = [grouped_by_traffic[key] for key in ordered_keys]
        x_label = "Background Traffic"
        title_suffix = "by Background Traffic"
    else:
        raise ValueError("No rows contain a supported grouping field and the requested metric.")

    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.boxplot(
        ordered_values,
        labels=ordered_labels,
        patch_artist=True,
        boxprops={"facecolor": "#d6ecec", "edgecolor": "#0d6e6e"},
        medianprops={"color": "#a6372b", "linewidth": 1.5},
        whiskerprops={"color": "#0d6e6e"},
        capprops={"color": "#0d6e6e"},
        flierprops={"marker": "o", "markersize": 4, "markerfacecolor": "#a6372b", "markeredgecolor": "#a6372b"},
    )
    axis.set_xlabel(x_label)
    axis.set_ylabel(f"{_metric_label(metric)} Delay (s)")
    axis.set_title(f"{_metric_label(metric)} Delay Distribution {title_suffix}")
    axis.grid(axis="y", alpha=0.25)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(output_path, dpi=180)
    plt.close(figure)
    return output_path


def build_run_order_scatter_plot(
    rows: list[dict[str, str | float | int | None]],
    output_path: Path,
    metric: str = "detection",
) -> Path:
    """Build a scatter plot for run order versus delay, colored by load level."""

    grouped: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for row in rows:
        run_order = _coerce_float(row.get("Run_Order"))
        load_percent = _coerce_float(row.get("background_load_percent"))
        metric_value = _metric_value(row, metric)
        if run_order is None or load_percent is None or metric_value is None:
            continue
        grouped[int(load_percent)].append((int(run_order), metric_value))

    if not grouped:
        raise ValueError("No rows contain Run_Order, background_load_percent, and the requested metric.")

    palette = {
        10: "#245b91",
        30: "#a6372b",
        50: "#0d6e6e",
        80: "#8a6d1d",
    }
    figure, axis = plt.subplots(figsize=(8.5, 4.8))
    for load_percent in sorted(grouped):
        points = sorted(grouped[load_percent], key=lambda item: item[0])
        axis.scatter(
            [run_order for run_order, _ in points],
            [value for _, value in points],
            s=42,
            alpha=0.85,
            color=palette.get(load_percent, "#444444"),
            edgecolors="white",
            linewidths=0.5,
            label=f"{load_percent}%",
        )

    axis.set_xlabel("Run Order")
    axis.set_ylabel(f"{_metric_label(metric)} Delay (s)")
    axis.set_title(f"{_metric_label(metric)} Delay vs Run Order")
    axis.grid(axis="both", alpha=0.25)
    axis.legend(title="Load")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(output_path, dpi=180)
    plt.close(figure)
    return output_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the plotting helper."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--plot-type",
        choices=["detection", "scalability", "load-scatter", "boxplot", "run-order-scatter"],
        default="detection",
    )
    parser.add_argument(
        "--metric",
        choices=["detection", "recovery", "ground_truth_detection", "ground_truth_recovery"],
        default="detection",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for plot generation."""

    args = parse_args(argv)
    rows = load_experiment_rows(args.input_csv)
    if args.plot_type == "detection":
        build_detection_delay_plot(rows, args.output)
    elif args.plot_type == "scalability":
        build_scalability_plot(rows, args.output)
    elif args.plot_type == "load-scatter":
        build_load_scatter_plot(rows, args.output, metric=args.metric)
    elif args.plot_type == "run-order-scatter":
        build_run_order_scatter_plot(rows, args.output, metric=args.metric)
    else:
        build_delay_box_plot(rows, args.output, metric=args.metric)
    print(str(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
