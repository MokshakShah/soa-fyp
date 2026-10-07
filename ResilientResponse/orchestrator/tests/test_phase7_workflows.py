"""
Phase 7 — Orchestrator workflow engine tests.
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from main import app
from app.workflows.definitions import get_workflow_definition, SUPPORTED_DISASTER_TYPES
from app.workflows.engine import select_workflow, run_workflow
from app.clients.service_client import ServiceCallError
from app.discovery import ServiceUnavailableError
from app.models.workflow import WorkflowStatus, WorkflowEventStatus


def _mock_db():
    workflows = {}
    events = []
    wf_counter = {"n": 0}

    async def insert_workflow(data):
        wf_counter["n"] += 1
        oid = f"507f1f77bcf86cd7994390{wf_counter['n']:02d}"
        doc = {"_id": oid, **data}
        workflows[oid] = doc
        return doc

    async def find_workflow(oid):
        return workflows.get(oid)

    async def update_workflow(oid, data):
        if oid not in workflows:
            return None
        workflows[oid].update(data)
        return workflows[oid]

    async def insert_event(data):
        eid = f"evt{len(events)}"
        doc = {"_id": eid, **data}
        events.append(doc)
        return doc

    db = MagicMock()
    db.workflows.insert_one = AsyncMock(side_effect=lambda d: MagicMock(
        inserted_id=list(workflows.keys())[-1] if workflows else "507f1f77bcf86cd799439011"
    ))
    db.workflows.find_one = AsyncMock(side_effect=lambda q: workflows.get(str(q.get("_id"))))
    db.workflows.find_one_and_update = AsyncMock(
        side_effect=lambda q, upd, **kw: update_workflow(str(q["_id"]), upd["$set"])
    )
    db.workflow_events.insert_one = AsyncMock(side_effect=lambda d: MagicMock(inserted_id="e1"))
    db.workflow_events.find_one = AsyncMock(side_effect=lambda q: events[-1] if events else None)
    db.workflow_events.find = MagicMock(return_value=MagicMock(
        sort=MagicMock(return_value=_AsyncIter(events))
    ))

    return db, workflows, events, insert_workflow, update_workflow, insert_event


class _AsyncIter:
    def __init__(self, items):
        self._items = items

    def __aiter__(self):
        self._i = 0
        return self

    async def __anext__(self):
        if self._i >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._i]
        self._i += 1
        return item


@pytest.mark.parametrize("disaster", sorted(SUPPORTED_DISASTER_TYPES))
def test_workflow_selection(disaster):
    wf = select_workflow(disaster)
    assert wf is not None
    assert wf.workflow_type == disaster
    assert len(wf.steps) >= 6


def test_workflow_selection_unknown():
    assert select_workflow("TSUNAMI") is not None
    assert select_workflow("NOT_A_REAL_DISASTER") is None
    assert select_workflow("UNKNOWN") is None


def test_step_ordering():
    wf = get_workflow_definition("FLOOD")
    actions = [s.action for s in wf.steps]
    assert actions.index("search_hospitals") < actions.index("reserve_hospital_beds")
    assert actions.index("search_resources") < actions.index("allocate_resource")
    assert actions[-2:] == ["plan_route", "dispatch_notification"]


@pytest.mark.asyncio
async def test_successful_workflow_execution():
    hospitals = [{"id": "h1", "name": "City Hospital"}]
    resources = [{"id": "r1", "name": "Ambulance"}]

    async def fake_execute(step, context):
        if step.action == "record_classification":
            return {"recorded": True}
        if step.action == "search_hospitals":
            context["hospitals"] = hospitals
            return {"count": 1}
        if step.action == "reserve_hospital_beds":
            context["reserved_hospital_id"] = "h1"
            return {"hospital_id": "h1"}
        if step.action == "search_police":
            return {"count": 1}
        if step.action == "search_resources":
            context["resources"] = resources
            return {"count": 1}
        if step.action == "allocate_resource":
            return {"resource_id": "r1"}
        raise ServiceCallError("unexpected")

    with patch("app.workflows.engine.create_workflow", new_callable=AsyncMock) as mock_create:
        with patch("app.workflows.engine.update_workflow", new_callable=AsyncMock) as mock_update:
            with patch("app.workflows.engine.create_workflow_event", new_callable=AsyncMock):
                with patch("app.workflows.engine.get_workflow", new_callable=AsyncMock) as mock_get:
                    with patch("app.workflows.engine.list_workflow_events", new_callable=AsyncMock, return_value=[]):
                        with patch("app.workflows.engine.execute_step_action", side_effect=fake_execute):
                            mock_create.return_value = {
                                "id": "wf1",
                                "created_at": datetime.utcnow(),
                                "status": "PENDING",
                            }
                            mock_get.return_value = {
                                "id": "wf1",
                                "status": WorkflowStatus.COMPLETED.value,
                                "workflow_type": "FLOOD",
                            }
                            db = MagicMock()
                            result = await run_workflow(
                                db,
                                incident_id="inc-1",
                                disaster_type="FLOOD",
                                classification={"disaster_type": "FLOOD", "severity": "HIGH"},
                                latitude=40.71,
                                longitude=-74.0,
                            )
    assert result["status"] == WorkflowStatus.COMPLETED.value
    assert mock_update.called


@pytest.mark.asyncio
async def test_partial_workflow_non_critical_failure():
    async def fake_execute(step, context):
        if step.action == "search_police":
            raise ServiceCallError("police search failed")
        if step.action == "search_hospitals":
            context["hospitals"] = [{"id": "h1"}]
            return {"count": 1}
        if step.action == "reserve_hospital_beds":
            return {"hospital_id": "h1"}
        if step.action == "search_resources":
            context["resources"] = [{"id": "r1"}]
            return {"count": 1}
        if step.action == "allocate_resource":
            return {"resource_id": "r1"}
        return {}

    with patch("app.workflows.engine.create_workflow", new_callable=AsyncMock) as mock_create:
        with patch("app.workflows.engine.update_workflow", new_callable=AsyncMock):
            with patch("app.workflows.engine.create_workflow_event", new_callable=AsyncMock):
                with patch("app.workflows.engine.get_workflow", new_callable=AsyncMock) as mock_get:
                    with patch("app.workflows.engine.list_workflow_events", new_callable=AsyncMock, return_value=[]):
                        with patch("app.workflows.engine.execute_step_action", side_effect=fake_execute):
                            mock_create.return_value = {"id": "wf2", "created_at": datetime.utcnow()}
                            mock_get.return_value = {"id": "wf2", "status": WorkflowStatus.PARTIAL.value}
                            db = MagicMock()
                            result = await run_workflow(
                                db,
                                incident_id="inc-2",
                                disaster_type="FIRE",
                                classification={"disaster_type": "FIRE"},
                            )
    assert result["status"] == WorkflowStatus.PARTIAL.value


@pytest.mark.asyncio
async def test_failed_workflow_critical_step():
    async def fake_execute(step, context):
        if step.action == "search_hospitals":
            context["hospitals"] = []
            return {"count": 0}
        if step.action == "reserve_hospital_beds":
            raise ServiceCallError("No hospitals available to reserve beds")
        return {}

    with patch("app.workflows.engine.create_workflow", new_callable=AsyncMock) as mock_create:
        with patch("app.workflows.engine.update_workflow", new_callable=AsyncMock):
            with patch("app.workflows.engine.create_workflow_event", new_callable=AsyncMock):
                with patch("app.workflows.engine.get_workflow", new_callable=AsyncMock) as mock_get:
                    with patch("app.workflows.engine.list_workflow_events", new_callable=AsyncMock, return_value=[]):
                        with patch("app.workflows.engine.execute_step_action", side_effect=fake_execute):
                            mock_create.return_value = {"id": "wf3", "created_at": datetime.utcnow()}
                            mock_get.return_value = {
                                "id": "wf3",
                                "status": WorkflowStatus.FAILED.value,
                                "failure_reason": "No hospitals",
                            }
                            db = MagicMock()
                            result = await run_workflow(
                                db,
                                incident_id="inc-3",
                                disaster_type="EARTHQUAKE",
                                classification={"disaster_type": "EARTHQUAKE"},
                            )
    assert result["status"] == WorkflowStatus.FAILED.value


@pytest.mark.asyncio
async def test_workflow_events_persisted():
    recorded = []

    async def capture_event(db, data):
        recorded.append(data)
        return {"id": "e1", **data}

    async def fake_execute(step, context):
        if step.action == "search_hospitals":
            context["hospitals"] = [{"id": "h1"}]
        if step.action == "search_resources":
            context["resources"] = [{"id": "r1"}]
        if step.action in ("reserve_hospital_beds", "allocate_resource"):
            return {"ok": True}
        return {}

    with patch("app.workflows.engine.create_workflow", new_callable=AsyncMock) as mock_create:
        with patch("app.workflows.engine.update_workflow", new_callable=AsyncMock):
            with patch("app.workflows.engine.create_workflow_event", side_effect=capture_event):
                with patch("app.workflows.engine.get_workflow", new_callable=AsyncMock) as mock_get:
                    with patch("app.workflows.engine.list_workflow_events", new_callable=AsyncMock, return_value=recorded):
                        with patch("app.workflows.engine.execute_step_action", side_effect=fake_execute):
                            mock_create.return_value = {"id": "wf4", "created_at": datetime.utcnow()}
                            mock_get.return_value = {"id": "wf4", "status": WorkflowStatus.COMPLETED.value}
                            await run_workflow(
                                MagicMock(),
                                incident_id="inc-4",
                                disaster_type="CHEMICAL",
                                classification={"disaster_type": "CHEMICAL"},
                            )
    assert len(recorded) >= 4
    # Phase 9: dispatch_notification is now executed (not skipped), so there are
    # no SKIPPED events in a successful workflow execution.
    skipped = [e for e in recorded if e["status"] == WorkflowEventStatus.SKIPPED.value]
    assert len(skipped) == 0


@pytest.mark.asyncio
async def test_service_client_failover():
    from app.clients import service_client

    instances = [
        {"base_url": "http://primary:8004", "instance_id": "p1", "instance_role": "PRIMARY"},
        {"base_url": "http://backup:8014", "instance_id": "b1", "instance_role": "BACKUP"},
    ]

    class FakeResp:
        def __init__(self, status, data=None):
            self.status_code = status
            self.content = b"{}"
            self._data = data or {}

        def json(self):
            return self._data

    call_count = {"n": 0}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def request(self, method, url, **kwargs):
            call_count["n"] += 1
            if "primary" in url:
                return FakeResp(503)
            return FakeResp(200, {"items": []})

    with patch("app.clients.service_client.discover_ordered_instances", new_callable=AsyncMock, return_value=instances):
        with patch("app.clients.service_client.httpx.AsyncClient", return_value=FakeClient()):
            data = await service_client.call_service(
                "hospital-service", "GET", "/api/hospitals/search"
            )
    assert data == {"items": []}
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_api_execute_unknown_disaster():
    with patch("main.register_with_registry", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/workflows/execute", json={
                "incident_id": "x",
                    "disaster_type": "NOT_A_REAL_DISASTER",
            })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_api_execute_success():
    with patch("main.register_with_registry", new_callable=AsyncMock):
        with patch("app.routers.workflows.run_workflow", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {
                "id": "wf99",
                "status": "COMPLETED",
                "workflow_type": "FLOOD",
                "events": [],
            }
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/workflows/execute", json={
                    "incident_id": "inc-99",
                    "disaster_type": "FLOOD",
                    "latitude": 40.71,
                    "longitude": -74.0,
                })
    assert resp.status_code == 200
    assert resp.json()["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_discovery_ordered_primary_first():
    from app.discovery import discover_ordered_instances

    payload = {
        "instances": [
            {"base_url": "http://backup:8014", "instance_role": "BACKUP", "status": "UP"},
            {"base_url": "http://primary:8004", "instance_role": "PRIMARY", "status": "UP"},
        ]
    }

    class FakeResp:
        status_code = 200

        def json(self):
            return payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            pass

        async def get(self, url):
            return FakeResp()

    with patch("app.discovery.httpx.AsyncClient", return_value=FakeClient()):
        ordered = await discover_ordered_instances("hospital-service")
    assert ordered[0]["instance_role"] == "PRIMARY"
