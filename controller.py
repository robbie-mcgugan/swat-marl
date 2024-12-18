from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from scapy.all import *
from scapy.layers.inet import IP, TCP, UDP, ICMP
from scapy.layers.l2 import Ether, ARP
import time
from flask import Flask, jsonify, request

import threading


flask_app = Flask(__name__)

class MininetController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(MininetController, self).__init__(*args, **kwargs)
        self.packet_count = 0
        self.rate_limit_levels = [1000, 5000, 10000, 50000, 100000]  # in Kbps
        self.priority_levels = [1, 2, 3, 4, 5]
        self.current_rate_limit = 100000 
        self.current_priority = 1

        self.lock = threading.Lock()
        
        # Start Flask in a separate thread
        self.flask_thread = threading.Thread(target=self.run_flask)
        self.flask_thread.start()

    def run_flask(self):
        flask_app.run(host='0.0.0.0', port=7777, threaded=True)
        

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Install table-miss flow entry
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_oflow(datapath, 0, match, actions)

    def add_oflow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]
        if buffer_id:
            mod = parser.OFPFlowMod(datapath=datapath, buffer_id=buffer_id,
                                    priority=priority, match=match,
                                    instructions=inst)
        else:
            mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                    match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        # Use Scapy to parse the packet
        scapy_pkt = Ether(msg.data)

        # Extract packet information
        packet_data = self.extract_packet_info(scapy_pkt, in_port)

        # Log the packet information
        self.logger.info("Packet Info: %s", packet_data)

        # Forward the packet (simple flooding)
        out_port = ofproto.OFPP_FLOOD
        actions = [parser.OFPActionOutput(out_port)]
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    def extract_packet_info(self, pkt, in_port):
        self.packet_count += 1
        packet_data = {
            "interface": f"s1-eth{in_port}",  # Assuming switch 1, modify as needed
            "no": self.packet_count,
            "time": time.time(),
            "source": pkt.src,
            "destination": pkt.dst,
            "protocol": "Unknown",
            "length": len(pkt),
            "info": ""
        }

        # Use Scapy's guess_payload_class to identify the highest layer
        highest_layer = pkt

        # Get the name of the highest layer protocol
        protocol_name = highest_layer.name

        # Set protocol and extract relevant information
        packet_data["protocol"] = protocol_name

        if IP in pkt:
            packet_data["source"] = pkt[IP].src
            packet_data["destination"] = pkt[IP].dst

        if TCP in pkt:
            packet_data["info"] = f"Src Port: {pkt[TCP].sport}, Dst Port: {pkt[TCP].dport}"
        elif UDP in pkt:
            packet_data["info"] = f"Src Port: {pkt[UDP].sport}, Dst Port: {pkt[UDP].dport}"
        elif ICMP in pkt:
            packet_data["info"] = f"Type: {pkt[ICMP].type}, Code: {pkt[ICMP].code}"
        elif ARP in pkt:
            packet_data["info"] = f"Who has {pkt[ARP].pdst}? Tell {pkt[ARP].psrc}"

        # Handle industrial protocols
        # if ENIP_TCP in pkt:
        #     packet_data["info"] = f"ENIP Command: {pkt[ENIP].command}"
        #     self.logger.info("ENIP Packet Detected: %s", pkt.summary())
        # elif CIP in pkt:
        #     packet_data["info"] = f"CIP Service: {pkt[CIP].service}"
        #     self.logger.info("CIP Packet Detected: %s", pkt.summary())

        # If no specific handling, provide a generic info
        if not packet_data["info"]:
            packet_data["info"] = f"Identified as {protocol_name}"

        return packet_data
    
    @flask_app.route('/actions/<int:action>', methods=['POST'])
    def take_action(self, action):
        with self.lock:
            if 0 <= action < 5:
                self.adjust_rate_limit(action)
            elif 5 <= action < 10:
                self.adjust_priority(action - 5)
    
    def adjust_rate_limit(self, action):
        new_rate = self.rate_limit_levels[action]
        if new_rate != self.current_rate_limit:
            self.current_rate_limit = new_rate
            self.apply_rate_limit()

    def adjust_priority(self, action):
        new_priority = self.priority_levels[action]
        if new_priority != self.current_priority:
            self.current_priority = new_priority
            self.apply_prioritization()

    def apply_rate_limit(self):
        # Remove existing meter if any
        meter_mod = self.parser.OFPMeterMod(
            self.datapath,
            command=self.ofproto.OFPMC_DELETE,
            flags=self.ofproto.OFPMF_KBPS,
            meter_id=1
        )
        self.datapath.send_msg(meter_mod)

        # Add new meter
        meter_mod = self.parser.OFPMeterMod(
            self.datapath,
            command=self.ofproto.OFPMC_ADD,
            flags=self.ofproto.OFPMF_KBPS,
            meter_id=1,
            bands=[self.parser.OFPMeterBandDrop(rate=self.current_rate_limit)]
        )
        self.datapath.send_msg(meter_mod)

        # Apply meter to all traffic
        match = self.parser.OFPMatch()
        actions = [self.parser.OFPActionMeter(1)]
        self.add_flow(match, actions, priority=1)

    def apply_prioritization(self):
        # Prioritize established connections
        match_established = self.parser.OFPMatch(
            eth_type=0x0800,
            ip_proto=6,
            tcp_flags=(self.ofproto.TCP_ACK, self.ofproto.TCP_ACK)
        )
        actions_established = [self.parser.OFPActionSetQueue(0)]  # Highest priority queue
        self.add_flow(match_established, actions_established, priority=self.current_priority + 1)

        # Set lower priority for non-established connections
        match_non_established = self.parser.OFPMatch(
            eth_type=0x0800,
            ip_proto=6
        )
        actions_non_established = [self.parser.OFPActionSetQueue(self.current_priority)]
        self.add_flow(match_non_established, actions_non_established, priority=self.current_priority)

    def add_flow(self, match, actions, priority=1):
        inst = [self.parser.OFPInstructionActions(self.ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = self.parser.OFPFlowMod(
            datapath=self.datapath,
            priority=priority,
            match=match,
            instructions=inst
        )
        self.datapath.send_msg(mod)