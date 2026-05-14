"""Scenario wrapper for a single link failure experiment."""

from src.twin.experiment_runner import main


if __name__ == "__main__":
    raise SystemExit(main(["--scenario", "single_link_failure"]))
