# backend/context-service/resources/ATM/schemas.py

from api.schemas import MetadataSchema
from apiflask.fields import Dict, String, Float, List, Integer
from apiflask import Schema, fields
from marshmallow import pre_load
class PlaneMetadataSchemaATM(MetadataSchema):
    id_plane = String()
    ApDest = Dict()
    Current_airspeed = Float()
    Latitude = Float()
    Longitude = Float()
    # True heading, degrees clockwise from north (0-360). Optional
    heading = Float(required=False)
    # True if another aircraft is inside this one's protected zone right now.
    in_los = fields.Boolean(required=False)
    wpList = List(Dict())

class ShapeMetadataSchemaATM(MetadataSchema):
    name = String(required=True)
    # SECTOR | WEATHER | VOLCANIC | OBSTACLE, see build_shapes_payload() in
    # ai4realnet_rl_batch_bridge.py.
    kind = String(required=False)
    coordinates = List(List(Float()), required=True)


class MetadataSchemaATM(MetadataSchema):
    airplanes = List(fields.Nested(PlaneMetadataSchemaATM), required=True)
    shapes = List(fields.Nested(ShapeMetadataSchemaATM), required=False)

    # Backward compatibility: optional fields for the single airplane case
    ApDest = Dict(required=False)
    Current_airspeed = Float(required=False)
    Latitude = Float(required=False)
    Longitude = Float(required=False)
    heading = Float(required=False)
    wpList = List(Dict(), required=False)

    @pre_load
    def handle_backward_compatibility(self, data, **kwargs):
        # If the new 'airplanes' field is not provided, assume the old format.
        if 'airplanes' not in data:
            airplane = {}
            for field in ['ApDest', 'Current_airspeed', 'Latitude', 'Longitude', 'heading', 'wpList']:
                if field in data:
                    airplane[field] = data[field]
            # Provide a default id_plane if not present.
            airplane.setdefault('id_plane', "X")
            data['airplanes'] = [airplane]
        return data