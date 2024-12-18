"""
swat-s1 topology
"""

from mininet.topo import Topo

from utils import IP, MAC, NETMASK

class SwatTopo(Topo):
    """SWaT 3 plcs + attacker + 4 HMI nodes + private dirs."""
    def build(self):
        switch = self.addSwitch('s1')

        # PLCs
        plc1 = self.addHost(
            'plc1',
            ip=IP['plc1'] + NETMASK,
            mac=MAC['plc1'])
        self.addLink(plc1, switch)

        plc2 = self.addHost(
            'plc2',
            ip=IP['plc2'] + NETMASK,
            mac=MAC['plc2'])
        self.addLink(plc2, switch)

        plc3 = self.addHost(
            'plc3',
            ip=IP['plc3'] + NETMASK,
            mac=MAC['plc3'])
        self.addLink(plc3, switch)

        # Analysis node
        analysis = self.addHost(
            'analysis',
            ip="192.168.1.15" + NETMASK,
            mac="00:00:00:00:00:15")
        self.addLink(analysis, switch)

        # HMI nodes
        hmi1 = self.addHost(
            'hmi1',
            ip="192.168.1.50" + NETMASK,
            mac="00:00:00:00:00:50")
        self.addLink(hmi1, switch)

        hmi2 = self.addHost(
            'hmi2',
            ip="192.168.1.60" + NETMASK,
            mac="00:00:00:00:00:60")
        self.addLink(hmi2, switch)

        hmi3 = self.addHost(
            'hmi3',
            ip="192.168.1.70" + NETMASK,
            mac="00:00:00:00:00:70")
        self.addLink(hmi3, switch)

        hmi4 = self.addHost(
            'hmi4',
            ip="192.168.1.80" + NETMASK,
            mac="00:00:00:00:00:80")
        self.addLink(hmi4, switch)

        hmi5 = self.addHost(
            'attacker',
            ip=IP['attacker'] + NETMASK,
            mac=MAC['attacker'])
        self.addLink(hmi5, switch)

