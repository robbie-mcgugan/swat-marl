import gymnasium as gym
from gymnasium.utils import seeding

class MininetEnv(gym.Env):
    LF_MIN = 1
    RT_MAX = 10

    MOVE_LF = 0
    MOVE_RT = 1

    MAX_STEPS = 10

    REWARD_AWAY = -2
    REWARD_STEP = -1
    REWARD_GOAL = MAX_STEPS

    metadata = {'render.modes': ['human']}

    def __init__(self):
        self.action_space = gym.spaces.Discrete(2)
        self.observation_space = gym.spaces.Discrete(self.RT_MAX + 1)

        self.goal = int((self.LF_MIN + self.RT_MAX - 1) / 2)
        self.init_positions = list(range(self.LF_MIN, self.RT_MAX))
        self.init_positions.remove(self.goal)

        self.seed()
        self.reset()

    def reset(self, *, seed=None, options=None):
        self.seed(seed)
        self.position = self.np_random.choice(self.init_positions)
        self.count = 0

        self.state = self.position
        self.reward = 0
        self.done = False
        self.info = {}

        return self.state, self.info
    
    def step(self, action):
        truncated = False
        if self.done:
            print('Episode is done')
        elif self.count == self.MAX_STEPS:
            self.done = True
            truncated = True
        else:
            assert self.action_space.contains(action)
            self.count += 1

            if action == self.MOVE_LF:
                if self.position == self.LF_MIN:
                    self.reward = self.REWARD_AWAY
                else:
                    self.position -= 1

                if self.position == self.goal:
                    self.reward = self.REWARD_GOAL
                    self.done = True
                elif self.position < self.goal:
                    self.reward = self.REWARD_AWAY
                else:
                    self.reward = self.REWARD_STEP

            elif action == self.MOVE_RT:
                if self.position == self.RT_MAX:
                    self.reward = self.REWARD_AWAY
                else:
                    self.position += 1

                if self.position == self.goal:
                    self.reward = self.REWARD_GOAL
                    self.done = True
                elif self.position > self.goal:
                    self.reward = self.REWARD_AWAY
                else:
                    self.reward = self.REWARD_STEP

            self.state = self.position
            self.info["dist"] = self.goal - self.position

        try:
            assert self.observation_space.contains(self.state)
        except AssertionError:
            print('Invalid state:', self.state)
        
        return (self.state, self.reward, self.done, truncated, self.info)
    
    def render(self, mode='human'):
        s = "position: {:2d}  reward: {:2d}  info: {}"
        print(s.format(self.state, self.reward, self.info))

    def seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]
    
    def close(self):
        pass