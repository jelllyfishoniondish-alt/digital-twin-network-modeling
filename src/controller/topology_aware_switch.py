"""Topology-aware OpenFlow 1.3 controller for looped data-driven experiments."""

from __future__ import annotations

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, DEAD_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.lib.packet import ethernet, ether_types, packet
from ryu.ofproto import ofproto_v1_3
from ryu.topology import event
from ryu.topology.api import get_link, get_switch

from src.controller.event_queue import publish_controller_event
from src.controller.topology_routing import LinkAttachment, TopologyRoutingState


class TopologyAwareSwitch(app_manager.RyuApp):
    """Minimal shortest-path controller with spanning-tree flooding for unknown destinations."""

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    FLOW_COOKIE = 0x5457494E

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.routing_state = TopologyRoutingState()
        self.datapaths = {}

    def _refresh_links(self) -> None:
        links = []
        for link in get_link(self, None):
            links.append(
                LinkAttachment(
                    src_switch=str(link.src.dpid),
                    src_port=link.src.port_no,
                    dst_switch=str(link.dst.dpid),
                    dst_port=link.dst.port_no,
                )
            )
        self.routing_state.replace_links(links)
        switch_ports = {}
        for switch in get_switch(self, None):
            switch_id = str(switch.dp.id)
            switch_ports[switch_id] = {
                port.port_no
                for port in switch.ports
                if port.port_no < ofproto_v1_3.OFPP_MAX and port.port_no != ofproto_v1_3.OFPP_LOCAL
            }
        self.routing_state.replace_switch_ports(switch_ports)
        self.logger.info(
            "Topology refresh: adjacency=%s switch_ports=%s",
            self.routing_state.adjacency,
            {switch_id: sorted(ports) for switch_id, ports in self.routing_state.switch_ports.items()},
        )
        self._clear_runtime_flows()

    def _clear_runtime_flows(self) -> None:
        for datapath in self.datapaths.values():
            parser = datapath.ofproto_parser
            ofproto = datapath.ofproto
            message = parser.OFPFlowMod(
                datapath=datapath,
                command=ofproto.OFPFC_DELETE,
                cookie=self.FLOW_COOKIE,
                cookie_mask=0xFFFFFFFFFFFFFFFF,
                out_port=ofproto.OFPP_ANY,
                out_group=ofproto.OFPG_ANY,
                match=parser.OFPMatch(),
            )
            datapath.send_msg(message)

    def _add_flow(self, datapath, priority: int, match, actions, cookie: int = 0) -> None:
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        instructions = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        flow_mod = parser.OFPFlowMod(
            datapath=datapath,
            cookie=cookie,
            priority=priority,
            match=match,
            instructions=instructions,
        )
        datapath.send_msg(flow_mod)

    def _datapath_by_id(self, switch_id: str):
        try:
            return self.datapaths.get(int(switch_id))
        except ValueError:
            return None

    def _install_path(self, path: list[str], src_mac: str, dst_mac: str) -> None:
        if not path:
            return
        for switch_id in path:
            datapath = self._datapath_by_id(switch_id)
            if datapath is None:
                continue
            out_port = self.routing_state.output_port_for_path(path, switch_id, dst_mac)
            if out_port is None:
                continue
            parser = datapath.ofproto_parser
            match = parser.OFPMatch(eth_src=src_mac, eth_dst=dst_mac)
            actions = [parser.OFPActionOutput(out_port)]
            self._add_flow(datapath, priority=10, match=match, actions=actions, cookie=self.FLOW_COOKIE)

    def _path_for_destination(self, src_switch: str, dst_switch: str) -> list[str] | None:
        """Return the path used for known unicast forwarding."""

        return self.routing_state.shortest_path(src_switch, dst_switch)

    def _packet_out(self, datapath, in_port: int, actions, data) -> None:
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        packet_out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=ofproto.OFP_NO_BUFFER,
            in_port=in_port,
            actions=actions,
            data=data,
        )
        datapath.send_msg(packet_out)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, event_message) -> None:
        datapath = event_message.datapath
        if event_message.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
            publish_controller_event("STATE_CHANGE", datapath_id=datapath.id, state="MAIN")
        elif event_message.state == DEAD_DISPATCHER:
            self.datapaths.pop(datapath.id, None)
            publish_controller_event("STATE_CHANGE", datapath_id=datapath.id, state="DEAD")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, event_message) -> None:
        datapath = event_message.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(datapath, priority=0, match=match, actions=actions)

    @set_ev_cls(event.EventSwitchEnter)
    @set_ev_cls(event.EventSwitchLeave)
    @set_ev_cls(event.EventLinkAdd)
    @set_ev_cls(event.EventLinkDelete)
    def topology_change_handler(self, _event_message) -> None:
        publish_controller_event("TOPOLOGY_CHANGE", topology_event=type(_event_message).__name__)
        self._refresh_links()

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def port_status_handler(self, event_message) -> None:
        reason = getattr(event_message.msg, "reason", None)
        desc = getattr(event_message.msg, "desc", None)
        publish_controller_event(
            "PORT_STATUS",
            datapath_id=event_message.msg.datapath.id,
            port_no=getattr(desc, "port_no", None),
            reason=reason,
        )

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, event_message) -> None:
        message = event_message.msg
        datapath = message.datapath
        parser = datapath.ofproto_parser
        in_port = message.match["in_port"]
        switch_id = str(datapath.id)

        pkt = packet.Packet(message.data)
        ethernet_frame = pkt.get_protocol(ethernet.ethernet)
        if ethernet_frame is None or ethernet_frame.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        src_mac = ethernet_frame.src
        dst_mac = ethernet_frame.dst
        is_host_facing = self.routing_state.is_host_facing_port(switch_id, in_port)
        self.logger.info(
            "PacketIn switch=%s in_port=%s src=%s dst=%s host_facing=%s",
            switch_id,
            in_port,
            src_mac,
            dst_mac,
            is_host_facing,
        )
        if is_host_facing:
            self.routing_state.learn_host(src_mac, switch_id=switch_id, port_no=in_port)
            self.logger.info("Learned host %s at %s/%s", src_mac, switch_id, in_port)

        dst_attachment = self.routing_state.host_locations.get(dst_mac)
        if dst_attachment is not None:
            path = self._path_for_destination(switch_id, dst_attachment.switch_id)
            if path is not None:
                self._install_path(path, src_mac, dst_mac)
                reverse_path = list(reversed(path))
                self._install_path(reverse_path, dst_mac, src_mac)
                out_port = self.routing_state.output_port_for_path(path, switch_id, dst_mac)
                if out_port is not None:
                    self.logger.info(
                        "Known destination %s via path=%s out_port=%s",
                        dst_mac,
                        path,
                        out_port,
                    )
                    actions = [parser.OFPActionOutput(out_port)]
                    self._packet_out(datapath, in_port=in_port, actions=actions, data=message.data)
                    return

        flood_ports = self.routing_state.flood_ports(switch_id, in_port=in_port)
        self.logger.info("Flooding src=%s dst=%s on switch=%s ports=%s", src_mac, dst_mac, switch_id, flood_ports)
        if not flood_ports:
            return
        actions = [parser.OFPActionOutput(port_no) for port_no in flood_ports]
        self._packet_out(datapath, in_port=in_port, actions=actions, data=message.data)
