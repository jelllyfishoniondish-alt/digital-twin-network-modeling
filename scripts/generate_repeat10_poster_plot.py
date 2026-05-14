#!/usr/bin/env python3
"""Generate a poster-friendly traffic-profile summary figure for repeat=10."""

from __future__ import annotations

import csv
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / ".cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("XDG_CACHE_HOME", str(CACHE_DIR))
os.environ.setdefault("MPLCONFIGDIR", str(CACHE_DIR / "matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

INPUT_CSV = PROJECT_ROOT / "data" / "exports" / "traffic_profile_repeat10_summary.csv"
OUTPUT_PNG = PROJECT_ROOT / "data" / "plots" / "traffic_profile_repeat10_poster.png"

TRAFFIC_ORDER = ["none", "icmp", "iperf_tcp"]
TRAFFIC_LABEL = {"none": "Sans trafic", "icmp": "ICMP", "iperf_tcp": "iPerf TCP"}
TRAFFIC_COLOR = {"none": "#2fa7a0", "icmp": "#f24e4b", "iperf_tcp": "#5f6dba"}


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def index_rows(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {(row["scenario_name"], row["background_traffic"]): row for row in rows}


def num(row: dict[str, str], key: str) -> float:
    return float(row.get(key) or 0.0)


def main() -> int:
    rows = load_rows(INPUT_CSV)
    row_map = index_rows(rows)

    detection_scenarios = [
        ("recovery_scenario", "Recovery"),
        ("link_flap_scenario_down_1", "Link Flap"),
        ("multi_fault_scenario_fault_1", "Multi-Fault"),
    ]

    fig, (ax_left, ax_right) = plt.subplots(1, 2, figsize=(12, 4.8))

    # Left panel: first detection phase by scenario and traffic profile.
    x = np.arange(len(detection_scenarios))
    width = 0.23
    offsets = [-width, 0.0, width]

    for offset, traffic in zip(offsets, TRAFFIC_ORDER):
        means = []
        stds = []
        for scenario_key, _ in detection_scenarios:
            row = row_map[(scenario_key, traffic)]
            means.append(num(row, "detection_mean"))
            stds.append(num(row, "detection_stddev"))
        ax_left.bar(
            x + offset,
            means,
            width=width,
            yerr=stds,
            capsize=4,
            color=TRAFFIC_COLOR[traffic],
            edgecolor="white",
            linewidth=0.8,
            label=TRAFFIC_LABEL[traffic],
        )

    ax_left.set_title("Délai de détection\n(matrice principale, REPEAT=10)", fontsize=13, weight="bold")
    ax_left.set_xticks(x, [label for _, label in detection_scenarios])
    ax_left.set_ylabel("Secondes")
    ax_left.grid(axis="y", alpha=0.22)
    ax_left.legend(frameon=True)

    # Right panel: recovery scenario only, grouped by traffic profile.
    recovery_means = [num(row_map[("recovery_scenario", traffic)], "recovery_mean") for traffic in TRAFFIC_ORDER]
    recovery_stds = [num(row_map[("recovery_scenario", traffic)], "recovery_stddev") for traffic in TRAFFIC_ORDER]
    x2 = np.arange(len(TRAFFIC_ORDER))
    bars = ax_right.bar(
        x2,
        recovery_means,
        yerr=recovery_stds,
        capsize=5,
        width=0.6,
        color=[TRAFFIC_COLOR[traffic] for traffic in TRAFFIC_ORDER],
        edgecolor="white",
        linewidth=0.8,
    )
    ax_right.set_title("Délai de reprise\n(recovery_scenario, REPEAT=10)", fontsize=13, weight="bold")
    ax_right.set_xticks(x2, [TRAFFIC_LABEL[traffic] for traffic in TRAFFIC_ORDER])
    ax_right.set_ylabel("Secondes")
    ax_right.grid(axis="y", alpha=0.22)
    ax_right.set_ylim(0, max(recovery_means) + max(recovery_stds) + 0.25)

    for bar, value in zip(bars, recovery_means):
        ax_right.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.04,
            f"{value:.2f}s",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    fig.suptitle("Impact du trafic de fond sur la détection et la reprise", fontsize=15, weight="bold", y=1.02)
    fig.tight_layout()
    OUTPUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PNG, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print(OUTPUT_PNG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
