from mininet.net import Mininet
from mininet.cli import CLI
from minicps.mcps import MiniCPS
from mininet.node import OVSController, RemoteController

from .topo import SwatTopo
from .run import SwatS1CPS

import gymnasium as gym
from gymnasium.utils import seeding
from gymnasium.spaces import Dict, Discrete, Box, Tuple
from ray.rllib.env.multi_agent_env import MultiAgentEnv
from mininet.cli import CLI
import numpy as np

import sys
import os
import subprocess

import requests
import json
import time

class SingleAgentSwatEnv(gym.Env):

    def __init__(self, env, agent_id, episode_length, epsilon_start=1.0, epsilon_decay=0.9, epsilon_min=0.01):

        # self.env = net
        self.agent_id = agent_id
        self.env = env
        print("STARTING SWAT ENVIRONMENT " + str(agent_id))

        # self.observation_space = Tuple((
        #     Box(low=-0, high=float('inf'), shape=(), dtype=float),  # Latency
        #     Box(low=0, high=np.inf, shape=(), dtype=int),  # Packet count of 10 second window
        #     Dict({  # Protocol frequencies of 10 second window
        #         'ENIP': spaces.Box(low=0, high=np.inf, shape=(), dtype=int),
        #         'CIPCM': spaces.Box(low=0, high=np.inf, shape=(), dtype=int),
        #         'TCP': spaces.Box(low=0, high=np.inf, shape=(), dtype=int),
        #         'UDP': spaces.Box(low=0, high=np.inf, shape=(), dtype=int),
        #         'ICMPV6': spaces.Box(low=0, high=np.inf, shape=(), dtype=int),
        #         'other': spaces.Box(low=0, high=np.inf, shape=(), dtype=int),
        #     })
        # ))

        # self.action_space = Discrete(11)

        self.episode_length = episode_length
        self.i = 0
        self.epsilon = epsilon_start
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min

        self.seed()
        self.reset()


    def reset(self, *, seed=None, options=None):

        print("Resetting the environment")
        self.full_reset()

        self.reward = 0
        self.done = False
        self.truncated = False
        self.info = {}
        self.i = 0

        plc1 = self.env.net.get('plc1')
        plc2 = self.env.net.get('plc2')
        plc3 = self.env.net.get('plc3')
        s1 = self.env.net.get('s1')

        plc2.cmd(sys.executable + ' -u ' +' plc2.py &> logs/plc2.log &')
        plc3.cmd(sys.executable + ' -u ' + ' plc3.py  &> logs/plc3.log &')
        plc1.cmd(sys.executable + ' -u ' + ' plc1.py  &> logs/plc1.log &')
        s1.cmd(sys.executable + ' -u ' + ' physical_process.py  &> logs/process.log &')

        s1.dpctl('del-flows')

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

        time.sleep(15)

        response = requests.get(f'http://localhost:5000/metrics').json()
        
        host1 = self.env.net.get(f'plc1')
        host2 = self.env.net.get(f'plc2')
        latency = self.env.net.ping([host1, host2], timeout='0.1')

        observation = (
            latency,
            response['packet_count'],
            {
                'ENIP': response["protocol_freq"].get('ENIP', 0),
                'CIPCM': response["protocol_freq"].get('CIPCM', 0),
                'TCP': response["protocol_freq"].get('TCP', 0),
                'UDP': response["protocol_freq"].get('UDP', 0),
                'ICMPV6': response["protocol_freq"].get('ICMPV6', 0),
                'other': response["protocol_freq"].get('other', 0),
            }
        )

        print(f"Resetting the environment with state: {observation}")

        return observation, self.info
    
    def step(self, action):
        self.i += 1

        if action == 10:
            pass
        else:
            requests.post(f'http://localhost:7777/actions/{action}')

        if self.i >= self.episode_length:
            self.truncated = True
            self.done = True

        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

        if self.i >= self.episode_length:
            print(f"Episode finished after {self.i} steps with total reward: {self.reward}")

        response = requests.get(f'http://localhost:5000/metrics').json()
        
        host1 = self.env.net.get(f'plc1')
        host2 = self.env.net.get(f'plc2')
        latency = self.env.net.ping([host1, host2], timeout='0.1')

        observation = (
            latency,
            response['packet_count'],
            {
                'ENIP': response["protocol_freq"].get('ENIP', 0),
                'CIPCM': response["protocol_freq"].get('CIPCM', 0),
                'TCP': response["protocol_freq"].get('TCP', 0),
                'UDP': response["protocol_freq"].get('UDP', 0),
                'ICMPV6': response["protocol_freq"].get('ICMPV6', 0),
                'other': response["protocol_freq"].get('other', 0),
            }
        )

        # REWARD FUNCTION #

        print(f"Step {self.i} with action {action} and reward {self.reward}")

        return observation, self.reward, self.i >= self.episode_length, self.i >= self.episode_length, self.info
    
    def render(self, mode='human'):
        print('Rendering the environment')

    def cli(self):
        CLI(self.env.net)

    def seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]
    
    def close(self):
        pass
