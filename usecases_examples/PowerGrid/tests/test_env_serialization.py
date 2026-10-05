# Tests the producer side of environment_state, without the Grid2Op stack.
# Run from usecases_examples/PowerGrid: python -m pytest tests -q
import base64
import gzip
import json

from app.models.env_serialization import (
    GRID2OP_OBSERVATION_V2,
    REPLAY_COMPRESSION,
    ReplayRecorder,
    build_env_identity,
    build_environment_state,
)

CONFIG = {"env_seed": "2118338672", "scenario_name": "jan_28_1"}


class StubAction:
    """Stands in for a Grid2Op action, vectorizable or not."""

    def __init__(self, vector: list, vectorizable: bool):
        self._vector = vector
        self._vectorizable = vectorizable

    def to_vect(self):
        if not self._vectorizable:
            raise RuntimeError("cannot vectorize this action")
        return _Vector(self._vector)


class _Vector:
    """Minimal stand-in for the numpy array to_vect() returns."""

    def __init__(self, values: list):
        self._values = values

    def tolist(self) -> list:
        return list(self._values)


class StubObservation:
    """Stands in for the Grid2Op observation being published."""

    current_step = 12

    def to_json(self) -> dict:
        return {"current_step": [self.current_step]}


def _decode(encoded: str) -> list:
    """Decodes a published history back into a list of actions."""
    return json.loads(gzip.decompress(base64.b64decode(encoded)).decode("utf-8"))


def test_the_published_state_carries_the_history_and_the_identity():
    recorder = ReplayRecorder()
    for step in range(3):
        recorder.record(StubAction([float(step), 0.0], vectorizable=True))

    state = build_environment_state(
        StubObservation(), build_env_identity(CONFIG), recorder, 32
    )

    assert state["serializer"] == GRID2OP_OBSERVATION_V2
    assert state["metadata"]["compression"] == REPLAY_COMPRESSION
    assert state["metadata"]["replayed_actions"] == 3
    assert state["state"]["seed"] == 2118338672
    assert state["state"]["scenario_name"] == "jan_28_1"
    assert _decode(state["state"]["replay_actions"]) == [
        {"vect": [0.0, 0.0]},
        {"vect": [1.0, 0.0]},
        {"vect": [2.0, 0.0]},
    ]


def test_a_failed_recording_publishes_nothing_for_the_rest_of_the_episode():
    recorder = ReplayRecorder()
    recorder.record(StubAction([1.0], vectorizable=True))
    recorder.record(StubAction([2.0], vectorizable=False))
    recorder.record(StubAction([3.0], vectorizable=True))

    assert recorder.broken
    assert len(recorder) == 0
    assert (
        build_environment_state(
            StubObservation(), build_env_identity(CONFIG), recorder, 32
        )
        is None
    )

    # A new episode records again.
    recorder.reset()
    recorder.record(StubAction([4.0], vectorizable=True))

    assert not recorder.broken
    assert len(recorder) == 1


def test_an_empty_history_publishes_nothing():
    assert (
        build_environment_state(
            StubObservation(), build_env_identity(CONFIG), ReplayRecorder(), 32
        )
        is None
    )


def test_an_oversized_history_is_dropped():
    recorder = ReplayRecorder()
    for step in range(50):
        recorder.record(StubAction([float(step)], vectorizable=True))

    assert (
        build_environment_state(
            StubObservation(), build_env_identity(CONFIG), recorder, 0.0
        )
        is None
    )


def test_the_identity_reports_the_libraries_it_can_read():
    identity = build_env_identity(CONFIG)

    assert identity["seed"] == 2118338672
    assert identity["scenario_name"] == "jan_28_1"
