from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub
from flask import Flask, jsonify, request
import threading
from collections import deque
import numpy as np

# Example for maintaining a rolling window of packet counts for each port
window_size = 20  # Number of time steps to include in the window
port_packet_counts = {port_no: deque(maxlen=window_size) for port_no in range(1, 4)}  # Assuming ports 1 to 3

app = Flask(__name__)
network_stats = {"ports": {}, "flows": {}, "tables": {}, "queues": {}, "port_packet_window": {}}

@app.route('/network/stats/<int:port_no>', methods=['GET'])
def get_network_stats(port_no):
    # Local stats
    local_stats = {
        'port': network_stats['ports'].get(port_no, {}),
        'flow': aggregate_flow_stats({k: v for k, v in network_stats['flows'].items() if str(port_no) in str(k)}),
        # 'queues': network_stats['queues'].get(port_no, {}),
        'window': network_stats['port_packet_window'].get(port_no, {})
    }

    # Global stats
    global_stats = {
        'port': aggregate_port_stats({k: v for k, v in network_stats['ports'].items() if str(port_no) not in str(k)}),
        'flow': aggregate_flow_stats({k: v for k, v in network_stats['flows'].items() if str(port_no) not in str(k)}),
        'tables': aggregate_table_stats(network_stats['tables']),
        # 'queues': aggregate_queue_stats({k: v for k, v in network_stats['queues'].items() if str(port_no) not in str(k)}),
        'window': aggregate_window_stats({k: v for k, v in network_stats['port_packet_window'].items() if str(port_no) not in str(k)})
    }

    # Combine local and global stats
    stats = {
        'local': local_stats,
        'global': global_stats
    }

    return jsonify(stats)

@app.route('/network/global_stats', methods=['GET'])
def get_global_stats():
    # Global stats
    global_stats = {
        'port': aggregate_port_stats(network_stats['ports']),
        'flow': aggregate_flow_stats(network_stats['flows']),
        'tables': aggregate_table_stats(network_stats['tables']),
        'window': aggregate_window_stats(network_stats['port_packet_window'])
    }

    return jsonify(global_stats)

def aggregate_port_stats(port_stats):
    # Aggregate port stats here
    aggregated_stats = {
        'collisions': int(np.mean([v['collisions'] for v in port_stats.values()])),
        'rx_bytes': int(np.sum([v['rx_bytes'] for v in port_stats.values()])),
        'rx_dropped': int(np.sum([v['rx_dropped'] for v in port_stats.values()])),
        'rx_errors': int(np.sum([v['rx_errors'] for v in port_stats.values()])),
        'rx_packets': int(np.sum([v['rx_packets'] for v in port_stats.values()])),
        'tx_errors': int(np.sum([v['tx_errors'] for v in port_stats.values()])),
        'tx_packets': int(np.sum([v['tx_packets'] for v in port_stats.values()])),
    }
    return aggregated_stats

def aggregate_flow_stats(flow_stats):
    # Aggregate flow stats here
    aggregated_stats = {
        'byte_count': int(np.sum([v['byte_count'] for v in flow_stats.values()])),
        'duration_nsec': float(np.mean([v['duration_nsec'] for v in flow_stats.values()])),
        'duration_sec': float(np.mean([v['duration_sec'] for v in flow_stats.values()])),
        'packet_count': int(np.sum([v['packet_count'] for v in flow_stats.values()])),
    }
    return aggregated_stats

def aggregate_table_stats(table_stats):
    # Aggregate table stats here
    aggregated_stats = {
        'active_count': int(np.sum([v['active_count'] for v in table_stats.values()])),
        'lookup_count': int(np.sum([v['lookup_count'] for v in table_stats.values()])),
        'matched_count': int(np.sum([v['matched_count'] for v in table_stats.values()])),
    }
    return aggregated_stats

def aggregate_queue_stats(queue_stats):
    # Aggregate queue stats here
    # Assuming queue_stats is a dictionary of dictionaries
    # If not, you may need to adjust this
    aggregated_stats = {k: np.mean([v[k] for v in queue_stats.values()]) for k in queue_stats.values()[0]}
    return aggregated_stats

def aggregate_window_stats(window_stats):
    # Aggregate window stats here
    aggregated_stats = {
        'average': float(np.mean([v['average'] for v in window_stats.values()])),
        'max': float(np.max([v['max'] for v in window_stats.values()])),
        'min': float(np.min([v['min'] for v in window_stats.values()])),
    }
    print(aggregated_stats)
    return aggregated_stats


def start_flask_app():
    app.run(threaded=True, port=5000)


class NetworkStatsCollector(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(NetworkStatsCollector, self).__init__(*args, **kwargs)
        self.datapaths = {}
        self.monitor_thread = hub.spawn(self._monitor_stats)
        flask_thread = threading.Thread(target=start_flask_app)
        flask_thread.daemon = True
        flask_thread.start()

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        self.datapaths[datapath.id] = datapath

    def _monitor_stats(self):
        while True:
            for dp in self.datapaths.values():
                self._request_port_stats(dp)
                self._request_flow_stats(dp)
                self._request_table_stats(dp)
                # self._request_aggregate_stats(dp)
                self._request_queue_stats(dp)
            hub.sleep(5)  # Interval for stats requests

    def _request_port_stats(self, datapath):
        parser = datapath.ofproto_parser
        req = parser.OFPPortStatsRequest(datapath, 0, ofproto_v1_3.OFPP_ANY)
        datapath.send_msg(req)

    def _request_flow_stats(self, datapath):
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    def _request_table_stats(self, datapath):
        parser = datapath.ofproto_parser
        req = parser.OFPTableStatsRequest(datapath, 0)
        datapath.send_msg(req)

    def _request_aggregate_stats(self, datapath):
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        req = parser.OFPAggregateStatsRequest(datapath, 0, match, 
                                              0, 0xffffffff, 0, ofproto_v1_3.OFPTT_ALL)
        datapath.send_msg(req)

    def _request_queue_stats(self, datapath):
        parser = datapath.ofproto_parser
        req = parser.OFPQueueStatsRequest(datapath, 0, ofproto_v1_3.OFPP_ANY, ofproto_v1_3.OFPQ_ALL)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply_handler(self, ev):
        for stat in ev.msg.body:
            network_stats["ports"][stat.port_no] = {
                "rx_packets": stat.rx_packets,
                "tx_packets": stat.tx_packets,
                "rx_bytes": stat.rx_bytes,
                "rx_dropped": stat.rx_dropped,
                "rx_errors": stat.rx_errors,
                "tx_errors": stat.tx_errors,
                "collisions": stat.collisions,
                # Include other stats as needed
            }

            # Rolling window of packet counts
            if stat.port_no in port_packet_counts:
                port_packet_counts[stat.port_no].append(stat.rx_packets + stat.tx_packets)

                windowed_stats = {}
                for port_no, counts in port_packet_counts.items():
                    if counts:
                        network_stats["port_packet_window"][port_no] = {
                            "average": np.mean(counts).item(),
                            "max": np.max(counts).item(),
                            "min": np.min(counts).item(),
                            # Add other statistical summaries as needed
                        }


    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):
        for stat in ev.msg.body:
            # Create a unique string identifier for each flow based on match criteria
            flow_id = f"{stat.match['in_port']}_{stat.match.get('ipv4_src', 'any')}_to_{stat.match.get('ipv4_dst', 'any')}"
            network_stats["flows"][flow_id] = {
                "packet_count": stat.packet_count,
                "byte_count": stat.byte_count,
                "duration_sec": stat.duration_sec,
                "duration_nsec": stat.duration_nsec,
                "idle_timeout": stat.idle_timeout,
                "hard_timeout": stat.hard_timeout,
                "priority": stat.priority,
                "flags": stat.flags,
                # Include additional stats as needed
            }

    @set_ev_cls(ofp_event.EventOFPTableStatsReply, MAIN_DISPATCHER)
    def table_stats_reply_handler(self, ev):
        table = ev.msg.body[0]
        network_stats["tables"][0] = {
            "active_count": table.active_count,
            "lookup_count": table.lookup_count,
            "matched_count": table.matched_count,
            # Include other relevant stats
        }
    
    @set_ev_cls(ofp_event.EventOFPAggregateStatsReply, MAIN_DISPATCHER)
    def aggregate_stats_reply_handler(self, ev):
        stats = ev.msg.body
        network_stats["aggregate"] = {
            "packet_count": stats.packet_count,
            "byte_count": stats.byte_count,
            "flow_count": stats.flow_count,
        }

    @set_ev_cls(ofp_event.EventOFPQueueStatsReply, MAIN_DISPATCHER)
    def queue_stats_reply_handler(self, ev):
        for stat in ev.msg.body:
            network_stats["queues"][stat.port_no][stat.queue_id] = {
                "tx_bytes": stat.tx_bytes,
                "tx_packets": stat.tx_packets,
                "tx_errors": stat.tx_errors,
            }

    def limit_rate_all_ports(self, datapath, rate):
        """Limit the rate of packets on all ports on a specific switch."""
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        # Add a meter to limit the rate of packets
        meter_mod = ofp_parser.OFPMeterMod(datapath=datapath, command=ofp.OFPMC_ADD,
                                            flags=ofp.OFPMF_KBPS, meter_id=1,
                                            bands=[ofp_parser.OFPMeterBandDrop(rate=rate, burst_size=10)])
        datapath.send_msg(meter_mod)

        # Get list of all ports on the switch
        ports = datapath.ports

        for port_no in ports:
            # Add a flow rule that uses the meter for each port
            match = ofp_parser.OFPMatch(in_port=port_no)
            actions = [ofp_parser.OFPActionOutput(ofp.OFPP_CONTROLLER)]
            inst = [ofp_parser.OFPInstructionMeter(meter_id=1),
                    ofp_parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
            mod = ofp_parser.OFPFlowMod(datapath=datapath, priority=1, match=match, instructions=inst)
            datapath.send_msg(mod)




