# backend/event-service/resources/Railway/schemas.py

from apiflask.fields import Float, String, Dict, List, Integer
from apiflask.validators import OneOf
from api.schemas import MetadataSchema

class MetadataSchemaRailway(MetadataSchema):
    agent_id = String(allow_none=True, required=True)
    event_type = String(required=True)
    id_event = String(allow_none=True, required=True)
    agent_position = List(
        Integer(allow_none=True), allow_none=True, default=None
    )
    delay = Integer(required=True)
    id_train = String(allow_none=True, required=True)
    malfunction_stop_position = List(Integer(allow_none=True), allow_none=True)
    num_rame = String(allow_none=True, default=None)
    tmp_rame = String(allow_none=True, default=None)
    travel_plan = List(Dict(), allow_none=True)
    longitude = Float(allow_none=True, default=None)
    latitude = Float(allow_none=True, default=None)
    simulation_name = String(allow_none=True, default=None)
    # Sent by the scripted Railway simulator (usecases_examples/Railway/); optional, so
    # publishers of the fields above stay valid. scenario_id, decision_index and run_mode are
    # the key of the recommendations RailwayManager returns; session_id is the Experiment's id.
    scenario_id = String(required=False, allow_none=True)
    timestep = Integer(required=False, allow_none=True)
    decision_index = Integer(required=False, allow_none=True)
    session_id = String(required=False, allow_none=True)
    run_mode = String(
        required=False, allow_none=True, validate=OneOf(["recommendation", "colearning"])
    )
