from fastapi import APIRouter
from app.env import interactive_env, EnvDoneException

router = APIRouter()


@router.get("/transitions")
def get_transitions():
    return interactive_env.baseline_env.env.rail.grid.tolist()


@router.get("/baseline")
def get_baseline():
    return interactive_env.baseline_env.steps


@router.get("/history")
def get_history():
    return interactive_env.history_env.steps


@router.get("/plans")
def get_plans():
    return [plan.steps for plan in interactive_env.plan_envs]


@router.post("/step")
def step_env(plan_index: int):
    return interactive_env.step(plan_index)


@router.post("/reset")
def reset_env():
    interactive_env.reset()


@router.post("/all_steps")
def step_all():
    plan_index = 0
    try:
        while True:
            # Step through the environment until a plan is selected
            plan_index = interactive_env.step(plan_index)
            print(f"Selected plan index: {plan_index}")
    except EnvDoneException:
        return
