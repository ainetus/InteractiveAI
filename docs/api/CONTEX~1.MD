# Context Service API

The Context Service collects and analyzes data related to the current operating environment: external conditions, controlled-system state, operator cognitive load, and mission parameters. The HMI module polls it continuously to display real-time context to the operator.

**Base path:** `/cab_context/api/v1`

---

## Send a context update

```http
POST http://{Platform_Server}/cab_context/api/v1/contexts
Content-Type: application/json
```

### Generic payload

| Field | Type | Required | Description |
|---|---|---|---|
| `use_case` | string | ✅ | Identifier for the application domain / use case |
| `date` | datetime | ✅ | Timestamp of the context snapshot (ISO 8601) |
| `data` | object | ❌ | Use-case-specific context information (see below) |

### Use-case-specific data (`data` field)

As with events, the `data` field carries domain-specific context that the HMI uses to render its context view.

**Example — power grid use case:**
```json
{
  "use_case": "power_grid",
  "date": "2024-03-15T10:23:00Z",
  "data": {
    "grid_load_percent": 87.3,
    "weather": "storm",
    "operator_shift": "night",
    "active_incidents": 2
  }
}
```

**Example — rail network use case:**
```json
{
  "use_case": "rail",
  "date": "2024-03-15T08:45:00Z",
  "data": {
    "trains_in_service": 42,
    "delayed_trains": 3,
    "weather": "fog",
    "operator_cognitive_load": "high"
  }
}
```

---

## Retrieve current context

Called by the HMI module to get the context at a given point in time. The platform automatically filters results to the running use case of the connected operator.

```http
GET http://{Platform_Server}/cab_context/api/v1/contexts/{date}
```

| Parameter | Location | Description |
|---|---|---|
| `date` | Path | ISO 8601 timestamp — returns the context closest to this date |

---

## Postman collection

[Context-service.postman_collection.json](https://github.com/IRT-SystemX/InteractiveAI/blob/main/docs/postman_collections/Context-service.postman_collection.json)
