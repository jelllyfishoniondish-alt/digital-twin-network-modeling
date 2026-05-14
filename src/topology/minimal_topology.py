"""Minimal Mininet topology for the TER network digital twin PoC."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

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


@dataclass(slots=True)
class MinimalTopologyConfig:
    """Runtime configuration for the Mininet demo topology."""

    controller_host: str = "127.0.0.1"
    controller_port: int = 6633
    link_bandwidth_mbps: int = 100
    link_delay_ms: int = 10
    auto_pingall: bool = False
    drop_into_cli: bool = True
    use_tc: bool = True


class MinimalTopo(Topo):
    """Three-switch line topology with one host attached to each switch."""

    def build(self, bw_mbps: int = 100, delay_ms: int = 10, use_tc: bool = True) -> None:
        delay = f"{delay_ms}ms"
        link_cls = TCLink if use_tc else Link
        link_kwargs = {"cls": link_cls, "bw": bw_mbps, "delay": delay} if use_tc else {"cls": link_cls}

        s1 = self.addSwitch("s1")
        s2 = self.addSwitch("s2")
        s3 = self.addSwitch("s3")

        h1 = self.addHost("h1", ip="10.0.0.1/24", mac="00:00:00:00:00:01")
        h2 = self.addHost("h2", ip="10.0.0.2/24", mac="00:00:00:00:00:02")
        h3 = self.addHost("h3", ip="10.0.0.3/24", mac="00:00:00:00:00:03")

        self.addLink(h1, s1, **link_kwargs)
        self.addLink(h2, s2, **link_kwargs)
        self.addLink(h3, s3, **link_kwargs)
        self.addLink(s1, s2, **link_kwargs)
        self.addLink(s2, s3, **link_kwargs)


def build_network(config: MinimalTopologyConfig) -> Mininet:
    """Build the Mininet network for the demo."""

    if MININET_IMPORT_ERROR is not None:  # pragma: no cover - runtime safeguard
        raise RuntimeError(
            "Mininet is not installed in the current environment. "
            "Install Mininet/OVS first, then rerun the topology command."
        ) from MININET_IMPORT_ERROR

    topo = MinimalTopo(
        bw_mbps=config.link_bandwidth_mbps,
        delay_ms=config.link_delay_ms,
        use_tc=config.use_tc,
    )
    controller = RemoteController(
        "c0",
        ip=config.controller_host,
        port=config.controller_port,
    )
    link_cls = TCLink if config.use_tc else Link
    network = Mininet(
        topo=topo,
        controller=controller,
        switch=OVSSwitch,
        link=link_cls,
        autoSetMacs=False,
    )
    return network


def run_network(config: MinimalTopologyConfig) -> None:
    """Start the network, optionally validate connectivity, and open the CLI."""

    network = build_network(config)
    network.start()
    try:
        if config.auto_pingall:
            network.pingAll()
        if config.drop_into_cli:
            CLI(network)
    finally:
        network.stop()


def parse_args(argv: list[str] | None = None) -> MinimalTopologyConfig:
    """Parse CLI arguments into a topology config."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controller-host", default="127.0.0.1")
    parser.add_argument("--controller-port", type=int, default=6633)
    parser.add_argument("--link-bandwidth-mbps", type=int, default=100)
    parser.add_argument("--link-delay-ms", type=int, default=10)
    parser.add_argument("--pingall", action="store_true")
    parser.add_argument("--no-cli", action="store_true")
    args = parser.parse_args(argv)

    return MinimalTopologyConfig(
        controller_host=args.controller_host,
        controller_port=args.controller_port,
        link_bandwidth_mbps=args.link_bandwidth_mbps,
        link_delay_ms=args.link_delay_ms,
        auto_pingall=args.pingall,
        drop_into_cli=not args.no_cli,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the minimal topology module."""

    config = parse_args(argv)
    try:
        setLogLevel("info")
        run_network(config)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
