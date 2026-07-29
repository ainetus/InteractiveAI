# Event Service API

The Event Service receives incoming messages, categorizes them, prioritizes tasks, and forwards notifications to the HMI frontend. It also maintains the system timeline.

**Base path:** `/cab_event/api/v1`

---

## Send an event

```http
POST http://{Platform_Server}/cab_event/api/v1/events
Content-Type: application/json
```

### Generic payload

| Field | Type | Required | Description |
|---|---|---|---|
| `use_case` | string | ✅ | Identifier for the application domain / use case (PowerGrid, Railway, ATM) |
| `title` | string | ✅ | Short title of the event |
| `description` | string | ✅ | Human-readable description of the event |
| `criticality` | string/int | ✅ | Severity level of the event (HIGH, MEDIUM, LOW|
| `start_date` | datetime | ✅ | When the event started (ISO 8601) |
| `end_date` | datetime | ❌ | When the event ended — omit if unknown |
| `parent_event_id` | string | ❌ | ID of the parent event, if this event is a consequence of another |
| `data` | object | ❌ | Use-case-specific payload (see below) |

### Use-case-specific data (`data` field)

The `data` field is a free-form object used to pass domain-specific information. This data can be consumed by use-case-specific HMI components.

**Example — power grid use case:**
```json
{
  "use_case": "power_grid",
  "title": "Line overload detected",
  "description": "Transmission line L42 is operating above rated capacity.",
  "criticality": "HIGH",
  "start_date": "2024-03-15T10:23:00Z",
  "data": {
    "line_id": "L42",
    "load_percentage": 112.5,
    "substation": "SUB-07"
  }
}
```

**Example — rail network use case:**
```json
{
  "use_case": "railway",
  "title": "Signal failure",
  "description": "Signal S18 is unresponsive at junction J3.",
  "criticality": "MEDIUM",
  "start_date": "2024-03-15T08:45:00Z",
  "parent_event_id": "evt_00234",
  "data": {
    "signal_id": "S18",
    "junction": "J3",
    "affected_lines": ["R2", "R5"]
  }
}
```

### Response

On success, the API returns the created event object including its generated `id`.

---

## Postman collection

[Event-service.postman_collection.json](https://github.com/IRT-SystemX/InteractiveAI/blob/main/docs/postman_collections/Event-service.postman_collection.json)
