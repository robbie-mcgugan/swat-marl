from mininet.net import Mininet
from mininet.cli import CLI
from minicps.mcps import MiniCPS
from mininet.node import OVSController, RemoteController

import gymnasium as gym
from gymnasium import spaces
from mininet.cli import CLI

import sys
import subprocess

import numpy as np
import requests
import json

import time
import math
import random

from typing import Optional
from topo import SwatTopo
import ray
from collections import deque 

from dotenv import load_dotenv
import os

# Load variables from .env file
load_dotenv() 

class SwatS1CPS(MiniCPS):

    """Main container used to run the simulation."""

    def __init__(self, name, net):

        self.name = name
        self.net = net

        net.start()

        # start devices
        plc1, plc2, plc3, s1 = self.net.get(
            'plc1', 'plc2', 'plc3', 's1',)
        

        # plc1.cmd(f'tc qdisc add dev s1-eth1 root handle 1: htb default 1')
        # plc1.cmd(f'tc class add dev s1-eth1 parent 1: classid 1:1 htb rate 100kbit')

        # SPHINX_SWAT_TUTORIAL RUN(
        s1.cmd(f'cd {os.getenv('PLC_FILE_PATH')} && ' + sys.executable + ' -u ' + ' physical_process.py  &> logs/process.log &')
        plc2.cmd(f'cd {os.getenv('PLC_FILE_PATH')} && ' + sys.executable + ' -u ' +' plc2.py &> logs/plc2.log &')
        plc3.cmd(f'cd {os.getenv('PLC_FILE_PATH')} && ' + sys.executable + ' -u ' + ' plc3.py  &> logs/plc3.log &')
        plc1.cmd(f'cd {os.getenv('PLC_FILE_PATH')} && ' + sys.executable + ' -u ' + ' plc1.py &> logs/plc1.log &')
        # attacker.cmd(sys.executable + ' -u ' + ' hmi.py  &> logs/attacker.log &')

        # attacker.cmd(sys.executable + ' -u ' + ' dos.py  &> logs/attacker.log &')

        # SPHINX_SWAT_TUTORIAL RUN)


        s1.dpctl('del-flows')

        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 "priority=100,ip,nw_dst=192.168.1.10,actions=output:1"')
        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 "priority=100,ip,nw_dst=192.168.1.20,actions=output:2"')
        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 "priority=100,ip,nw_dst=192.168.1.30,actions=output:3"')
        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 "priority=100,ip,nw_dst=192.168.1.70,actions=output:4"')
        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 "priority=100,ip,nw_dst=192.168.1.15,actions=output:5"')

        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 arp,in_port=1,actions=output:2,3,4,5')
        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 arp,in_port=2,actions=output:1,3,4,5')
        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 arp,in_port=3,actions=output:1,2,4,5')
        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 arp,in_port=4,actions=output:1,2,3,5')
        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 arp,in_port=5,actions=output:1,2,3,4')


        # s1.cmd(f'ovs-ofctl -O OpenFlow13 add-meter s1 meter=1,kbps,burst,stats,bands=type=drop,rate=10000,burst_size=100')

        # s1.cmd(f'ovs-ofctl -O OpenFlow13 add-flow s1 "cookie=1,priority=101,ip,nw_src=192.168.1.70,nw_dst=192.168.1.10,actions=meter:1,output:5"')

        CLI(self.net)



class SwatEnv(gym.Env):

    def __init__(self, agent_id, episode_length, epsilon_start=1.0, epsilon_decay=0.9, epsilon_min=0.01):

        # self.env = net
        self.agent_id = agent_id
        topo = SwatTopo()
        net = Mininet(topo=topo)
        self.env = SwatS1CPS(name='swat_s1', net=net)

        self.observation_space = spaces.Tuple((
            spaces.Box(low=-0, high=np.inf, shape=(), dtype=float), 
            spaces.Box(low=0, high=1.0, shape=(), dtype=float),  
            spaces.Box(low=0, high=np.inf, shape=(), dtype=int), 
            spaces.Box(low=0, high=1.0, shape=(), dtype=float), 
            spaces.Box(low=0, high=np.inf, shape=(), dtype=float),  
            spaces.Box(low=0, high=1.0, shape=(), dtype=float),  
        ))

        self.action_space = spaces.Tuple((
            spaces.Box(low=0, high=2, shape=(1,), dtype=int),  # Add or remove
            spaces.Box(low=1, high=2, shape=(1,), dtype=int),  # Flow ID: 1-4
            spaces.Box(low=6, high=8, shape=(1,), dtype=int),  # IP number: -1-4
        ))

        self.episode_length = episode_length
        self.i = 0
        self.flow_rate_limits = [1000, 1000, 1000, 1000]
        self.epsilon = epsilon_start
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.info = {}
        window_size=50

        # Define normal operating ranges
        self.normal_ranges = {
            'avg_inter_arrival_time': (0.020, 0.025),    # Around 0.022
            'cipcm_ratio': (0.15, 0.18),                 # Around 0.166
            'packet_count': (1000, 1500),                # Around 1300
            'request_ratio': (0.07, 0.09),               # Around 0.083
            'request_response_ratio': (0.9, 1.1),        # Around 1.0
            'response_ratio': (0.07, 0.09)               # Around 0.083
        }
        
        # Define attack indicators
        self.attack_indicators = {
            'avg_inter_arrival_time': 0.004,    # Very small inter-arrival
            'cipcm_ratio': 0.077,               # Low CIP ratio
            'packet_count': 8000,               # Very high packet count
            'request_response_ratio': 12.0,     # High req/resp ratio
            'response_ratio': 0.006             # Low response ratio
        }
        
        self.metric_history = {
            'avg_inter_arrival_time': deque(maxlen=window_size),
            'cipcm_ratio': deque(maxlen=window_size),
            'packet_count': deque(maxlen=window_size),
            'request_ratio': deque(maxlen=window_size),
            'request_response_ratio': deque(maxlen=window_size),
            'response_ratio': deque(maxlen=window_size)
        }

        print("Waiting for the CAPTURE to start")
        time.sleep(20)


    def reset(self, *, seed=None, options=None):
        self.reward = 0
        self.done = False
        self.truncated = False
        self.info = {}
        self.i = 0
        window_size=50

        self.metric_history = {
            'avg_inter_arrival_time': deque(maxlen=window_size),
            'cipcm_ratio': deque(maxlen=window_size),
            'packet_count': deque(maxlen=window_size),
            'request_ratio': deque(maxlen=window_size),
            'request_response_ratio': deque(maxlen=window_size),
            'response_ratio': deque(maxlen=window_size)
        }

        plc1 = self.env.net.get('plc1')
        plc2 = self.env.net.get('plc2')
        plc3 = self.env.net.get('plc3')
        s1 = self.env.net.get('s1')
        attackers = ['hmi1', 'hmi2', 'hmi3', 'hmi4', 'hmi5']
        random_attacker = random.choice(attackers)
        attacker = self.env.net.get(random_attacker)

        self.attacker = attacker

        attacker.cmd('pkill -9 -f dos.py')
        attacker.cmd('pkill -9 -f oscilating_dos.py')

        plc2.cmd('pkill -9 -f plc2.py')
        plc2.cmd(f'cd {os.getenv('PLC_FILE_PATH')} && ' + sys.executable + ' -u ' +' plc2.py &> logs/plc2.log &')

        plc3.cmd('pkill -9 -f plc3.py')
        plc3.cmd(f'cd {os.getenv('PLC_FILE_PATH')} && ' + sys.executable + ' -u ' + ' plc3.py  &> logs/plc3.log &')

        plc1.cmd('pkill -9 -f plc1.py')
        plc1.cmd(f'cd {os.getenv('PLC_FILE_PATH')} && ' + sys.executable + ' -u ' + ' plc1.py &> logs/plc1.log &')

        s1.cmd('pkill -9 -f physical_process.py')
        s1.cmd(f'cd {os.getenv('PLC_FILE_PATH')} && ' + sys.executable + ' -u ' + ' physical_process.py  &> logs/process.log &')

        requests.get('http://localhost:5000/restart')

        s1.dpctl('del-flows')

        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 "priority=100,ip,nw_dst=192.168.1.10,actions=output:1"')
        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 "priority=100,ip,nw_dst=192.168.1.20,actions=output:2"')
        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 "priority=100,ip,nw_dst=192.168.1.30,actions=output:3"')
        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 "priority=100,ip,nw_dst=192.168.1.70,actions=output:4"')
        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 "priority=100,ip,nw_dst=192.168.1.15,actions=output:5"')

        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 arp,in_port=1,actions=output:2,3,4,5')
        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 arp,in_port=2,actions=output:1,3,4,5')
        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 arp,in_port=3,actions=output:1,2,4,5')
        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 arp,in_port=4,actions=output:1,2,3,5')
        s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 arp,in_port=5,actions=output:1,2,3,4')


        observation = (0, 0, 0, 0, 0, 0) 

        return observation, self.info

    def step(self, action):
        self.i += 1

        
        decision, flow_id, ip_number = action

        if random.random() < self.epsilon:
            decision = random.randint(1, 2)
            flow_id = random.randint(1, 3)
            ip_number = random.randint(6, 8)

        if decision == 0:
            pass
        elif decision == 1:
            self.remove_aux_flow(flow_id)
        else:
            self.add_aux_flow(flow_id, ip_number)

        time.sleep(30)

        if self.i >= self.episode_length:
            self.truncated = True
            self.done = True

        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

        response = requests.get(f'http://localhost:5000/metrics').json()

        observation = (
            response['avg_inter_arrival_time'],
            response['cipcm_ratio'],
            response['packet_count'],
            response['request_ratio'],
            response['request_response_ratio'],
            response['response_ratio']
        )

        # Combine immediate and trend rewards
        immediate_reward = self.calculate_immediate_reward(response)
        trend_reward = self.calculate_trend_reward(response)
        
        # Weight immediate state (60%) and trends (40%)
        self.reward = (0.6 * immediate_reward + 0.4 * trend_reward)

        print(f"Step {self.i} with action {action} and reward {self.reward}")
        print(f"New state: {observation}")


        if self.i == 2:
            if random.random() < 0.5:
                self.attacker.cmd(f'cd {os.getenv('PLC_FILE_PATH')} && ' + sys.executable + ' -u ' + ' dos.py  &> logs/attacker.log &')
            else:
                self.attacker.cmd(f'cd {os.getenv('PLC_FILE_PATH')} && ' + sys.executable + ' -u ' + ' oscillating_dos.py  &> logs/attacker.log &')

        return observation, self.reward, self.i >= self.episode_length, self.i >= self.episode_length, self.info

    def seed(self, seed=None):
        return [seed]
    
    def close(self):
        pass

    def calculate_immediate_reward(self, metrics):
        """Calculate immediate reward on a 0-10 scale"""
        scores = []
        
        # Score each metric individually (0-10)
        
        # Inter-arrival time (higher is better in normal operation)
        iat_score = self.scale_metric(
            metrics['avg_inter_arrival_time'],
            bad_value=self.attack_indicators['avg_inter_arrival_time'],
            good_range=self.normal_ranges['avg_inter_arrival_time'],
            reverse=False  # Higher is better
        )
        scores.append(iat_score * 2.0)  # Weight: 2.0
        
        # CIP ratio (higher is better in normal operation)
        cip_score = self.scale_metric(
            metrics['cipcm_ratio'],
            bad_value=self.attack_indicators['cipcm_ratio'],
            good_range=self.normal_ranges['cipcm_ratio'],
            reverse=False
        )
        scores.append(cip_score * 2.0)  # Weight: 2.0
        
        # Packet count (lower is better during attack)
        packet_score = self.scale_metric(
            metrics['packet_count'],
            bad_value=self.attack_indicators['packet_count'],
            good_range=self.normal_ranges['packet_count'],
            reverse=True  # Lower is better
        )
        scores.append(packet_score * 2.5)  # Weight: 2.5
        
        # Request/Response ratio (closer to 1 is better)
        rr_score = self.scale_metric(
            metrics['request_response_ratio'],
            bad_value=self.attack_indicators['request_response_ratio'],
            good_range=self.normal_ranges['request_response_ratio'],
            reverse=True
        )
        scores.append(rr_score * 3.5)  # Weight: 3.5
        
        # Calculate weighted average and normalize to 0-10
        return sum(scores) / 10.0

    def scale_metric(self, value, bad_value, good_range, reverse=False):
        """Scale a metric to a 0-10 score"""
        low, high = good_range
        
        if reverse:
            if value <= low:
                return 10
            elif value >= bad_value:
                return 0
            else:
                return 10 * (bad_value - value) / (bad_value - low)
        else:
            if value >= low and value <= high:
                return 10
            elif value <= bad_value:
                return 0
            else:
                return 10 * (value - bad_value) / (low - bad_value)
            
    def calculate_metric_trend(self, metric_deque):
        """
        Calculate the trend of a metric over the window
        Returns slope normalized by mean value
        Positive slope means increasing trend
        Negative slope means decreasing trend
        """
        values = list(metric_deque)
        if len(values) < 2:
            return 0
            
        # Use linear regression to get trend
        x = np.arange(len(values))
        y = np.array(values)
        slope = np.polyfit(x, y, 1)[0]
        
        # Normalize by the mean to get relative trend
        mean_value = np.mean(values)
        if mean_value != 0:
            relative_trend = slope / mean_value
        else:
            relative_trend = slope
            
        return relative_trend

    def calculate_trend_reward(self, metrics):
        """Calculate trend-based reward"""
        trend_score = 10
        
        # Add current metrics to history
        for key, value in metrics.items():
            self.metric_history[key].append(value)
            
        if len(list(self.metric_history.values())[0]) >= 3:  # Need at least 3 points for trend
            # Score improvements in key metrics
            
            # Packet count trend (want decrease during attack, stable otherwise)
            packet_trend = self.calculate_metric_trend(self.metric_history['packet_count'])
            if metrics['packet_count'] > self.normal_ranges['packet_count'][1]:
                # During high traffic, reward decreasing trend
                trend_score += 3.0 if packet_trend < 0 else 0
            else:
                # During normal traffic, reward stability
                trend_score += 2.0 if abs(packet_trend) < 0.1 else 0
            
            # Request/Response ratio trend (want trending toward 1.0)
            rr_trend = self.calculate_metric_trend(self.metric_history['request_response_ratio'])
            current_rr = metrics['request_response_ratio']
            if current_rr > self.normal_ranges['request_response_ratio'][1]:
                # If ratio is high, reward decreasing trend
                trend_score += 4.0 if rr_trend < 0 else 0
            elif current_rr < self.normal_ranges['request_response_ratio'][0]:
                # If ratio is low, reward increasing trend
                trend_score += 4.0 if rr_trend > 0 else 0
            else:
                # If ratio is good, reward stability
                trend_score += 3.0 if abs(rr_trend) < 0.1 else 0
                
        return trend_score
    
    def add_aux_flow(self, flow_id, ip_number):
        s1 = self.env.net.get('s1')

        s1.cmd('ovs-ofctl -O OpenFlow13 packet-out actions=drop')
        
        # Remove existing flow
        s1.cmd(f'ovs-ofctl -O OpenFlow13 del-flows s1 "cookie={flow_id}/-1"')
        s1.cmd(f'ovs-ofctl -O OpenFlow13 del-meter s1 meter={flow_id}')

        # Set meter for rate limiting
        s1.cmd(f'ovs-ofctl -O OpenFlow13 add-meter s1 meter={flow_id},kbps,burst,stats,bands=type=drop,rate=100000,burst_size=100')
        s1.cmd(f'ovs-ofctl -O OpenFlow13 add-flow s1 "cookie={flow_id},priority=101,ip,nw_src=192.168.1.{ip_number}0,nw_dst=192.168.1.{flow_id}0,actions=meter:{flow_id},output:5"')

    def remove_aux_flow(self, flow_id):
        s1 = self.env.net.get('s1')
        
        # Remove existing flow
        s1.cmd(f'ovs-ofctl -O OpenFlow13 del-flows s1 "cookie={flow_id}/-1"')
        s1.cmd(f'ovs-ofctl -O OpenFlow13 del-meter s1 meter={flow_id}')
        


