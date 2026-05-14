"""Tests for the minimal topology CLI parsing."""

from src.topology.minimal_topology import parse_args


def test_parse_args_defaults() -> None:
    config = parse_args([])

    assert config.controller_host == "127.0.0.1"
    assert config.controller_port == 6633
    assert config.link_bandwidth_mbps == 100
    assert config.link_delay_ms == 10
    assert config.auto_pingall is False
    assert config.drop_into_cli is True


def test_parse_args_overrides() -> None:
    config = parse_args(
        [
            "--controller-host",
            "10.0.0.10",
            "--controller-port",
            "6653",
            "--link-bandwidth-mbps",
            "50",
            "--link-delay-ms",
            "25",
            "--pingall",
            "--no-cli",
        ]
    )

    assert config.controller_host == "10.0.0.10"
    assert config.controller_port == 6653
    assert config.link_bandwidth_mbps == 50
    assert config.link_delay_ms == 25
    assert config.auto_pingall is True
    assert config.drop_into_cli is False
