"""
swat-s1 topology
"""

from mininet.topo import Topo
from mininet.link import TCLink

from .utils import IP, MAC, NETMASK


class SwatTopo(Topo):

    """SWaT 3 plcs + attacker + private dirs."""

    def build(self):

        switch = self.addSwitch('s1')

        plc1 = self.addHost(
            'plc1',
            ip=IP['plc1'] + NETMASK,
            mac=MAC['plc1'])
        self.addLink(plc1, switch, cls=TCLink, bw=10)

        plc2 = self.addHost(
            'plc2',
            ip=IP['plc2'] + NETMASK,
            mac=MAC['plc2'])
        self.addLink(plc2, switch, cls=TCLink, bw=10)

        plc3 = self.addHost(
            'plc3',
            ip=IP['plc3'] + NETMASK,
            mac=MAC['plc3'])
        self.addLink(plc3, switch, cls=TCLink, bw=10)

        attacker = self.addHost(
            'attacker',
            ip=IP['attacker'] + NETMASK,
            mac=MAC['attacker'])
        self.addLink(attacker, switch)

        sources = self.addHost(
            'sources',
            ip=IP['sources'] + NETMASK,
            mac=MAC['sources'])
        self.addLink(sources, switch)
