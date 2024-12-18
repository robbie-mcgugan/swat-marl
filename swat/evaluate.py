import ray
from ray.rllib.algorithms.ppo import PPO
import numpy as np
import matplotlib.pyplot as plt

def evaluate_model():
    ray.init()
    
    checkpoint_path = "/root/ray_results/PPO_2024-12-13_02-10-06/PPO_swat_env-v0_5ef63_00000_0_2024-12-13_02-10-06/checkpoint_000000"
    
    # Load the saved model directly from checkpoint
    agent = PPO.from_checkpoint(checkpoint_path)
    
    num_episodes = 5
    all_rewards = []
    
    for episode in range(num_episodes):
        # Use the environment that's already configured in the agent
        env = agent.env_creator(agent.config.env_config)
        obs = env.reset()[0]
        done = False
        truncated = False
        episode_rewards = []
        
        while not (done or truncated):
            action = agent.compute_single_action(obs)
            obs, reward, done, truncated, info = env.step(action)
            episode_rewards.append(reward)
            
        all_rewards.append(episode_rewards)
        print(f"Episode {episode + 1} completed with total reward: {sum(episode_rewards)}")
    
    ray.shutdown()
    return all_rewards

if __name__ == "__main__":
    try:
        rewards = evaluate_model()

        plt.figure(figsize=(10, 6))
        
        for i, episode_rewards in enumerate(rewards):
            plt.plot(episode_rewards, label=f'Episode {i+1}')

        plt.title('Reward per Timestep')
        plt.xlabel('Timestep')
        plt.ylabel('Reward')
        plt.legend()
        plt.grid(True)
        plt.show()

        print("\nSummary Statistics:")
        print(f"Average Episode Length: {np.mean([len(ep) for ep in rewards]):.2f} timesteps")
        print(f"Average Total Reward per Episode: {np.mean([sum(ep) for ep in rewards]):.2f}")

    except Exception as e:
        print(f"Error: {str(e)}")