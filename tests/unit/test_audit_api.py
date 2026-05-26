"""Unit tests for execution audit API."""
from backend.memory.audit_store import init_audit_store, log_execution_audit


def test_audit_executions_endpoint(client, tmp_path):
    init_audit_store(tmp_path / "audit.db")
    log_execution_audit(
        execution_id="exec-api-1",
        action_type="tool_read",
        status="success",
        tool_name="get_pods",
        command_details={"namespace": "demo"},
    )
    log_execution_audit(
        execution_id="exec-api-2",
        action_type="tool_write",
        status="success",
        tool_name="restart_pod",
        command_details={"pod": "app-1"},
    )

    resp = client.get("/api/v1/audit/executions?limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 2
    assert any(e["execution_id"] == "exec-api-1" for e in body["entries"])

    filtered = client.get("/api/v1/audit/executions?execution_id=exec-api-1")
    assert filtered.status_code == 200
    assert all(e["execution_id"] == "exec-api-1" for e in filtered.json()["entries"])

    by_action = client.get("/api/v1/audit/executions?action_type=tool_write")
    assert by_action.status_code == 200
    entries = by_action.json()["entries"]
    assert entries, "expected at least one tool_write entry"
    assert all(e["action_type"] == "tool_write" for e in entries)

    by_status = client.get("/api/v1/audit/executions?status=success")
    assert by_status.status_code == 200
    assert all(e["status"] == "success" for e in by_status.json()["entries"])

    facets = client.get("/api/v1/audit/facets")
    assert facets.status_code == 200
    body = facets.json()
    assert "tool_write" in body["action_types"]
    assert "success" in body["statuses"]
