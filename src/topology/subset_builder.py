"""Build connected topology subsets from an imported internal topology JSON."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from src.topology.topology_loader import load_topology_definition


def _scenario_targets(links: list[dict[str, object]]) -> dict[str, object]:
    if not links:
        raise ValueError("Subset must contain at least one link.")
    first_link = [str(links[0]["src"]), str(links[0]["dst"])]
    second_link = [str(links[1]["src"]), str(links[1]["dst"])] if len(links) > 1 else first_link
    return {
        "single_link_failure": first_link,
        "recovery_scenario": first_link,
        "link_flap_scenario": first_link,
        "multi_fault_scenario": [first_link, second_link],
    }


def build_topology_subset(
    source_path: Path,
    output_path: Path,
    selected_switches: list[str],
    topology_name: str,
    description: str | None = None,
) -> Path:
    """Create an induced subgraph topology JSON from a source topology."""

    definition = load_topology_definition(source_path)
    selected = set(selected_switches)

    switches = [switch for switch in definition.switches if switch.name in selected]
    if len(switches) != len(selected):
        known_switches = {switch.name for switch in definition.switches}
        missing = sorted(selected - known_switches)
        raise ValueError(f"Unknown switch names for subset: {', '.join(missing)}")

    hosts = [host for host in definition.hosts if host.switch in selected]
    links = [link for link in definition.links if link.src in selected and link.dst in selected]
    if not links:
        raise ValueError("Selected subset does not contain any links.")

    link_payloads = [asdict(link) for link in links]
    payload = {
        "name": topology_name,
        "description": description or f"Subset of {definition.name} built from selected switches.",
        "provenance": {
            **definition.provenance,
            "subset_of": definition.name,
            "subset_source": str(source_path),
            "selected_switches": selected_switches,
            "subset_builder": "src.topology.subset_builder",
        },
        "switches": [asdict(switch) for switch in switches],
        "hosts": [asdict(host) for host in hosts],
        "links": link_payloads,
        "scenario_targets": _scenario_targets(link_payloads),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI args for subset building."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--description", default=None)
    parser.add_argument("--switches", nargs="+", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for subset generation."""

    args = parse_args(argv)
    build_topology_subset(
        source_path=args.input,
        output_path=args.output,
        selected_switches=args.switches,
        topology_name=args.name,
        description=args.description,
    )
    print(str(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
