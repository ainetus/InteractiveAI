import random
from flatland.envs.rail_env_action import RailEnvActions


class RandomPolicy:
    def act(self, _obs):
        return RailEnvActions.from_value(random.randint(0, 4))

    def act_many(self, obs):
        return {a: self.act(o) for a, o in obs.items()}
