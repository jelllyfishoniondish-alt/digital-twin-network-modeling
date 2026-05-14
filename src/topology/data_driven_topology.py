"""Data-driven Mininet topology builder for realistic twin experiments."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from mininet.cli import CLI
    from mininet.link import Link, TCLink
    from mininet.log import setLogLevel
    from mininet.net import Mininet
    from mininet.node import OVSSwitch, RemoteController
    from mininet.topo import Topo
except ImportError as exc:  # pragma: no cover - requires Mininet runtime
    Topo = object  # type: ignore[assignment]
    MININET_IMPORT_ERROR = exc
    Mininet = object  # type: ignore[assignment]

    def setLogLevel(_: str) -> None:
        """Fallback no-op when Mininet is unavailable."""
else:
    MININET_IMPORT_ERROR = None

from src.topology.topology_loader import TopologyDefinition, load_topology_definition


@dataclass(slots=True)
class DataDrivenTopologyConfig:
    """Runtime configuration for a topology loaded from JSON."""

    topology_path: Path
    controller_host: str = "127.0.0.1"
    controller_port: int = 6633
    auto_pingall: bool = False
    drop_into_cli: bool = True
    use_tc: bool = True


class DataDrivenTopo(Topo):
    """Mininet topology generated from a normalized topology definition."""

    def build(self, definition: TopologyDefinition, use_tc: bool = True) -> None:
        link_cls = TCLink if use_tc else Link

        for switch in definition.switches:
            self.addSwitch(switch.name, dpid=switch.dpid)

        for host in definition.hosts:
            self.addHost(host.name, ip=host.ip, mac=host.mac)
            self.addLink(host.name, host.switch, cls=link_cls)

        for link in definition.active_links():
            if use_tc:
                self.addLink(
                    link.src,
                    link.dst,
                    cls=link_cls,
                    bw=link.bandwidth_mbps,
                    delay=f"{link.delay_ms}ms",
                )
            else:
                self.addLink(link.src, link.dst, cls=link_cls)


def build_network(config: DataDrivenTopologyConfig, definition: TopologyDefinition | None = None) -> Mininet:
    """Build a Mininet network from a normalized topology definition."""

    if MININET_IMPORT_ERROR is not None:  # pragma: no cover - runtime safeguard
        raise RuntimeError(
            "Mininet is not installed in the current environment. "
            "Install Mininet/OVS first, then rerun the topology command."
        ) from MININET_IMPORT_ERROR

    topology_definition = definition or load_topology_definition(config.topology_path)
    topo = DataDrivenTopo(definition=topology_definition, use_tc=config.use_tc)
    link_cls = TCLink if config.use_tc else Link
    controller = RemoteController(
        "c0",
        ip=config.controller_host,
        port=config.controller_port,
    )
    return Mininet(
        topo=topo,
        controller=controller,
        switch=OVSSwitch,
        link=link_cls,
        autoSetMacs=False,
    )


def run_network(config: DataDrivenTopologyConfig) -> None:
    """Start a data-driven topology and optionally open a CLI."""

    network = build_network(config)
    network.start()
    try:
        if config.auto_pingall:
            network.pingAll()
        if config.drop_into_cli:
            CLI(network)
    finally:
        network.stop()


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the data-driven topology module."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology-file", type=Path, required=True)
    parser.add_argument("--controller-host", default="127.0.0.1")
    parser.add_argument("--controller-port", type=int, default=6633)
    parser.add_argument("--pingall", action="store_true")
    parser.add_argument("--no-cli", action="store_true")
    args = parser.parse_args(argv)

    config = DataDrivenTopologyConfig(
        topology_path=args.topology_file,
        controller_host=args.controller_host,
        controller_port=args.controller_port,
        auto_pingall=args.pingall,
        drop_into_cli=not args.no_cli,
    )
    try:
        setLogLevel("info")
        run_network(config)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
