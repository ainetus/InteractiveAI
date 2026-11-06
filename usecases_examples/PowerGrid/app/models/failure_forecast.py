"""Runtime failure forecasting for PowerGrid overload events.

This is the inference-only subset of the failure forecast implemented in the
RL_agent_failure_forecast project.  It deliberately owns its history and model
loading inside the simulator so InteractiveAI does not need a forecasting API.
"""
from __future__ import annotations

import datetime as dt
import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Deque, Dict, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


HORIZON_STEPS = 12
STEP_MINUTES = 5
HISTORY_STEPS = 2016

CLASSIFIER_FEATURES = [
    "line_id_encoded",
    "sum_load_p",
    "sum_load_q",
    "sum_gen_p",
    "var_line_rho",
    "avg_line_rho",
    "max_line_rho",
    "nb_rho_ge_0.95",
    "load_gen_ratio",
    "fcast_sum_load_p",
    "fcast_sum_load_q",
    "fcast_sum_gen_p",
    "fcast_var_line_rho",
    "fcast_avg_line_rho",
    "fcast_max_line_rho",
    "fcast_nb_rho_ge_0.95",
    "aleatoric_load_p_mean",
    "aleatoric_load_q_mean",
    "aleatoric_gen_p_mean",
    "epistemic_before",
    "epistemic_after",
]


@dataclass(frozen=True)
class ObservationHistoryEntry:
    """Small immutable subset of an observation needed by the forecasters."""

    load_p: np.ndarray
    load_q: np.ndarray
    gen_p: np.ndarray

    @classmethod
    def from_observation(cls, obs: Any) -> "ObservationHistoryEntry":
        return cls(
            load_p=np.asarray(obs.load_p, dtype=float).copy(),
            load_q=np.asarray(obs.load_q, dtype=float).copy(),
            gen_p=np.asarray(obs.gen_p, dtype=float).copy(),
        )


def _cyclic(value: float, period: float) -> Tuple[float, float]:
    return (
        float(np.cos(2 * np.pi * value / period)),
        float(np.sin(2 * np.pi * value / period)),
    )


def get_features_with_history(
    history: Sequence[ObservationHistoryEntry], obs: Any
) -> np.ndarray:
    """Build current, 1-hour, 1-day and 1-week injection features."""
    sizes = (len(obs.load_p), len(obs.load_q), len(obs.gen_p))

    def values(lag_steps: int, attr: str, size: int) -> np.ndarray:
        if len(history) <= lag_steps:
            return np.full(size, np.nan, dtype=float)
        return np.asarray(getattr(history[-1 - lag_steps], attr), dtype=float)

    injection_features = np.concatenate([
        np.asarray(obs.load_p, dtype=float),
        np.asarray(obs.load_q, dtype=float),
        np.asarray(obs.gen_p, dtype=float),
        values(12, "load_p", sizes[0]),
        values(12, "load_q", sizes[1]),
        values(12, "gen_p", sizes[2]),
        values(288, "load_p", sizes[0]),
        values(288, "load_q", sizes[1]),
        values(288, "gen_p", sizes[2]),
        values(2016, "load_p", sizes[0]),
        values(2016, "load_q", sizes[1]),
        values(2016, "gen_p", sizes[2]),
    ])
    hour_cos, hour_sin = _cyclic(getattr(obs, "hour_of_day", 0), 23)
    minute_cos, minute_sin = _cyclic(getattr(obs, "minute_of_hour", 0), 59)
    dow_cos, dow_sin = _cyclic(getattr(obs, "day_of_week", 0), 6)
    temporal = np.asarray([
        getattr(obs, "day", 1),
        hour_cos,
        hour_sin,
        minute_cos,
        minute_sin,
        dow_cos,
        dow_sin,
    ])
    return np.concatenate([injection_features, temporal]).astype(float)


def _grid_stats(obs: Any) -> Dict[str, float]:
    rho = np.asarray(obs.rho, dtype=float)
    return {
        "sum_load_p": float(np.sum(obs.load_p)),
        "sum_load_q": float(np.sum(obs.load_q)),
        "sum_gen_p": float(np.sum(obs.gen_p)),
        "var_line_rho": float(np.var(rho)),
        "avg_line_rho": float(np.mean(rho)),
        "max_line_rho": float(np.max(rho)),
        "nb_rho_ge_0.95": int(np.sum(rho >= 0.95)),
    }


def _no_op(env: Any, obs: Any) -> Any:
    try:
        return env.action_space({})
    except Exception:
        return obs._obs_env._helper_action_env({})


def _forecast_observation(
    env: Any,
    obs: Any,
    load_p: np.ndarray,
    load_q: np.ndarray,
    gen_p: np.ndarray,
) -> Any:
    simulator_factory = getattr(obs, "get_simulator", None)
    if callable(simulator_factory):
        simulator = simulator_factory().predict(
            _no_op(env, obs),
            new_gen_p=gen_p,
            new_gen_v=obs.gen_v,
            new_load_p=load_p,
            new_load_q=load_q,
        )
        if not simulator.converged:
            raise RuntimeError(f"Forecast power flow did not converge: {simulator.error}")
        return simulator.current_obs

    now = obs.get_time_stamp()
    future = now + dt.timedelta(minutes=HORIZON_STEPS * STEP_MINUTES)
    obs_copy = obs.copy()
    obs_copy._forecasted_inj = [
        (now, {"injection": {
            "load_p": obs.load_p,
            "load_q": obs.load_q,
            "prod_p": obs.gen_p,
            "prod_v": obs.gen_v,
        }}),
        (future, {"injection": {
            "load_p": load_p,
            "load_q": load_q,
            "prod_p": gen_p,
            "prod_v": obs.gen_v,
        }}),
    ]
    forecast_obs, _, done, info = obs_copy.simulate(_no_op(env, obs))
    if done and info.get("exception"):
        raise RuntimeError(f"Forecast power flow failed: {info['exception']}")
    return forecast_obs


class FailureForecastService:
    """Load trained artifacts, retain simulator history, and score overloads."""

    REQUIRED_FILES = (
        "mean_forecaster.pkl",
        "aleatoric_forecaster.pkl",
        "failure_classifier.pkl",
        "failure_classifier_metadata.json",
    )

    def __init__(self, artifact_dir: str | Path):
        import joblib

        self.artifact_dir = Path(artifact_dir)
        missing = [
            name for name in self.REQUIRED_FILES
            if not (self.artifact_dir / name).is_file()
        ]
        if missing:
            raise FileNotFoundError(
                "Missing failure forecast artifacts in "
                f"{self.artifact_dir}: {', '.join(missing)}"
            )
        self.mean_model = joblib.load(self.artifact_dir / "mean_forecaster.pkl")
        self.aleatoric_model = joblib.load(
            self.artifact_dir / "aleatoric_forecaster.pkl"
        )
        self.classifier = joblib.load(
            self.artifact_dir / "failure_classifier.pkl"
        )
        self.metadata = json.loads(
            (self.artifact_dir / "failure_classifier_metadata.json").read_text(
                encoding="utf-8"
            )
        )
        self.features = list(self.metadata.get("features", CLASSIFIER_FEATURES))
        self.line_map = {
            str(name).replace("line_", ""): int(encoded)
            for name, encoded in self.metadata.get("line_map", {}).items()
        }
        self.threshold = float(self.metadata.get("decision_threshold", 0.5))
        self.history: Deque[ObservationHistoryEntry] = deque(
            maxlen=HISTORY_STEPS + 1
        )
        self.last_recorded_step: Optional[int] = None

    def record_observation(self, obs: Any) -> None:
        """Record each simulator step once, including the warm-up period."""
        step = int(getattr(obs, "current_step", -1))
        if step == self.last_recorded_step:
            return
        self.history.append(ObservationHistoryEntry.from_observation(obs))
        self.last_recorded_step = step

    def _failure_probability(self, features: pd.DataFrame) -> float:
        probabilities = np.asarray(self.classifier.predict_proba(features))
        classes = np.asarray(getattr(self.classifier, "classes_", [0, 1]))
        matches = np.where(classes == 1)[0]
        if len(matches) != 1:
            raise ValueError("Failure classifier does not expose class 1")
        return float(probabilities[0, matches[0]])

    def predict(self, env: Any, obs: Any, line_name: str) -> Dict[str, Any]:
        """Forecast failure for the line involved in the current overload."""
        self.record_observation(obs)
        normalized_line = str(line_name).replace("line_", "")
        if normalized_line not in self.line_map:
            raise ValueError(f"Unknown line for failure classifier: {line_name!r}")

        x_t12 = get_features_with_history(list(self.history), obs)
        mean_prediction = np.asarray(
            self.mean_model.predict([x_t12])[0], dtype=float
        )
        variance_prediction = np.asarray(
            self.aleatoric_model.predict([x_t12])[0], dtype=float
        )
        n_load = int(env.n_load)
        n_gen = int(env.n_gen)
        expected_outputs = 2 * n_load + n_gen
        if mean_prediction.size != expected_outputs:
            raise ValueError(
                "Failure forecast artifact is incompatible with this grid: "
                f"expected {expected_outputs} outputs, got {mean_prediction.size}"
            )

        load_p = mean_prediction[:n_load]
        load_q = mean_prediction[n_load:2 * n_load]
        gen_p = np.clip(
            mean_prediction[2 * n_load:],
            np.asarray(env.gen_pmin, dtype=float),
            np.asarray(env.gen_pmax, dtype=float),
        )
        sigma = np.sqrt(
            np.expm1(np.clip(variance_prediction, 0.0, None)) + 1e-12
        )
        forecast_obs = _forecast_observation(
            env, obs, load_p, load_q, gen_p
        )
        current = _grid_stats(obs)
        forecast = _grid_stats(forecast_obs)
        sum_gen = current["sum_gen_p"]
        row = {
            "line_id_encoded": self.line_map[normalized_line],
            **current,
            "load_gen_ratio": current["sum_load_p"] / (sum_gen + 1e-6),
            **{f"fcast_{key}": value for key, value in forecast.items()},
            "aleatoric_load_p_mean": float(np.mean(sigma[:n_load])),
            "aleatoric_load_q_mean": float(np.mean(sigma[n_load:2 * n_load])),
            "aleatoric_gen_p_mean": float(np.mean(sigma[2 * n_load:])),
            # The deployed classifier was trained to accept missing optional ENN
            # values, so the simulator does not need to load a second model.
            "epistemic_before": float("nan"),
            "epistemic_after": float("nan"),
        }
        classifier_input = pd.DataFrame([
            {feature: row.get(feature, np.nan) for feature in self.features}
        ])
        probability = self._failure_probability(classifier_input)
        return {
            "failure_prediction": int(probability >= self.threshold),
            "failure_probability": round(probability, 3),
            "failure_probability_pct": round(probability * 100.0, 1),
            "forecast_horizon_steps": int(HORIZON_STEPS),
            "forecast_horizon_minutes": int(HORIZON_STEPS * STEP_MINUTES),
            "line": normalized_line,
        }


def build_failure_forecast_event(
    context_date: dt.datetime,
    forecast: Dict[str, Any],
    parent_event_id: str,
    line_name: str,
    img_b64: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a schema-compatible event linked to an overload event."""
    probability_pct = float(forecast["failure_probability_pct"])
    will_fail = bool(forecast["failure_prediction"])
    criticality = "HIGH" # as there's already an overload in the line
    if will_fail:
        description = (
            "The agent is likely unable to provide a solution "
            f"for overload on line {line_name} within one hour."
        )
    else:
        description = (
            "The agent is likely able to provide a solution for overload "
            f"on line {line_name} within one hour."
        )

    event_data = {
        "event_type": "anticipation",
        # InteractiveAI currently de-duplicates PowerGrid events by data.line.
        # Keep the forecast distinct from its overload parent.
        "line": f"failure_forecast:{line_name}",
        "kpis": dict(forecast),
    }
    if img_b64 is not None:
        event_data["event_context"] = img_b64

    return {
        "criticality": criticality,
        "title": f"Failure prediction {probability_pct:.1f}%",
        "description": description,
        "start_date": f"{context_date}",
        "end_date": f"{context_date + dt.timedelta(minutes=5)}",
        "parent_event_id": str(parent_event_id),
        "data": event_data,
        "use_case": "PowerGrid",
        "is_active": False,
    }
