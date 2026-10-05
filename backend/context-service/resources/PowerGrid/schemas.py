from api.schemas import MetadataSchema
from apiflask.fields import Dict, String


class MetadataSchemaPowerGrid(MetadataSchema):
    topology = String(allow_none=False)
    observation = Dict(allow_none=False)
    # Serialized environment state, so agents can rebuild it by replay. Optional.
    environment_state = Dict(allow_none=True, required=False)
