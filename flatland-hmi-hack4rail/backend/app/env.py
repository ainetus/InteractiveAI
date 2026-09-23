from dataclasses import dataclass, field
import tempfile
import random

from flatland.envs.rail_env_action import RailEnvActions
from flatland.envs.persistence import RailEnvPersister

from flatland.core.policy import Policy
from flatland.envs.rail_env import RailEnv
from flatland.envs.predictions import ShortestPathPredictorForRailEnv
from flatland.envs.observations import TreeObsForRailEnv
from flatland.envs import malfunction_generators as mal_gen

from .scenario.hack4rail import Hack4RailEnvGenerator


class EnvDoneException(Exception):
    """Exception raised when the environment is done."""


@dataclass
class EnvOption:
    policy: Policy
    env: RailEnv
    steps: list = field(default_factory=list)

    def update_env(self, env: RailEnv):
        """Update the environment for the policy."""
        self.env = env
        if hasattr(self.policy, "env"):
            self.policy.env = env

    def reset(self):
        """Reset the environment and policy."""
        self.env.reset()
        self.steps = []

    def step(self, explicit_actions=None) -> None:
        """Exeecute the next step in the environment based on the policy."""
        if explicit_actions is None:
            explicit_actions = {}
        if self.env.dones.get("__all__", False):
            raise EnvDoneException("Environment done, call reset() to start a new episode")
        actions = self.policy.act_many(self.env.obs_dict)
        actions.update(
            {
                a: RailEnvActions.from_value(action)
                for a, action in explicit_actions.items()
            }
        )
        self.env.step(actions)
        self.steps.append(self._step_to_dict())

    def _step_to_dict(self):
        return {
            str(agent.handle): {
                "position": (
                    None
                    if agent.position is None
                    else tuple(int(c) for c in agent.position)
                ),
                "direction": agent.direction,
                "moving": agent.moving,
                "speed_counter": agent.speed_counter,
                "target": (
                    None
                    if agent.target is None
                    else tuple(int(c) for c in agent.target)
                ),
                "malfunction": agent.malfunction_handler.malfunction_down_counter,
            }
            for agent in self.env.agents
        }

    def simulate(self):
        """Run all steps until the environment is done."""
        if self.env.dones.get("__all__", False):
            raise EnvDoneException("Environment done, call reset() to start a new episode")
        malfunction_generator = self.env.malfunction_generator
        self.env.malfunction_generator = mal_gen.NoMalfunctionGen()
        while not self.env.dones.get("__all__", False):
            self.step()
        self.env.malfunction_generator = malfunction_generator

    def switch_policy(self, new_policy: Policy):
        """Switch the policy for the environment."""
        tmp_file_name = tempfile.NamedTemporaryFile(suffix=".pkl").name
        RailEnvPersister.save(self.env, tmp_file_name)
        obs_builder = TreeObsForRailEnv(
            max_depth=1, predictor=ShortestPathPredictorForRailEnv()
        )
        env_copy, _ = RailEnvPersister.load_new(
            tmp_file_name,
            obs_builder_object=obs_builder,
        )
        env_copy.obs_builder.reset()
        copy = EnvOption(policy=new_policy, env=env_copy, steps=self.steps.copy())
        copy.update_env(env_copy)
        return copy


class InteractiveEnv:
    def __init__(
        self, generator: Hack4RailEnvGenerator, baseline_policy, plan_policies
    ):
        self.generator: Hack4RailEnvGenerator = generator
        self.baseline_env = EnvOption(
            baseline_policy, generator.create_hack4rail_env(enable_malfunctions=False)
        )
        self.plan_envs = [
            EnvOption(plan_policy, generator.create_hack4rail_env())
            for plan_policy in plan_policies
        ]
        self.history_env = EnvOption(baseline_policy, generator.create_hack4rail_env())
        self.reset()

    def reset(self):
        for env_option in [self.baseline_env, self.history_env] + self.plan_envs:
            env_option.update_env(self.generator.create_hack4rail_env())
            env_option.reset()

        # Generate baseline env
        self.baseline_env.reset()
        self.baseline_env.simulate()
        for plan_env in self.plan_envs:
            plan_env.simulate()

    def step(self, plan_index) -> int | None:
        """Step the environment and return the observations, rewards, done flags, info, and actions."""
        self.history_env = self.history_env.switch_policy(
            self.plan_envs[plan_index].policy
        )
        # update history env with the current step
        #TODO: Investigate why we need to step twice. Reloaded env seems to be in a wierd state.
        self.history_env.step()
        self.history_env.step()
        # update the plan envs with the current step
        for i, plan_env in enumerate(self.plan_envs):
            updated = self.history_env.switch_policy(plan_env.policy)
            # simulate the plan with the new state
            updated.simulate()
            self.plan_envs[i] = updated

        # evaluate the plans to determine the best solution
        # placholder returning a random value for the index of plan_env
        best_plan_index = random.randint(0, len(self.plan_envs) - 1)

        return best_plan_index


# Import hack4rail environment generator providing a static environment
from .scenario.hack4rail import Hack4RailEnvGenerator


# Import the RandomPolicy from the policies module
# from .policy.random_policy import RandomPolicy

# Create a random agent policy
# random_policy = RandomPolicy()

# Import the DeadLockAvoidancePolicy from the policies module
from .policy.deadlock_avoidance_policy import DeadLockAvoidancePolicy


# Initialize the interactive environment with env and policy
interactive_env = InteractiveEnv(
    generator=Hack4RailEnvGenerator(),
    baseline_policy=DeadLockAvoidancePolicy(),
    plan_policies=[
        DeadLockAvoidancePolicy(default_eps=0.2, enable_eps=True),
        DeadLockAvoidancePolicy(default_eps=0.8, enable_eps=True),
    ],
)
