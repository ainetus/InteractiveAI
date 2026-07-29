# Historic Service API

The Historic Service maintains a log of all events and operator actions. It is called automatically by the Event Service and the HMI module — external integrators generally do not need to call it directly. It is documented here for reference and for generating reports.

**Base path:** `/api/v1`

---

## Write a trace

```http
POST http://{Platform_Server}/api/v1/traces
Content-Type: application/json
```

### Payload

| Field | Type | Description |
|---|---|---|
| `trace_type` | string | Type of trace (see values below) |
| `data` | object | Data associated with the trace |

### Trace types

| `trace_type` | Triggered when |
|---|---|
| `EVENT` | An event is received by the platform |
| `ASKFORHELP` | The operator requests assistance from the AI assistant |
| `ACTION` | The operator resolves the problem independently (without AI help) |
| `AWARD` | The operator selects one of the AI recommendations |

### Example

```json
{
  "trace_type": "AWARD",
  "data": {
    "event_id": "evt_00312",
    "recommendation_id": "rec_00089",
    "operator_id": "op_42"
  }
}
```

---

## Retrieve traces (for reports)

Returns traces within a time window. Results are automatically filtered to the running use case of the connected operator.

```http
GET http://{Platform_Server}/api/v1/traces/{start_date}/&end_date={end_date}
```

| Parameter | Location | Description |
|---|---|---|
| `start_date` | Path | ISO 8601 start of the time window |
| `end_date` | Query | ISO 8601 end of the time window |

---

## Postman collection

[Historic-service.postman_collection.json](https://github.com/IRT-SystemX/InteractiveAI/blob/main/docs/postman_collections/Historic-service.postman_collection.json)
