from apiflask import Schema
from apiflask.fields import Dict, Integer, List, Nested, String
from apiflask.validators import Length


class RecommendationAsk(Schema):
    context = Dict()
    event = Dict()
    # Optional operator cognitive/stress snapshot, sent alongside event/context
    # only when the operator has consented. Declared so it survives schema
    # validation and is forwarded verbatim to the RL agent.
    cognitive_snapshot = Dict()
    # Ids of the agents to ask (see AgentOut); all of them when absent or empty.
    agents = List(String())


class RecommendationOut(Schema):
    title = String()
    description = String()
    use_case = String()
    description = String()
    agent_type = String()
    actions = List(Dict())
    kpis = Dict(allow_none=True)
    # Which agent made the recommendation, when the use case has several
    agent_id = String()
    agent_name = String()
    # Unique within a request: two agents can propose the same title
    recommendation_id = String()


class AgentOut(Schema):
    id = String()
    name = String()


class JobAgentOut(Schema):
    id = String()
    name = String(allow_none=True)
    # pending, done or failed
    status = String()


class RecommendationJobOut(Schema):
    id = String()
    use_case = String()
    # running while an agent is pending, then done
    status = String()
    agents = List(Nested(JobAgentOut))
    # Those of the agents that have answered
    recommendations = List(Nested(RecommendationOut))


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
