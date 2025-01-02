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
from ray.rllib.env.multi_agent_env import MultiAgentEnv

from collections import deque
from rl import SwatS1CPS

from dotenv import load_dotenv
import os

# Load variables from .env file
load_dotenv() 

class SingleAgentSwatEnv(gym.Env):

    def __init__(self, agent_id, episode_length, env, epsilon_start=1.0, epsilon_decay=0.9, epsilon_min=0.01):

        # self.env = net
        self.agent_id = agent_id
        self.env = env

        self.observation_space = spaces.Tuple((
            # Global metrics tuple
            spaces.Tuple((
                spaces.Box(low=0, high=np.inf, shape=(), dtype=float),  # avg_inter_arrival_time
                spaces.Box(low=0, high=1.0, shape=(), dtype=float),     # cipcm_ratio
                spaces.Box(low=0, high=np.inf, shape=(), dtype=int),    # packet_count
                spaces.Box(low=0, high=1.0, shape=(), dtype=float),     # request_ratio
                spaces.Box(low=0, high=np.inf, shape=(), dtype=float),  # request_response_ratio
                spaces.Box(low=0, high=1.0, shape=(), dtype=float),     # response_ratio
            )),
            # Local metrics tuple
            spaces.Tuple((
                spaces.Box(low=0, high=np.inf, shape=(), dtype=float),  # avg_inter_arrival_time
                spaces.Box(low=0, high=1.0, shape=(), dtype=float),     # cipcm_ratio
                spaces.Box(low=0, high=np.inf, shape=(), dtype=int),    # packet_count
                spaces.Box(low=0, high=1.0, shape=(), dtype=float),     # request_ratio
                spaces.Box(low=0, high=np.inf, shape=(), dtype=float),  # request_response_ratio
                spaces.Box(low=0, high=1.0, shape=(), dtype=float),     # response_ratio
            ))
        ))

        self.action_space = spaces.Tuple((
            spaces.Box(low=0, high=2, shape=(1,), dtype=int),  # Add or remove
            spaces.Box(low=6, high=8, shape=(1,), dtype=int),  # IP number: -1-4
        ))

        self.episode_length = episode_length
        self.count = 0
        self.flow_rate_limits = [1000, 1000, 1000, 1000]
        self.epsilon = epsilon_start
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        window_size = 4

        self.global_normal_ranges = {
            'avg_inter_arrival_time': (0.022, 0.023),
            'cipcm_ratio': (0.165, 0.168),
            'packet_count': (1250, 1300),
            'request_ratio': (0.0825, 0.084),
            'request_response_ratio': (0.95, 1.05),
            'response_ratio': (0.0825, 0.084)
        }
        
        # Local ranges are wider to accommodate individual link variation
        self.local_normal_ranges = {
            'avg_inter_arrival_time': (0.045, 0.090),
            'cipcm_ratio': (0.165, 0.168),
            'packet_count': (300, 650),
            'request_ratio': (0.0825, 0.084),
            'request_response_ratio': (0.95, 1.05),
            'response_ratio': (0.0825, 0.084)
        }
        
        self.attack_indicators = {
            'avg_inter_arrival_time': 0.004,
            'cipcm_ratio': 0.077,
            'packet_count': 8000,
            'request_ratio': 0.076,
            'request_response_ratio': 12.0,
            'response_ratio': 0.006
        }
        
        self.metric_weights = {
            'avg_inter_arrival_time': 1.5,
            'cipcm_ratio': 1.5,
            'packet_count': 2.0,
            'request_ratio': 1.5,
            'request_response_ratio': 2.0,
            'response_ratio': 1.5
        }
        
        self.metric_history = {
            'avg_inter_arrival_time': deque(maxlen=window_size),
            'cipcm_ratio': deque(maxlen=window_size),
            'packet_count': deque(maxlen=window_size),
            'request_ratio': deque(maxlen=window_size),
            'request_response_ratio': deque(maxlen=window_size),
            'response_ratio': deque(maxlen=window_size)
        }
        
        self.global_context_history = {
            'system_load': deque(maxlen=window_size),
            'attack_severity': deque(maxlen=window_size)
        }




    def reset(self, *, seed=None, options=None):
        self.reward = 0
        self.done = False
        self.truncated = False
        self.info = {}
        self.count = 0

        observation = ((0, 0, 0, 0, 0, 0), (0, 0, 0, 0, 0, 0))

        return observation

    def step(self, action):
        self.count += 1

        decision, ip_number = action

        if random.random() < self.epsilon:
            decision = random.randint(1, 2)
            ip_number = random.randint(6, 8)


        if decision == 0 or self.agent_id != 1:
            pass
        elif decision == 1:
            self.remove_aux_flow(self.agent_id)
        else:
            self.add_aux_flow(self.agent_id, ip_number)

        time.sleep(30)

        if self.count >= self.episode_length:
            self.truncated = True
            self.done = True

        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

        print("Agent ID: ", self.agent_id)

        response = requests.get(f'http://localhost:5000/metrics/{self.agent_id}').json()

        observation = ((
            response['local']['avg_inter_arrival_time'],
            response['local']['cipcm_ratio'],
            response['local']['packet_count'],
            response['local']['request_ratio'],
            response['local']['request_response_ratio'],
            response['local']['response_ratio']
        ), (
            response['global']['avg_inter_arrival_time'],
            response['global']['cipcm_ratio'],
            response['global']['packet_count'],
            response['global']['request_ratio'],
            response['global']['request_response_ratio'],
            response['global']['response_ratio']
        ))
        
        # host1 = self.env.net.get(f'plc1')
        # host2 = self.env.net.get(f'plc2')
        # latency = self.env.net.ping([host1, host2], timeout='0.1')

        # Calculate rewards
        immediate_reward = self.calculate_immediate_reward(
            local_metrics=response['local'],
            global_metrics=response['global']
        )

        trend_reward = self.calculate_trend_reward(
            local_metrics=response['local'],
            global_metrics=response['global']
        )

        self.reward = (0.6 * immediate_reward + 0.4 * trend_reward)

        print(f"Step {self.count} with action {action} and reward {self.reward}")
        print(f"New state: {response}")

        return observation, self.reward, self.count >= self.episode_length, self.count >= self.episode_length, self.info

    def seed(self, seed=None):
        return [seed]
    
    def close(self):
        pass

    def calculate_immediate_reward(self, local_metrics, global_metrics):
        local_scores = []
        global_scores = []
        
        for metric, value in local_metrics.items():
            if metric in self.local_normal_ranges:
                score = self.scale_metric(
                    value,
                    self.attack_indicators[metric],
                    self.local_normal_ranges[metric],
                    reverse=(metric in ['packet_count', 'request_response_ratio'])
                )
                local_scores.append(score * self.metric_weights[metric])
        
        for metric, value in global_metrics.items():
            if metric in self.global_normal_ranges:
                score = self.scale_metric(
                    value,
                    self.attack_indicators[metric],
                    self.global_normal_ranges[metric],
                    reverse=(metric in ['packet_count', 'request_response_ratio'])
                )
                global_scores.append(score * self.metric_weights[metric])
        
        local_reward = sum(local_scores) / sum(self.metric_weights.values())
        global_reward = sum(global_scores) / sum(self.metric_weights.values())

        global_weight = 0.3
        
        return (1 - global_weight) * local_reward + global_weight * global_reward

    def calculate_trend_reward(self, local_metrics, global_metrics):
        self.update_history(local_metrics)
        
        if len(list(self.metric_history.values())[0]) < 3:
            return 10
            
        trend_scores = []
        
        for metric, history in self.metric_history.items():
            trend = self.calculate_metric_trend(history)
            score = self.evaluate_trend_score(
                metric, 
                trend, 
                local_metrics[metric],
                global_metrics[metric]
            )
            trend_scores.append(score * self.metric_weights[metric])
            
        return sum(trend_scores) / sum(self.metric_weights.values())

    def evaluate_trend_score(self, metric, trend, local_value, global_value):
        ranges = self.local_normal_ranges
        
        if metric == 'packet_count':
            if local_value > ranges[metric][1]:
                return 10 if trend < 0 else 0
            return 10 if abs(trend) < 0.1 else 0
            
        elif metric == 'request_response_ratio':
            if local_value > ranges[metric][1]:
                return 10 if trend < 0 else 0
            if local_value < ranges[metric][0]:
                return 10 if trend > 0 else 0
            return 10 if abs(trend) < 0.1 else 0
            
        else:
            if local_value < self.attack_indicators[metric]:
                return 10 if trend > 0 else 0
            return 10 if abs(trend) < 0.1 else 0

    def scale_metric(self, value, bad_value, good_range, reverse=False):
        low, high = good_range
        if reverse:
            if value <= low: return 10
            if value >= bad_value: return 0
            return 10 * (bad_value - value) / (bad_value - low)
        else:
            if low <= value <= high: return 10
            if value <= bad_value: return 0
            return 10 * (value - bad_value) / (low - bad_value)

    def calculate_metric_trend(self, metric_deque):
        values = list(metric_deque)
        if len(values) < 2: return 0
        x = np.arange(len(values))
        y = np.array(values)
        slope = np.polyfit(x, y, 1)[0]
        mean_value = np.mean(values)
        return slope / mean_value if mean_value != 0 else slope

    def update_history(self, local_metrics):
        for key, value in local_metrics.items():
            self.metric_history[key].append(value)
    
    def add_aux_flow(self, flow_id, ip_number):
        s1 = self.env.net.get('s1')
        
        # Remove existing flow
        s1.cmd(f'ovs-ofctl -O OpenFlow13 del-flows s1 "cookie={flow_id}/-1"')
        s1.cmd(f'ovs-ofctl -O OpenFlow13 del-meter s1 meter={flow_id}')

        # Set meter for rate limiting
        s1.cmd(f'ovs-ofctl -O OpenFlow13 add-meter s1 meter={flow_id},kbps,burst,stats,bands=type=drop,rate=100000,burst_size=100')
        s1.cmd(f'ovs-ofctl -O OpenFlow13 add-flow s1 "cookie={flow_id},priority=101,ip,nw_src=192.168.1.{ip_number}0,nw_dst=192.168.1.{flow_id}0,actions=output:5"')

    def remove_aux_flow(self, flow_id):
        s1 = self.env.net.get('s1')
        
        # Remove existing flow
        s1.cmd(f'ovs-ofctl -O OpenFlow13 del-flows s1 "cookie={flow_id}/-1"')
        s1.cmd(f'ovs-ofctl -O OpenFlow13 del-meter s1 meter={flow_id}')
        




class MultiAgentSwatEnv(MultiAgentEnv):

    def __init__(self, evaluate=False):
        super().__init__()


        print("STARTING MULTI AGENT SWAT ENVIRONMENT")
        topo = SwatTopo()
        net = Mininet(topo=topo)
        self.env = SwatS1CPS(name='swat_s1', net=net)

        self.agents = [SingleAgentSwatEnv(i, 20, self.env) for i in range(1,4)]

        self._agent_ids = set(range(3))
        self.terminateds = set()
        self.truncateds = set()
        self.resetted = False
        self.info_dict = {}
        self.operation_count = 0
        self.attacked = False
        self.s = 0

        self.observation_space = spaces.Tuple((
            # Global metrics tuple
            spaces.Tuple((
                spaces.Box(low=0, high=np.inf, shape=(), dtype=float),  # avg_inter_arrival_time
                spaces.Box(low=0, high=1.0, shape=(), dtype=float),     # cipcm_ratio
                spaces.Box(low=0, high=np.inf, shape=(), dtype=int),    # packet_count
                spaces.Box(low=0, high=1.0, shape=(), dtype=float),     # request_ratio
                spaces.Box(low=0, high=np.inf, shape=(), dtype=float),  # request_response_ratio
                spaces.Box(low=0, high=1.0, shape=(), dtype=float),     # response_ratio
            )),
            # Local metrics tuple
            spaces.Tuple((
                spaces.Box(low=0, high=np.inf, shape=(), dtype=float),  # avg_inter_arrival_time
                spaces.Box(low=0, high=1.0, shape=(), dtype=float),     # cipcm_ratio
                spaces.Box(low=0, high=np.inf, shape=(), dtype=int),    # packet_count
                spaces.Box(low=0, high=1.0, shape=(), dtype=float),     # request_ratio
                spaces.Box(low=0, high=np.inf, shape=(), dtype=float),  # request_response_ratio
                spaces.Box(low=0, high=1.0, shape=(), dtype=float),     # response_ratio
            ))
        ))

        self.action_space = spaces.Tuple((
            spaces.Box(low=1, high=2, shape=(1,), dtype=int),  # Flow ID: 1-4
            spaces.Box(low=6, high=8, shape=(1,), dtype=int),  # IP number: -1-4
        ))

        print("Waiting for the CAPTURE to start")
        time.sleep(20)

    def reset(self, *, seed=None, options=None):
        self.terminateds = set()
        self.truncateds = set()
        self.resetted = False
        self.info_dict = {}
        self.operation_count = 0
        self.attacked = False
        self.s = 0

        plc1 = self.env.net.get('plc1')
        plc2 = self.env.net.get('plc2')
        plc3 = self.env.net.get('plc3')
        s1 = self.env.net.get('s1')
        
        attackers = ['hmi1', 'hmi2', 'hmi3', 'hmi4', 'hmi5']
        random_attacker = random.choice(attackers)
        attacker = self.env.net.get(random_attacker)

        self.attacker = attacker

        attacker.cmd('pkill -9 -f dos.py')
        attacker.cmd('pkill -9 -f oscillating_dos.py')

        plc2.cmd('pkill -9 -f plc2.py')
        plc2.cmd(f'cd {os.getenv("PLC_FILE_PATH")} && ' + sys.executable + ' -u ' +' plc2.py &> logs/plc2.log &')

        plc3.cmd('pkill -9 -f plc3.py')
        plc3.cmd(f'cd {os.getenv("PLC_FILE_PATH")} && ' + sys.executable + ' -u ' + ' plc3.py  &> logs/plc3.log &')

        plc1.cmd('pkill -9 -f plc1.py')
        plc1.cmd(f'cd {os.getenv("PLC_FILE_PATH")} && ' + sys.executable + ' -u ' + ' plc1.py &> logs/plc1.log &')

        s1.cmd('pkill -9 -f physical_process.py')
        s1.cmd(f'cd {os.getenv("PLC_FILE_PATH")} && ' + sys.executable + ' -u ' + ' physical_process.py  &> logs/process.log &')

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

        # s1.cmd(f'ovs-ofctl -O OpenFlow13 add-meter s1 meter=1,kbps,burst,stats,bands=type=drop,rate=10000,burst_size=100')

        # s1.cmd(f'ovs-ofctl -O OpenFlow13 add-flow s1 "cookie=1,priority=101,ip,nw_src=192.168.1.70,nw_dst=192.168.1.10,actions=meter:1,output:5"')

        # response = requests.get(f'http://localhost:5000/metrics').json()
        
        # host1 = self.env.net.get(f'plc1')
        # host2 = self.env.net.get(f'plc2')
        # # latency = self.env.net.ping([host1, host2], timeout='0.1')

        # observation = (
        #     response['avg_inter_arrival_time'],
        #     response['cipcm_ratio'],
        #     response['packet_count'],
        #     response['request_ratio'],
        #     response['request_response_ratio'],
        #     response['response_ratio']
        # )

        return {i: a.reset() for i, a in enumerate(self.agents)}, {}

    def step(self, action_dict):
        obs, rew, terminated, trunc, info = {}, {}, {}, {}, {}

        self.s += 1

        if self.s == 2:
            self.attacker.cmd(f'cd {os.getenv("PLC_FILE_PATH")} && ' + sys.executable + ' -u ' + ' dos.py  &> logs/attacker.log &')
        else:
            self.attacker.cmd(f'cd {os.getenv("PLC_FILE_PATH")} && ' + sys.executable + ' -u ' + ' oscillating_dos.py  &> logs/attacker.log &')

        for i, action in action_dict.items():
            obs[i], rew[i], terminated[i], trunc[i], info[i] = self.agents[i].step(action)
            if terminated[i]:
                self.terminateds.add(i)

            if trunc[i]:
                self.truncateds.add(i)

        terminated["__all__"] = len(self.terminateds) == len(self.agents)
        trunc["__all__"] = len(self.truncateds) == len(self.agents)

        return obs, rew, terminated, trunc, info
    
