from flatland.envs.observations import TreeObsForRailEnv
from flatland.envs.predictions import ShortestPathPredictorForRailEnv
from flatland.envs.rail_env import RailEnv
from flatland.envs.rail_generators import sparse_rail_generator
from flatland.envs.line_generators import sparse_line_generator
from flatland.envs.observations import TreeObsForRailEnv
from flatland.envs.predictions import ShortestPathPredictorForRailEnv


# Create a Flatland environment
def create_random_env(
    width=32,
    height=32,
    obs_builder=None,
    malfunction_generator=None,
):
    """
    Create a random Flatland environment with specified width and height.
    The environment will have sparse rail generation and a tree observation builder.
    """
    return RailEnv(
        width=width,
        height=height,
        rail_generator=sparse_rail_generator(
            max_num_cities=4,
            grid_mode=False,
            max_rails_between_cities=2,
            max_rail_pairs_in_city=1,
        ),
        line_generator=sparse_line_generator(),
        number_of_agents=5,
        obs_builder_object=obs_builder,
        malfunction_generator=malfunction_generator,
    )
