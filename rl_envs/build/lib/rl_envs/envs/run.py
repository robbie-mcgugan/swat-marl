"""
swat-s1 run.py
"""

from mininet.net import Mininet
from mininet.cli import CLI
from minicps.mcps import MiniCPS
from mininet.node import OVSController, RemoteController

from .topo import SwatTopo


import sys


class SwatS1CPS(MiniCPS):

    """Main container used to run the simulation."""

    def __init__(self, name, net):

        self.name = name
        self.net = net

        net.start()

        # net.pingAll()

        # start devices
        plc1, plc2, plc3, s1, attacker = self.net.get(
            'plc1', 'plc2', 'plc3', 's1', 'attacker')

        # SPHINX_SWAT_TUTORIAL RUN(
        plc2.cmd(sys.executable + ' -u ' +'rl_envs/rl_envs/envs/plc2.py &> logs/plc2.log &')
        plc3.cmd(sys.executable + ' -u ' + 'rl_envs/rl_envs/envs/plc3.py  &> logs/plc3.log &')
        plc1.cmd(sys.executable + ' -u ' + 'rl_envs/rl_envs/envs/plc1.py  &> logs/plc1.log &')
        s1.cmd(sys.executable + ' -u ' + 'rl_envs/rl_envs/envs/physical_process.py  &> logs/process.log &')
        # SPHINX_SWAT_TUTORIAL RUN)
        # CLI(self.net)

        s1.cmd('ovs-ofctl --protocols=OpenFlow13 add-flow s1 priority=10,ip,in_port=1,actions=output:2,3,4,5')
        s1.cmd('ovs-ofctl --protocols=OpenFlow13 add-flow s1 priority=10,ip,in_port=2,actions=output:1,3,4,5')
        s1.cmd('ovs-ofctl --protocols=OpenFlow13 add-flow s1 priority=10,ip,in_port=3,actions=output:1,2,4,5')
        s1.cmd('ovs-ofctl --protocols=OpenFlow13 add-flow s1 priority=10,ip,in_port=4,actions=output:1,2,3,5')
        s1.cmd('ovs-ofctl --protocols=OpenFlow13 add-flow s1 priority=10,ip,in_port=5,actions=output:1,2,3,4')

        s1.cmd('ovs-ofctl --protocols=OpenFlow13 add-flow s1 priority=10,arp,in_port=1,actions=output:2,3,4,5')
        s1.cmd('ovs-ofctl --protocols=OpenFlow13 add-flow s1 priority=10,arp,in_port=2,actions=output:1,3,4,5')
        s1.cmd('ovs-ofctl --protocols=OpenFlow13 add-flow s1 priority=10,arp,in_port=3,actions=output:1,2,4,5')
        s1.cmd('ovs-ofctl --protocols=OpenFlow13 add-flow s1 priority=10,arp,in_port=4,actions=output:1,2,3,5')
        s1.cmd('ovs-ofctl --protocols=OpenFlow13 add-flow s1 priority=10,arp,in_port=5,actions=output:1,2,3,4')


    def reset(self):
        self.net.stop()

        self.net = Mininet(topo=self.TOPO, controller=self.controller)

        self.net.start()

