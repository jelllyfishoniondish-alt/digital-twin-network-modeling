"""Tests for OVS/Mininet ground-truth collection."""

from __future__ import annotations

from src.twin.ground_truth import (
    build_ovs_ground_truth_state,
    parse_ovs_ofctl_dump_ports,
    parse_ovs_ofctl_dump_ports_desc,
    wait_for_ovs_link_state,
)


def test_parse_ovs_ofctl_dump_ports_desc_marks_link_down_ports() -> None:
    output = """
OFPST_PORT_DESC reply (xid=0x2):
 1(s1-eth1): addr:aa:bb:cc:dd:ee:ff
     config:     0
     state:      0
 2(s1-eth2): addr:aa:bb:cc:dd:ee:00
     config:     0
     state:      LINK_DOWN
"""

    ports = parse_ovs_ofctl_dump_ports_desc(output)

    assert ports["s1-eth1"].port_no == 1
    assert ports["s1-eth1"].is_up is True
    assert ports["s1-eth2"].port_no == 2
    assert ports["s1-eth2"].is_up is False


def test_parse_ovs_ofctl_dump_ports_extracts_counters() -> None:
    output = """
OFPST_PORT reply (xid=0x2): 1 ports
  port  2: rx pkts=10, bytes=100, drop=0, errs=0, frame=0, over=0, crc=0
           tx pkts=20, bytes=200, drop=0, errs=0, coll=0
"""

    counters = parse_ovs_ofctl_dump_ports(output)

    assert counters == {
        "rx_packets": 10,
        "tx_packets": 20,
        "rx_bytes": 100,
        "tx_bytes": 200,
    }


def test_build_ovs_ground_truth_state_uses_runtime_port_status_and_counters() -> None:
    class FakeIntf:
        def __init__(self, name: str) -> None:
            self.name = name

    class FakeSwitch:
        def __init__(self, name: str, dpid: str, outputs: dict[str, str]) -> None:
            self.name = name
            self.dpid = dpid
            self._outputs = outputs
            self._connections: dict[str, list[tuple[FakeIntf, FakeIntf]]] = {}

        def cmd(self, command: str) -> str:
            return self._outputs[command]

        def connectionsTo(self, other):
            return self._connections.get(other.name, [])

    class FakeNetwork:
        def __init__(self, switches) -> None:
            self.switches = switches
            self._index = {switch.name: switch for switch in switches}

        def get(self, name: str):
            return self._index[name]

    s1 = FakeSwitch(
        "s1",
        "0000000000000001",
        {
            "ovs-ofctl dump-ports-desc s1": """
 1(s1-eth1): addr:aa:bb
     config:     0
     state:      0
""",
            "ovs-ofctl dump-ports s1 1": """
  port  1: rx pkts=10, bytes=100, drop=0, errs=0, frame=0, over=0, crc=0
           tx pkts=20, bytes=200, drop=0, errs=0, coll=0
""",
        },
    )
    s2 = FakeSwitch(
        "s2",
        "0000000000000002",
        {
            "ovs-ofctl dump-ports-desc s2": """
 3(s2-eth1): addr:cc:dd
     config:     0
     state:      0
""",
            "ovs-ofctl dump-ports s2 3": """
  port  3: rx pkts=30, bytes=300, drop=0, errs=0, frame=0, over=0, crc=0
           tx pkts=40, bytes=400, drop=0, errs=0, coll=0
""",
        },
    )

    s1_intf = FakeIntf("s1-eth1")
    s2_intf = FakeIntf("s2-eth1")
    s1._connections["s2"] = [(s1_intf, s2_intf)]
    s2._connections["s1"] = [(s2_intf, s1_intf)]

    network = FakeNetwork([s1, s2])

    truth_state = build_ovs_ground_truth_state(network)

    assert len(truth_state.switches) == 2
    assert len(truth_state.links) == 1
    assert truth_state.links[0].is_up is True
    assert truth_state.links[0].src_port == 1
    assert truth_state.links[0].dst_port == 3
    assert truth_state.switches[0].ports[0].rx_packets == 10
    assert truth_state.switches[1].ports[0].tx_bytes == 400


def test_wait_for_ovs_link_state_returns_timestamp_when_state_matches() -> None:
    class FakeIntf:
        def __init__(self, name: str) -> None:
            self.name = name

    class FakeSwitch:
        def __init__(self, name: str, dpid: str, state_payload: str) -> None:
            self.name = name
            self.dpid = dpid
            self._state_payload = state_payload
            self._connections: dict[str, list[tuple[FakeIntf, FakeIntf]]] = {}

        def cmd(self, command: str) -> str:
            if command.startswith("ovs-ofctl dump-ports-desc"):
                return self._state_payload
            return """
  port  1: rx pkts=0, bytes=0, drop=0, errs=0, frame=0, over=0, crc=0
           tx pkts=0, bytes=0, drop=0, errs=0, coll=0
"""

        def connectionsTo(self, other):
            return self._connections.get(other.name, [])

    class FakeNetwork:
        def __init__(self, switches) -> None:
            self.switches = switches
            self._index = {switch.name: switch for switch in switches}

        def get(self, name: str):
            return self._index[name]

    s1 = FakeSwitch(
        "s1",
        "0000000000000001",
        """
 1(s1-eth1): addr:aa:bb
     config:     0
     state:      LINK_DOWN
""",
    )
    s2 = FakeSwitch(
        "s2",
        "0000000000000002",
        """
 1(s2-eth1): addr:cc:dd
     config:     0
     state:      LINK_DOWN
""",
    )
    s1_intf = FakeIntf("s1-eth1")
    s2_intf = FakeIntf("s2-eth1")
    s1._connections["s2"] = [(s1_intf, s2_intf)]
    s2._connections["s1"] = [(s2_intf, s1_intf)]

    network = FakeNetwork([s1, s2])

    timestamp = wait_for_ovs_link_state(network, "s1", "s2", expected_up=False, timeout_seconds=0.01, sleep_seconds=0)

    assert timestamp is not None
