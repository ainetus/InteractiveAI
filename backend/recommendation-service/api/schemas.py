from apiflask import Schema
from apiflask.fields import Dict, Integer, List, String
from apiflask.validators import Length


class RecommendationAsk(Schema):
    context = Dict()
    event = Dict()
    # Optional operator cognitive/stress snapshot, sent alongside event/context
    # only when the operator has consented. Declared so it survives schema
    # validation and is forwarded verbatim to the RL agent.
    cognitive_snapshot = Dict()
    # Optional per-request tuning, e.g. kpi_prediction_steps for A3S.
    options = Dict()


class RecommendationOut(Schema):
    title = String()
    description = String()
    use_case = String()
    description = String()
    agent_type = String()
    actions = List(Dict())
    kpis = Dict(allow_none=True)
    # A3S multi-step rollouts: candidate index and rollout timestep.
    branch_index = Integer(allow_none=True)
    step = Integer(allow_none=True)


class ProcedureOut(Schema):
    procedure = List(Dict())
    max_speed = Integer()
    min_speed = Integer()


class UseCaseIn(Schema):
    name = String(required=True, validate=Length(1, 255))
    manager_class = String(validate=Length(1, 255))


class UseCaseOut(Schema):
    id = Integer()
    name = String(required=True, validate=Length(1, 255))
    manager_class = String(validate=Length(1, 255))
