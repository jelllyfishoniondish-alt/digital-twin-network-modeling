"""Scenario wrapper for a simple sequential multi-fault experiment."""

from src.twin.experiment_runner import main


if __name__ == "__main__":
    raise SystemExit(main(["--scenario", "multi_fault_scenario"]))
