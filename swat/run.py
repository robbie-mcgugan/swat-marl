"""
swat-s1 run.py
"""

from mininet.net import Mininet
from mininet.cli import CLI
from minicps.mcps import MiniCPS
from mininet.node import RemoteController

from ray.tune.registry import register_env
import gymnasium as gym
import os
import ray
from ray.rllib.algorithms.ppo import PPOConfig
from ray import tune, air

from topo import SwatTopo

import sys
from rl_envs.envs.test import CustomEnv

from rl import SwatEnv, SwatS1CPS
from marl import MultiAgentSwatEnv

import shutil
import time

def create_single_env(env_config={}):
    # return SwatEnv(1, 10)
    return MultiAgentSwatEnv()

if __name__ == "__main__":

    # topo = SwatTopo()
    # net = Mininet(topo=topo)
    # env = SwatS1CPS(name='swat_s1', net=net)

    ray.init(ignore_reinit_error=True)
    tune.register_env("swat_env-v0", create_single_env)

    # Define the configuration for the PPO algorithm
    config = (
        PPOConfig()
        .training(
            gamma=0.99,
            lr=3e-4,
            lambda_=0.95,
            kl_coeff=0.2,
            clip_param=0.2,
            vf_clip_param=10.0,
            num_sgd_iter=10,
            sgd_minibatch_size=16,
            train_batch_size=64,
        )
        .environment(
            "swat_env-v0"
        )
        .framework("torch")
        .resources(
            num_gpus=0,
            num_cpus_per_worker=1
        )
        .rollouts(
            num_rollout_workers=0,  # Force single worker
            num_envs_per_worker=1,  # Only one env per worker
            enable_connectors=False  # Disable distributed training
        )
    )

    tune.Tuner("PPO", run_config=air.RunConfig(stop={"training_iteration": 12}), param_space=config.to_dict(), ).fit()

    # Shutdown Ray
    ray.shutdown()
