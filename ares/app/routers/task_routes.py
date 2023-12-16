from fastapi import Request, APIRouter
from fastapi.security import OAuth2PasswordBearer
from slowapi.util import get_remote_address
from slowapi import Limiter

from app.internal.errors.global_exceptions import (
    ObjectNotFound,
)

from app.internal.utilities.auth import require_valid_token
from app.internal.utilities.task import task_manager
from app.internal.utilities.reports import get_all_reports, get_one_report

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@router.get("/api/tasks")
@require_valid_token
async def get_tasks(request: Request):
    return {"data": task_manager.get_tasks()}


@router.get("/api/tasks/{task_id}")
@require_valid_token
async def get_task_progress(request: Request, task_id: str):
    task = task_manager.get_task(task_id)

    if task is None:
        raise ObjectNotFound("Task")

    return {"data": task["progress"]}


@router.delete("/api/tasks/{task_id}")
@require_valid_token
async def delete_task(request: Request, task_id: str):
    try:
        task_manager.delete_task(task_id)
    except KeyError:
        raise ObjectNotFound("Task")

    return {"data": "Task deleted"}

@router.get("/api/reports/{report_id}")
@require_valid_token
async def get_report(request: Request, report_id: str):
    reports = await get_one_report(report_id)
    
    return {"data": reports}

@router.get("/api/reports")
@require_valid_token
async def get_reports(request: Request):
    reports = await get_all_reports()
    
    return {"data": reports}

