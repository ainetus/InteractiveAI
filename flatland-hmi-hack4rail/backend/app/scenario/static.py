from flatland.envs.rail_env import RailEnv


def rail_generator_from_grid_map(grid_map):
    def rail_generator(*args, **kwargs):
        return grid_map, {
            "agents_hints": {"city_positions": {}},
            "level_free_positions": [],
        }

    return rail_generator


def line_generator_from_line(line):
    def line_generator(*args, **kwargs):
        return line

    return line_generator


def timetable_generator_from_timetable(timetable):
    def timetable_generator(*args, **kwargs):
        return timetable

    return timetable_generator


def create_static_env(
    width=32,
    height=32,
    map=None,
    line=None,
    timetable=None,
    obs_builder=None,
    malfunction_generator=None,
):

    assert map is not None, "Grid must be provided"
    assert line is not None, "Line must be provided"
    assert timetable is not None, "Timetable must be provided"

    env = RailEnv(
        width=width,
        height=height,
        rail_generator=rail_generator_from_grid_map(map),
        line_generator=line_generator_from_line(line),
        timetable_generator=timetable_generator_from_timetable(timetable),
        obs_builder_object=obs_builder,
        malfunction_generator=malfunction_generator,
    )

    return env
