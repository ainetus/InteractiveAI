# Serializes the simulator's environment state (identity + action history) so
# consumers like A3S can rebuild it exactly by replay instead of approximating it.
import base64
import gzip
import json
import logging

# Must stay in sync with GRID2OP_OBSERVATION_V2 in the A3S service
# (a3s-service/agent_as_a_service/powergrid/serialization.py).
GRID2OP_OBSERVATION_V2 = "grid2op_observation_v2"

# Framing of replay_actions, stamped in metadata.
REPLAY_COMPRESSION = "gzip+base64"


class ReplayRecorder:
    """Records actions applied since the last reset; the history must be gap-free to replay."""

    def __init__(self):
        self._actions = []
        self._broken = False

    def reset(self) -> None:
        self._actions = []
        self._broken = False

    def record(self, action) -> None:
        """Appends an action; marks the recorder broken (for the rest of the episode) on failure."""
        if self._broken:
            return
        try:
            self._actions.append({"vect": action.to_vect().tolist()})
        except Exception as e:
            logging.error(
                "Failed to record an action for replay; no environment state "
                "will be published for the rest of this episode: %s", e)
            self._actions = []
            self._broken = True

    @property
    def actions(self) -> list:
        return self._actions

    @property
    def broken(self) -> bool:
        return self._broken

    def __len__(self) -> int:
        return len(self._actions)


def build_env_identity(config: dict) -> dict:
    """Captures which environment (seed, scenario, library versions) to replay against."""
    identity = {
        "seed": int(config["env_seed"]),
        "scenario_name": str(config["scenario_name"]),
    }
    for name, package in (("grid2op_version", "grid2op"),
                          ("lightsim2grid_version", "lightsim2grid")):
        try:
            identity[name] = __import__(package).__version__
        except Exception as e:
            logging.warning("Could not read the %s version: %s", package, e)
    return identity


def encode_replay_actions(replay_actions: list) -> str:
    """Compresses the action history to gzipped, base64-encoded JSON."""
    raw = json.dumps(replay_actions, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(gzip.compress(raw, 6)).decode("ascii")


def build_environment_state(obs, env_identity: dict, recorder: ReplayRecorder,
                            max_state_mb: float) -> dict:
    """Builds the environment_state envelope, or None if there's nothing replayable or it's too large."""
    if recorder.broken or not len(recorder):
        return None

    encoded = encode_replay_actions(recorder.actions)
    size_mb = len(encoded) / (1024 * 1024)
    if size_mb > max_state_mb:
        logging.warning(
            "Replay history dropped: %.1f MB over the %.1f MB cap (%d actions).",
            size_mb, max_state_mb, len(recorder))
        return None

    return {
        "serializer": GRID2OP_OBSERVATION_V2,
        "state": {
            "observation": obs.to_json(),
            "replay_actions": encoded,
            **env_identity,
        },
        "metadata": {
            "current_step": int(obs.current_step),
            "replayed_actions": len(recorder),
            "compression": REPLAY_COMPRESSION,
        },
    }
