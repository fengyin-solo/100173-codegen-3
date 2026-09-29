"""投诉与回访接口：投诉单登记、回访结果登记、超期判定与撤销。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.complaint import ComplaintService

router = APIRouter(prefix="/api/complaint", tags=["投诉与回访"])

service = ComplaintService()

LIST_FIELDS = ["投诉编号", "来源", "诉求描述", "受理人", "受理时间", "回访结果", "回访时间", "状态"]
STATUSES = ["待回访", "已回访", "已撤销"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按投诉编号、来源、受理人、诉求描述检索"),
    status: str | None = Query(default=None, description="待回访、已回访、已撤销"),
    overdue: bool | None = Query(default=None, description="仅看超期未回访"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按关键词、状态与超期标记过滤投诉单列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, overdue=overdue, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出投诉与回访清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "complaint", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条投诉单明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"投诉单 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条投诉单，缺字段或重复录入时说明原因而不是静默丢弃。"""
    entry, error = service.create_entry(payload.values)
    if error:
        return ActionResult(ok=False, message=error)
    return ActionResult(ok=True, message="投诉单已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条投诉单执行登记回访、撤销；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
