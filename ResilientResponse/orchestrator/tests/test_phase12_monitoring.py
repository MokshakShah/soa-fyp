"""
Phase 12 — Orchestrator monitoring tests.

Covers:
  - GET /api/workflows/summary counts (total, running, completed, partial, failed)
  - Structured logging for workflow start/completion/failure/partial
  - Workflow engine produces correct PARTIAL status on non-critical step failure
  - Workflow engine produces correct FAILED status on critical step failure
"""
import logging
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from main import app
from app.workflows.engine import run_workflow
from app.models.workflow import WorkflowStatus


# ─── /api/workflows/summary ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_workflow_summary_returns_correct_fields():
    """GET /api/workflows/summary returns total, by_status, running, completed, partial, failed."""
    summary_data = {
        "total": 15,
        "by_status": {"COMPLETED": 10, "PARTIAL": 2, "FAILED": 1, "RUNNING": 2},
        "running": 2,
        "completed": 10,
        "partial": 2,
        "failed": 1,
    }
    with patch("main.register_with_registry", new_callable=AsyncMock):
        with patch("app.routers.workflows.workflow_status_summary", new_callable=AsyncMock, return_value=summary_data):
            with patch("app.routers.workflows.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/workflows/summary")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 15
    assert data["running"] == 2
    assert data["completed"] == 10
    assert data["partial"] == 2
    assert data["failed"] == 1
    assert "by_status" in data


@pytest.mark.asyncio
async def test_workflow_summary_empty_db():
    """When no workflows exist, all counts are zero."""
    summary_data = {
        "total": 0,
        "by_status": {},
        "running": 0, "completed": 0, "partial": 0, "failed": 0,
    }
    with patch("main.register_with_registry", new_callable=AsyncMock):
        with patch("app.routers.workflows.workflow_status_summary", new_callable=AsyncMock, return_value=summary_data):
            with patch("app.routers.workflows.get_db"):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    resp = await ac.get("/api/workflows/summary")

    data = resp.json()
    assert data["total"] == 0
    assert data["running"] == 0


# ─── Workflow engine structured logging ───────────────────────────────────────

@pytest.mark.asyncio
async def test_engine_logs_workflow_start(caplog):
    """run_workflow logs [workflow] START with incident_id, workflow_id, type, total_steps."""
    async def fake_execute(step, context):
        if step.action == "search_hospitals":
            context["hospitals"] = [{"id": "h1"}]
        if step.action == "search_resources":
            context["resources"] = [{"id": "r1"}]
        if step.action in ("reserve_hospital_beds", "allocate_resource"):
            return {"ok": True}
        return {}

    with caplog.at_level(logging.INFO, logger="orchestrator.engine"):
        with patch("app.workflows.engine.create_workflow", new_callable=AsyncMock) as mock_create:
            with patch("app.workflows.engine.update_workflow", new_callable=AsyncMock):
                with patch("app.workflows.engine.create_workflow_event", new_callable=AsyncMock):
                    with patch("app.workflows.engine.get_workflow", new_callable=AsyncMock) as mock_get:
                        with patch("app.workflows.engine.list_workflow_events", new_callable=AsyncMock, return_value=[]):
                            with patch("app.workflows.engine.execute_step_action", side_effect=fake_execute):
                                mock_create.return_value = {
                                    "id": "wf-log-1",
                                    "created_at": datetime.utcnow(),
                                }
                                mock_get.return_value = {
                                    "id": "wf-log-1",
                                    "status": WorkflowStatus.COMPLETED.value,
                                }
                                await run_workflow(
                                    MagicMock(),
                                    incident_id="inc-log-1",
                                    disaster_type="FLOOD",
                                    classification={"disaster_type": "FLOOD", "severity": "HIGH"},
                                )

    start_logs = [r for r in caplog.records if "[workflow] START" in r.message]
    assert len(start_logs) >= 1, "Expected [workflow] START log entry"
    assert "inc-log-1" in start_logs[0].message
    assert "FLOOD" in start_logs[0].message


@pytest.mark.asyncio
async def test_engine_logs_workflow_completed(caplog):
    """Successful workflow logs [workflow] COMPLETED."""
    async def fake_execute(step, context):
        if step.action == "search_hospitals":
            context["hospitals"] = [{"id": "h1"}]
        if step.action == "search_resources":
            context["resources"] = [{"id": "r1"}]
        if step.action in ("reserve_hospital_beds", "allocate_resource"):
            return {"ok": True}
        return {}

    with caplog.at_level(logging.INFO, logger="orchestrator.engine"):
        with patch("app.workflows.engine.create_workflow", new_callable=AsyncMock) as mock_create:
            with patch("app.workflows.engine.update_workflow", new_callable=AsyncMock):
                with patch("app.workflows.engine.create_workflow_event", new_callable=AsyncMock):
                    with patch("app.workflows.engine.get_workflow", new_callable=AsyncMock) as mock_get:
                        with patch("app.workflows.engine.list_workflow_events", new_callable=AsyncMock, return_value=[]):
                            with patch("app.workflows.engine.execute_step_action", side_effect=fake_execute):
                                mock_create.return_value = {"id": "wf-log-2", "created_at": datetime.utcnow()}
                                mock_get.return_value = {"id": "wf-log-2", "status": WorkflowStatus.COMPLETED.value}
                                await run_workflow(
                                    MagicMock(),
                                    incident_id="inc-log-2",
                                    disaster_type="FIRE",
                                    classification={"disaster_type": "FIRE", "severity": "HIGH"},
                                )

    completed_logs = [r for r in caplog.records if "[workflow] COMPLETED" in r.message]
    assert len(completed_logs) >= 1


@pytest.mark.asyncio
async def test_engine_logs_workflow_partial(caplog):
    """PARTIAL workflow (non-critical step failed) logs [workflow] PARTIAL."""
    from app.clients.service_client import ServiceCallError

    async def fake_execute(step, context):
        if step.action == "search_hospitals":
            context["hospitals"] = [{"id": "h1"}]
        if step.action == "reserve_hospital_beds":
            return {"hospital_id": "h1"}
        if step.action == "search_resources":
            context["resources"] = [{"id": "r1"}]
        if step.action == "allocate_resource":
            return {"resource_id": "r1"}
        if step.action == "plan_route":
            raise ServiceCallError("route-provider down")
        return {}

    with caplog.at_level(logging.WARNING, logger="orchestrator.engine"):
        with patch("app.workflows.engine.create_workflow", new_callable=AsyncMock) as mock_create:
            with patch("app.workflows.engine.update_workflow", new_callable=AsyncMock):
                with patch("app.workflows.engine.create_workflow_event", new_callable=AsyncMock):
                    with patch("app.workflows.engine.get_workflow", new_callable=AsyncMock) as mock_get:
                        with patch("app.workflows.engine.list_workflow_events", new_callable=AsyncMock, return_value=[]):
                            with patch("app.workflows.engine.execute_step_action", side_effect=fake_execute):
                                mock_create.return_value = {"id": "wf-log-3", "created_at": datetime.utcnow()}
                                mock_get.return_value = {"id": "wf-log-3", "status": WorkflowStatus.PARTIAL.value}
                                await run_workflow(
                                    MagicMock(),
                                    incident_id="inc-log-3",
                                    disaster_type="EARTHQUAKE",
                                    classification={"disaster_type": "EARTHQUAKE"},
                                )

    partial_logs = [r for r in caplog.records if "[workflow] PARTIAL" in r.message]
    assert len(partial_logs) >= 1


@pytest.mark.asyncio
async def test_engine_logs_workflow_failed(caplog):
    """Critical step failure logs [workflow] FAILED with reason."""
    from app.clients.service_client import ServiceCallError

    async def fake_execute(step, context):
        if step.action == "search_hospitals":
            context["hospitals"] = []
        if step.action == "reserve_hospital_beds":
            raise ServiceCallError("No hospitals available")
        return {}

    with caplog.at_level(logging.ERROR, logger="orchestrator.engine"):
        with patch("app.workflows.engine.create_workflow", new_callable=AsyncMock) as mock_create:
            with patch("app.workflows.engine.update_workflow", new_callable=AsyncMock):
                with patch("app.workflows.engine.create_workflow_event", new_callable=AsyncMock):
                    with patch("app.workflows.engine.get_workflow", new_callable=AsyncMock) as mock_get:
                        with patch("app.workflows.engine.list_workflow_events", new_callable=AsyncMock, return_value=[]):
                            with patch("app.workflows.engine.execute_step_action", side_effect=fake_execute):
                                mock_create.return_value = {"id": "wf-log-4", "created_at": datetime.utcnow()}
                                mock_get.return_value = {
                                    "id": "wf-log-4",
                                    "status": WorkflowStatus.FAILED.value,
                                    "failure_reason": "No hospitals available",
                                }
                                await run_workflow(
                                    MagicMock(),
                                    incident_id="inc-log-4",
                                    disaster_type="CYCLONE",
                                    classification={"disaster_type": "CYCLONE"},
                                )

    failed_logs = [r for r in caplog.records if "[workflow] FAILED" in r.message]
    assert len(failed_logs) >= 1
    assert "No hospitals available" in failed_logs[0].message


@pytest.mark.asyncio
async def test_engine_logs_step_start_and_ok(caplog):
    """Engine logs STEP_START and STEP_OK for each successful step."""
    async def fake_execute(step, context):
        if step.action == "search_hospitals":
            context["hospitals"] = [{"id": "h1"}]
        if step.action == "search_resources":
            context["resources"] = [{"id": "r1"}]
        if step.action in ("reserve_hospital_beds", "allocate_resource"):
            return {"ok": True}
        return {}

    with caplog.at_level(logging.INFO, logger="orchestrator.engine"):
        with patch("app.workflows.engine.create_workflow", new_callable=AsyncMock) as mock_create:
            with patch("app.workflows.engine.update_workflow", new_callable=AsyncMock):
                with patch("app.workflows.engine.create_workflow_event", new_callable=AsyncMock):
                    with patch("app.workflows.engine.get_workflow", new_callable=AsyncMock) as mock_get:
                        with patch("app.workflows.engine.list_workflow_events", new_callable=AsyncMock, return_value=[]):
                            with patch("app.workflows.engine.execute_step_action", side_effect=fake_execute):
                                mock_create.return_value = {"id": "wf-log-5", "created_at": datetime.utcnow()}
                                mock_get.return_value = {"id": "wf-log-5", "status": WorkflowStatus.COMPLETED.value}
                                await run_workflow(
                                    MagicMock(),
                                    incident_id="inc-log-5",
                                    disaster_type="LANDSLIDE",
                                    classification={"disaster_type": "LANDSLIDE"},
                                )

    step_starts = [r for r in caplog.records if "[workflow] STEP_START" in r.message]
    step_oks    = [r for r in caplog.records if "[workflow] STEP_OK" in r.message]
    assert len(step_starts) >= 1
    assert len(step_oks) >= 1
