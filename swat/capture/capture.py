import pyshark
import threading
from datetime import datetime, timedelta
from queue import Queue
from typing import List, Optional
from collections import deque
from dataclasses import dataclass
from threading import Lock

@dataclass
class PacketData:
    timestamp: datetime
    interface: str
    protocol: str
    length: int
    src_ip: str = None
    dst_ip: str = None
    is_cip: bool = False
    is_request: bool = False
    cip_info: dict = None

class TrafficWindow:
    def __init__(self, window_seconds: int = 30):
        self.window_seconds = window_seconds
        self.packets = deque()
        self.lock = Lock()
        
    def add_packet(self, packet: PacketData) -> None:
        with self.lock:
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(seconds=self.window_seconds)
            
            # Remove old packets
            while self.packets and self.packets[0].timestamp < cutoff_time:
                self.packets.popleft()
            
            # Add new packet
            self.packets.append(packet)

    def restart(self) -> None:
        """
        Clear all stored packets and reset the traffic window to its initial state.
        This allows the capture to start fresh as if it was just initialized.
        """
        with self.lock:
            self.packets.clear()
    
    def get_metrics(self, interface=None) -> dict:
        with self.lock:
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(seconds=self.window_seconds)

            interface_formatted = f"s1-eth{interface}" if interface is not None else None
            
            # Filter packets by interface if specified
            filtered_packets = [p for p in self.packets if interface is None or p.interface == interface_formatted]
            
            # Calculate inter-arrival times
            timestamps = sorted([p.timestamp for p in filtered_packets])
            inter_arrival_times = []
            if len(timestamps) > 1:
                inter_arrival_times = [(timestamps[i] - timestamps[i-1]).total_seconds() 
                                     for i in range(1, len(timestamps))]
            
            # Basic metrics
            total_packets = len(filtered_packets)
            cip_packets = sum(1 for p in filtered_packets if p.is_cip)
            cip_requests = sum(1 for p in filtered_packets if p.is_request)
            cip_responses = cip_packets - cip_requests  # Derive responses
            
            # Calculate requested metrics
            avg_inter_arrival = sum(inter_arrival_times) / len(inter_arrival_times) if inter_arrival_times else 0
            
            # Calculate ratios
            cip_ratio = cip_packets / total_packets if total_packets > 0 else 0
            request_ratio = cip_requests / total_packets if total_packets > 0 else 0
            response_ratio = cip_responses / total_packets if total_packets > 0 else 0
            request_response_ratio = cip_requests / cip_responses if cip_responses > 0 else 0

            return {
                'packet_count': total_packets,
                'avg_inter_arrival_time': avg_inter_arrival,
                'cipcm_ratio': cip_ratio,
                'request_ratio': request_ratio,
                'response_ratio': response_ratio,
                'request_response_ratio': request_response_ratio
            }

class PacketCapture:
    def __init__(self, interfaces: List[str]):
        self.interfaces = interfaces
        self.packet_queue = Queue()
        self.stop_event = threading.Event()
        self.threads = []
        self.traffic_window = TrafficWindow()

    def process_packet(self, packet, interface: str) -> None:
        """Process each captured packet and identify CIP packets."""
        try:
            timestamp = datetime.fromtimestamp(float(packet.sniff_timestamp))
            protocol = packet.highest_layer
            
            # Create packet data object
            packet_data = PacketData(
                timestamp=timestamp,
                interface=interface,
                protocol=protocol,
                length=len(packet)
            )

            # Network layer info
            if 'IP' in packet:
                packet_data.src_ip = packet.ip.src
                packet_data.dst_ip = packet.ip.dst
            elif 'IPv6' in packet:
                packet_data.src_ip = packet.ipv6.src
                packet_data.dst_ip = packet.ipv6.dst

            # Check for CIP layer
            cip_info = {}
            for layer in packet.layers:
                layer_name = layer.layer_name.upper()
                if 'CIP' in layer_name:
                    packet_data.is_cip = True
                    
                    # Extract CIP-specific information
                    for field_name in layer.field_names:
                        try:
                            value = getattr(layer, field_name)
                            cip_info[field_name] = value
                        except AttributeError:
                            continue
            
            if packet_data.is_cip:
                packet_data.cip_info = cip_info
                # Check if it's a read request (0x4C)
                if 'cip_service' in cip_info and cip_info['cip_service'].lower() == '0x4c':
                    packet_data.is_request = True
                self._print_cip_info(packet_data)

            # Add packet to the traffic window
            self.traffic_window.add_packet(packet_data)
            
            # Also add to queue for any other processing
            self.packet_queue.put(packet_data)

        except AttributeError as e:
            print(f"Error processing packet on {interface}: {str(e)}")

    def _print_cip_info(self, packet_data: PacketData) -> None:
        # """Print CIP packet information."""
        # print(f"\nCIP Packet Detected on {packet_data.interface}:")
        # print(f"Timestamp: {packet_data.timestamp}")
        # print(f"Protocol: {packet_data.protocol}")
        # print(f"Type: {'Request' if packet_data.is_request else 'Response'}")
        # print("CIP Information:")
        # for key, value in packet_data.cip_info.items():
        #     print(f"  {key}: {value}")
        # print("-" * 50)
        pass

    def capture_on_interface(self, interface: str, packet_count: Optional[int] = None) -> None:
        """Capture packets on a specific interface."""
        try:
            capture = pyshark.LiveCapture(interface=interface)
            
            for packet in capture.sniff_continuously(packet_count=packet_count):
                if self.stop_event.is_set():
                    break
                self.process_packet(packet, interface)
                
        except Exception as e:
            print(f"Error capturing on interface {interface}: {str(e)}")

    def start_capture(self, packet_count: Optional[int] = None) -> None:
        """Start packet capture on all interfaces."""
        print(f"Starting capture on interfaces: {', '.join(self.interfaces)}")
        
        for interface in self.interfaces:
            thread = threading.Thread(
                target=self.capture_on_interface,
                args=(interface, packet_count)
            )
            thread.daemon = True
            thread.start()
            self.threads.append(thread)

    def stop_capture(self) -> None:
        """Stop packet capture on all interfaces."""
        self.stop_event.set()
        for thread in self.threads:
            thread.join()
        print("\nCapture stopped on all interfaces")

    def get_current_metrics(self, interface: str = None) -> dict:
        """Get metrics for all interfaces or a specific interface."""
        return self.traffic_window.get_metrics(interface)
    
    def restart_capture(self) -> None:
        """
        Clear all stored packets and reset the traffic window,
        allowing the capture to start fresh without stopping the capture threads.
        """
        # Clear the packet queue
        while not self.packet_queue.empty():
            try:
                self.packet_queue.get_nowait()
            except Queue.Empty:
                break
                
        # Reset the traffic window
        self.traffic_window.restart()
        
        print("Capture data cleared - starting fresh")

def main():
    # Example usage
    interfaces = ['s1-eth1', 's1-eth2', 's1-eth3']  # Replace with your interface names
    
    capture = PacketCapture(interfaces)
    
    try:
        capture.start_capture()

        i = 0
        
        # Example of periodically printing metrics
        while True:
            # Print combined metrics
            print("\n=== Combined Interface Metrics ===")
            metrics = capture.get_current_metrics()
            print_metrics(metrics)

            # Print per-interface metrics
            for interface in [1]:
                print(f"\n=== Interface {interface} Metrics ===")
                metrics = capture.get_current_metrics(interface)
                print_metrics(metrics)

            
            # Wait for 5 seconds before next metrics update
            import time
            time.sleep(5)

            
    except KeyboardInterrupt:
        print("\nStopping capture...")
        capture.stop_capture()
        print("Capture completed")

def print_metrics(metrics):
    """Helper function to print metrics in a consistent format."""
    print(f"Total Packets: {metrics['total_packets']}")
    print(f"Avg Inter-arrival Time: {metrics['avg_inter_arrival_time']:.6f} seconds")
    print(f"CIP/Total Ratio: {metrics['cip_ratio']:.4f}")
    print(f"Request/CIP Ratio: {metrics['request_ratio']:.4f}")
    print(f"Response/CIP Ratio: {metrics['response_ratio']:.4f}")
    print(f"Request/Response Ratio: {metrics['request_response_ratio']:.4f}")

# if __name__ == "__main__":
#     main()