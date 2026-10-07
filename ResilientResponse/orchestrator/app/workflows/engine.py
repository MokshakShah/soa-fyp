"""
Phase 7 workflow engine — sequential execution with persistence and resilience.
Phase 12: structured operational logging added throughout.
"""
import logging
import time
from datetime import datetime
from typing import Any, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.clients.service_client import ServiceCallError, elapsed_ms
from app.discovery import ServiceUnavailableError
from app.models.workflow import WorkflowStatus, WorkflowEventStatus
from app.repositories.workflow_repo import (
    create_workflow,
    update_workflow,
    create_workflow_event,
    list_workflow_events,
    get_workflow,
)
from app.workflows.definitions import WorkflowDefinition, get_workflow_definition
from app.workflows.step_handlers import execute_step_action

logger = logging.getLogger("orchestrator.engine")


def select_workflow(disaster_type: str) -> Optional[WorkflowDefinition]:
    return get_workflow_definition(disaster_type)


async def run_workflow(
    db: AsyncIOMotorDatabase,
    *,
    incident_id: str,
    disaster_type: str,
    classification: dict[str, Any],
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    expand_search: bool = False,
    search_timeout_seconds: int = 25,
) -> dict:
    definition = select_workflow(disaster_type)
    if definition is None:
        raise ValueError(f"Unsupported disaster type for workflow: {disaster_type}")

    total_steps = len(definition.steps)
    workflow = await create_workflow(db, {
        "incident_id": incident_id,
        "workflow_type": definition.workflow_type,
        "status": WorkflowStatus.PENDING.value,
        "current_step": 0,
        "total_steps": total_steps,
        "classification_snapshot": classification,
        "failure_reason": None,
        "step_results": [],
    })

    workflow_id = workflow["id"]

    logger.info(
        "[workflow] START incident_id=%s workflow_id=%s type=%s total_steps=%d",
        incident_id, workflow_id, disaster_type, total_steps,
    )

    context: dict[str, Any] = {
        "incident_id": incident_id,
        "workflow_id": workflow_id,
        "classification": classification,
        "latitude": latitude,
        "longitude": longitude,
        "expand_search": expand_search,
        "search_deadline": time.monotonic() + max(1, min(search_timeout_seconds, 25))
        if expand_search else None,
        "reserve_beds": definition.steps[2].params.get("beds") if total_steps > 2 else 1,
    }

    await update_workflow(db, workflow_id, {
        "status": WorkflowStatus.RUNNING.value,
        "started_at": workflow.get("created_at"),
        "current_step": 0,
    })

    had_non_critical_failure = False
    failure_reason: Optional[str] = None

    for index, step in enumerate(definition.steps):
        step_num = index + 1
        await update_workflow(db, workflow_id, {"current_step": step_num})

        logger.info(
            "[workflow] STEP_START workflow_id=%s step=%d/%d action=%s service=%s",
            workflow_id, step_num, total_steps, step.action, step.service,
        )

        start = time.perf_counter()
        try:
            result = await execute_step_action(step, context)
            duration = elapsed_ms(start)

            logger.info(
                "[workflow] STEP_OK workflow_id=%s step=%d action=%s duration_ms=%d",
                workflow_id, step_num, step.action, duration,
            )

            await create_workflow_event(db, {
                "workflow_id": workflow_id,
                "step_index": step_num,
                "service": step.service,
                "action": step.action,
                "status": WorkflowEventStatus.SUCCESS.value,
                "error": None,
                "duration_ms": duration,
                "result": result,
            })
        except (ServiceCallError, ServiceUnavailableError) as exc:
            duration = elapsed_ms(start)
            err_msg = str(exc)

            logger.warning(
                "[workflow] STEP_FAIL workflow_id=%s step=%d action=%s critical=%s duration_ms=%d error=%s",
                workflow_id, step_num, step.action, step.critical, duration, err_msg,
            )

            await create_workflow_event(db, {
                "workflow_id": workflow_id,
                "step_index": step_num,
                "service": step.service,
                "action": step.action,
                "status": WorkflowEventStatus.FAILED.value,
                "error": err_msg,
                "duration_ms": duration,
                "result": None,
            })

            if step.critical:
                failure_reason = err_msg
                await update_workflow(db, workflow_id, {
                    "status": WorkflowStatus.FAILED.value,
                    "failure_reason": failure_reason,
                    "completed_at": _utcnow(),
                })
                logger.error(
                    "[workflow] FAILED workflow_id=%s incident_id=%s reason=%s",
                    workflow_id, incident_id, err_msg,
                )
                return await _final_workflow(db, workflow_id)

            had_non_critical_failure = True

        except Exception as exc:
            duration = elapsed_ms(start)
            err_msg = str(exc)
            logger.exception(
                "[workflow] STEP_UNEXPECTED workflow_id=%s step=%d action=%s",
                workflow_id, step_num, step.action,
            )
            await create_workflow_event(db, {
                "workflow_id": workflow_id,
                "step_index": step_num,
                "service": step.service,
                "action": step.action,
                "status": WorkflowEventStatus.FAILED.value,
                "error": err_msg,
                "duration_ms": duration,
                "result": None,
            })
            if step.critical:
                failure_reason = err_msg
                await update_workflow(db, workflow_id, {
                    "status": WorkflowStatus.FAILED.value,
                    "failure_reason": failure_reason,
                    "completed_at": _utcnow(),
                })
                logger.error(
                    "[workflow] FAILED workflow_id=%s incident_id=%s reason=%s",
                    workflow_id, incident_id, err_msg,
                )
                return await _final_workflow(db, workflow_id)
            had_non_critical_failure = True

    final_status = WorkflowStatus.PARTIAL if had_non_critical_failure else WorkflowStatus.COMPLETED
    await update_workflow(db, workflow_id, {
        "status": final_status.value,
        "failure_reason": failure_reason,
        "completed_at": _utcnow(),
        "current_step": total_steps,
    })

    if final_status == WorkflowStatus.PARTIAL:
        logger.warning(
            "[workflow] PARTIAL workflow_id=%s incident_id=%s",
            workflow_id, incident_id,
        )
    else:
        logger.info(
            "[workflow] COMPLETED workflow_id=%s incident_id=%s",
            workflow_id, incident_id,
        )

    return await _final_workflow(db, workflow_id)


def _utcnow():
    return datetime.utcnow()


async def _final_workflow(db: AsyncIOMotorDatabase, workflow_id: str) -> dict:
    wf = await get_workflow(db, workflow_id)
    events = await list_workflow_events(db, workflow_id)
    return {**wf, "events": events}
