"""Tests for experiment plotting helpers."""

from src.twin.plotting import (
    build_delay_box_plot,
    build_detection_delay_plot,
    build_load_scatter_plot,
    build_run_order_scatter_plot,
)


def test_build_detection_delay_plot(tmp_path) -> None:
    output_path = build_detection_delay_plot(
        [
            {
                "scenario_name": "single_link_failure",
                "detection_delay": "2.0",
                "recovery_delay": "",
            },
            {
                "scenario_name": "recovery_scenario",
                "detection_delay": "3.0",
                "recovery_delay": "1.0",
            },
        ],
        tmp_path / "plot.png",
    )

    assert output_path.exists()


def test_build_detection_delay_plot_supports_multiple_topologies(tmp_path) -> None:
    output_path = build_detection_delay_plot(
        [
            {
                "scenario_name": "recovery_scenario",
                "topology_name": "geant_backbone_8cities_stage3",
                "background_traffic": "none",
                "detection_mean": "0.2",
                "recovery_mean": "1.8",
                "detection_p95": "0.3",
            },
            {
                "scenario_name": "recovery_scenario",
                "topology_name": "geant2012_core12",
                "background_traffic": "none",
                "detection_mean": "0.7",
                "recovery_mean": "1.9",
                "detection_p95": "0.8",
            },
        ],
        tmp_path / "multi_topology_plot.png",
    )

    assert output_path.exists()


def test_build_load_scatter_plot_groups_points_by_load_percent(tmp_path) -> None:
    output_path = build_load_scatter_plot(
        [
            {
                "scenario_name": "recovery_scenario",
                "background_load_percent": "10",
                "detection_delay": "0.4",
            },
            {
                "scenario_name": "recovery_scenario",
                "background_load_percent": "30",
                "detection_delay": "0.9",
            },
            {
                "scenario_name": "recovery_scenario",
                "background_load_percent": "30",
                "detection_delay": "1.1",
            },
        ],
        tmp_path / "scatter_plot.png",
    )

    assert output_path.exists()


def test_build_delay_box_plot_supports_recovery_metric(tmp_path) -> None:
    output_path = build_delay_box_plot(
        [
            {
                "scenario_name": "recovery_scenario",
                "background_load_percent": "10",
                "recovery_delay": "1.4",
            },
            {
                "scenario_name": "recovery_scenario",
                "background_load_percent": "10",
                "recovery_delay": "1.7",
            },
            {
                "scenario_name": "recovery_scenario",
                "background_load_percent": "50",
                "recovery_delay": "2.1",
            },
        ],
        tmp_path / "box_plot.png",
        metric="recovery",
    )

    assert output_path.exists()


def test_build_delay_box_plot_supports_ground_truth_detection_metric(tmp_path) -> None:
    output_path = build_delay_box_plot(
        [
            {
                "scenario_name": "recovery_scenario",
                "background_load_percent": "10",
                "ground_truth_detection_lag": "0.3",
            },
            {
                "scenario_name": "recovery_scenario",
                "background_load_percent": "10",
                "ground_truth_detection_lag": "0.5",
            },
            {
                "scenario_name": "recovery_scenario",
                "background_load_percent": "50",
                "ground_truth_detection_lag": "0.8",
            },
        ],
        tmp_path / "ground_truth_box_plot.png",
        metric="ground_truth_detection",
    )

    assert output_path.exists()


def test_build_delay_box_plot_groups_by_background_traffic_when_load_missing(tmp_path) -> None:
    output_path = build_delay_box_plot(
        [
            {
                "scenario_name": "recovery_scenario",
                "background_traffic": "none",
                "ground_truth_detection_lag": "0.27",
            },
            {
                "scenario_name": "recovery_scenario",
                "background_traffic": "icmp",
                "ground_truth_detection_lag": "1.01",
            },
            {
                "scenario_name": "recovery_scenario",
                "background_traffic": "iperf_tcp",
                "ground_truth_detection_lag": "0.71",
            },
        ],
        tmp_path / "ground_truth_background_traffic_box_plot.png",
        metric="ground_truth_detection",
    )

    assert output_path.exists()


def test_build_run_order_scatter_plot_uses_run_order_column(tmp_path) -> None:
    output_path = build_run_order_scatter_plot(
        [
            {
                "scenario_name": "recovery_scenario",
                "background_load_percent": "10",
                "Run_Order": "1",
                "detection_delay": "2.4",
            },
            {
                "scenario_name": "recovery_scenario",
                "background_load_percent": "50",
                "Run_Order": "2",
                "detection_delay": "1.2",
            },
            {
                "scenario_name": "recovery_scenario",
                "background_load_percent": "80",
                "Run_Order": "3",
                "detection_delay": "0.9",
            },
        ],
        tmp_path / "run_order_scatter.png",
    )

    assert output_path.exists()
