"""Phase 8 — orchestrator route workflow step."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.workflow import WorkflowStatus, WorkflowEventStatus
from app.workflows.engine import run_workflow
from app.workflows.step_handlers import execute_step_action
from app.workflows.definitions import get_workflow_definition
from app.clients.service_client import ServiceCallError


@pytest.mark.asyncio
async def test_plan_route_calls_route_service():
    step = get_workflow_definition("FLOOD").steps[6]
    assert step.action == "plan_route"
    context = {
        "latitude": 40.71,
        "longitude": -74.0,
        "incident_id": "inc-1",
        "workflow_id": "wf-1",
        "hospitals": [{"id": "h1", "latitude": 40.75, "longitude": -73.98}],
    }
    with patch("app.workflows.step_handlers.call_service", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = {
            "route": {"id": "r1", "status": "CALCULATED", "distance_km": 3.1},
            "message": "ok",
        }
        result = await execute_step_action(step, context)
    assert result["id"] == "r1"
    assert context["route_id"] == "r1"
    mock_call.assert_awaited_once()
    args, kwargs = mock_call.call_args
    assert args[0] == "route-service"
    assert kwargs["json_body"]["origin_lat"] == 40.71


@pytest.mark.asyncio
async def test_plan_route_failure_partial_workflow():
    async def fake_execute(step, context):
        if step.action == "plan_route":
            raise ServiceCallError("route-service unavailable")
        if step.action == "search_hospitals":
            context["hospitals"] = [{"id": "h1", "latitude": 40.75, "longitude": -73.98}]
            return {"count": 1}
        if step.action == "reserve_hospital_beds":
            return {"hospital_id": "h1"}
        if step.action == "search_resources":
            context["resources"] = [{"id": "res1", "latitude": 40.76, "longitude": -73.97}]
            return {"count": 1}
        if step.action == "allocate_resource":
            return {"resource_id": "res1"}
        return {}

    with patch("app.workflows.engine.create_workflow", new_callable=AsyncMock) as mock_create:
        with patch("app.workflows.engine.update_workflow", new_callable=AsyncMock):
            with patch("app.workflows.engine.create_workflow_event", new_callable=AsyncMock):
                with patch("app.workflows.engine.get_workflow", new_callable=AsyncMock) as mock_get:
                    with patch("app.workflows.engine.list_workflow_events", new_callable=AsyncMock, return_value=[]):
                        with patch("app.workflows.engine.execute_step_action", side_effect=fake_execute):
                            mock_create.return_value = {"id": "wf8", "created_at": datetime.utcnow()}
                            mock_get.return_value = {"id": "wf8", "status": WorkflowStatus.PARTIAL.value}
                            result = await run_workflow(
                                MagicMock(),
                                incident_id="inc-8",
                                disaster_type="FLOOD",
                                classification={"disaster_type": "FLOOD"},
                                latitude=40.71,
                                longitude=-74.0,
                            )
    assert result["status"] == WorkflowStatus.PARTIAL.value


@pytest.mark.asyncio
async def test_route_step_uses_registry_discovery():
    from app.clients import service_client

    instances = [
        {"base_url": "http://route-primary:8006", "instance_role": "PRIMARY"},
    ]

    class FakeResp:
        status_code = 201
        content = b'{"route":{"id":"r99","status":"CALCULATED"},"message":"ok"}'

        def json(self):
            return {"route": {"id": "r99", "status": "CALCULATED"}, "message": "ok"}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def request(self, method, url, **kwargs):
            assert "route-primary" in url
            return FakeResp()

    with patch("app.clients.service_client.discover_ordered_instances", new_callable=AsyncMock, return_value=instances):
        with patch("app.clients.service_client.httpx.AsyncClient", return_value=FakeClient()):
            data = await service_client.call_service(
                "route-service", "POST", "/api/routes/calculate",
                json_body={"origin_lat": 1, "origin_lon": 1, "destination_lat": 2, "destination_lon": 2},
            )
    assert data["route"]["id"] == "r99"
