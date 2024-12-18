import gymnasium as gym
from gymnasium import spaces
import numpy as np

import sys
import requests
import os


class CustomEnv(gym.Env):
    """
    Custom Environment that follows gymnasium interface.
    """
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 30}

    def __init__(self, env, render_mode=None, epsilon_start=1.0, epsilon_decay=0.9, epsilon_min=0.01):
        self.env = env
        self.agent_id = 1
        print("STARTING SWAT ENVIRONMENT " + str(self.agent_id))

        self.observation_space = spaces.Tuple((
            spaces.Box(low=-0, high=np.inf, shape=(), dtype=float), 
            spaces.Box(low=0, high=1.0, shape=(), dtype=float),  
            spaces.Box(low=0, high=np.inf, shape=(), dtype=int), 
            spaces.Box(low=0, high=1.0, shape=(), dtype=float), 
            spaces.Box(low=0, high=1.0, shape=(), dtype=float),  
            spaces.Box(low=0, high=1.0, shape=(), dtype=float),  
        ))

        self.action_space = spaces.Tuple((
            spaces.Box(low=0, high=4, shape=(1,), dtype=int),  # Flow ID: 1-4
            spaces.Box(low=-1, high=9, shape=(1,), dtype=int),  # IP number: -1-4
            spaces.Box(low=0, high=100, shape=(1,), dtype=int)  # Rate limit in kbps
        ))

        self.episode_length = 10
        self.i = 0
        self.flow_rate_limits = [1000, 1000, 1000, 1000]
        self.epsilon = epsilon_start
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        
        # Initialize state
        self.state = None
        self._episode_length = 0
        self._max_episode_steps = 100

        self.reset()


    def step(self, action):
        """
        Execute one time step within the environment
        """
        self.state = (0,0,0,0,0,0)
        
        # Example implementation:
        self._episode_length += 1
        
        # Your custom state transition logic here
        self.state = self._next_state(action)
        
        # Calculate reward
        reward = self._get_reward(action)
        
        # Check if episode is done
        terminated = self._episode_length >= self._max_episode_steps
        truncated = False  # You can define custom truncation conditions
        
        # Optional info dict
        info = {}
        
        return self.state, reward, terminated, truncated, info

    def reset(self, seed=None, options=None):
        print("Resetting the environment")

        self.reward = 0
        self.done = False
        self.truncated = False
        self.info = {}
        self.i = 0

        plc1 = self.env.net.get('plc1')
        plc2 = self.env.net.get('plc2')
        plc3 = self.env.net.get('plc3')
        s1 = self.env.net.get('s1')

        print(os.getcwd())

        print(plc2.cmd(sys.executable + ' -u ' +' plc2.py'))

        # plc2.cmd(sys.executable + ' -u ' +' plc2.py &> logs/plc2.log &')
        # plc3.cmd(sys.executable + ' -u ' + ' plc3.py  &> logs/plc3.log &')
        # plc1.cmd(sys.executable + ' -u ' + ' plc1.py  &> logs/plc1.log &')
        # s1.cmd(sys.executable + ' -u ' + ' physical_process.py  &> logs/process.log &')

        # s1.dpctl('del-flows')

        # s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 "priority=100,ip,nw_dst=192.168.1.10,actions=output:1"')
        # s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 "priority=100,ip,nw_dst=192.168.1.20,actions=output:2"')
        # s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 "priority=100,ip,nw_dst=192.168.1.30,actions=output:3"')
        # s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 "priority=100,ip,nw_dst=192.168.1.70,actions=output:4"')

        # s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 arp,in_port=1,actions=output:2,3,4')
        # s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 arp,in_port=2,actions=output:1,3,4')
        # s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 arp,in_port=3,actions=output:1,2,4')
        # s1.cmd('ovs-ofctl -O OpenFlow13 add-flow s1 arp,in_port=4,actions=output:1,2,3')

        # response = requests.get(f'http://localhost:5000/metrics').json()
        
        host1 = self.env.net.get(f'plc1')
        host2 = self.env.net.get(f'plc2')
        # latency = self.env.net.ping([host1, host2], timeout='0.1')

        # observation = (
        #     response['avg_inter_arrival_time'],
        #     response['cipcm_ratio'],
        #     response['packet_count'],
        #     response['request_ratio'],
        #     response['request_response_ratio'],
        #     response['response_ratio']
        # )

        observation = (0,0,0,0,0,0)

        print(f"Resetting the environment with state: {observation}")

        return observation, self.info

    def render(self):
        """
        Render the environment to the screen
        """
        pass

    def close(self):
        """
        Clean up resources
        """
        pass

    def _next_state(self, action):
        """
        Helper method to calculate next state
        """
        # Implement your state transition logic here
        return self.observation_space.sample()  # Placeholder

    def _get_reward(self, action):
        """
        Helper method to calculate reward
        """
        # Implement your reward logic here
        return 0.0  # Placeholder