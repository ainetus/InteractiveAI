# backend/context-service/resources/Railway/schemas.py

from api.schemas import MetadataSchema
from apiflask.fields import Dict, String, List, Integer

class MetadataSchemaRailway(MetadataSchema):
    trains = List(Dict(), required=False)
    list_of_target = Dict(required=False)
    direction_agents = List(Integer(), required=False)
    position_agents = Dict(required=False)
    # Sent by the scripted Railway simulator (usecases_examples/Railway/): the Experiment, the
    # running scenario, the static track network, the train history for the ZWL diagram and the
    # applied decisions. Optional, so contexts with the fields above stay valid.
    session = Dict(required=False, allow_none=True)
    scenario = Dict(required=False, allow_none=True)
    infra = Dict(required=False, allow_none=True)
    history = List(Dict(), required=False, allow_none=True)
    decisions = List(Dict(), required=False, allow_none=True)
