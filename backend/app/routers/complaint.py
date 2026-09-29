"""投诉与回访接口：登记投诉、登记回访、撤销、重复合并，并按待回访/已回访分组呈现。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.complaint import ComplaintService

router = APIRouter(prefix="/api/complaint", tags=["投诉与回访"])

service = ComplaintService()

LIST_FIELDS = ["投诉单号", "来源", "诉求描述", "受理人", "首次受理时间", "最新受理时间", "回访时限", "最新回访结果", "最新回访时间", "状态"]
GROUPS = ["pending", "visited", "closed"]


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出投诉与回访清单：返回当前全量数据，含受理与回访历史。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "complaint", "total": total, "items": items}


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按投诉单号、来源、诉求描述或受理人检索"),
    group: str | None = Query(default=None, description="pending=待回访，visited=已回访，closed=已撤销/重复"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按关键字与分组读取投诉列表；没有数据时返回空页，不报错。"""
    if group and group not in GROUPS:
        raise HTTPException(status_code=400, detail="分组只支持 pending、visited、closed")
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, group=group, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条投诉明细（含受理记录、历次回访结论）；不存在时给出可读说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"投诉单 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记投诉来源、诉求描述与受理人；与有效主记录重复时并入主记录，不新建单。"""
    entry, missing, message = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/visits", response_model=ActionResult)
def add_visit(entry_id: int, payload: EntryPayload) -> ActionResult:
    """登记一次回访结果与回访时间；历史回访结论追加保留，列表取最新一条。"""
    entry, message = service.add_visit(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/revoke", response_model=ActionResult)
def revoke_entry(entry_id: int) -> ActionResult:
    """撤销投诉：同时清理挂在单上的回访记录，不允许残留。"""
    entry, message = service.revoke(entry_id)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/merge", response_model=ActionResult)
def merge_entry(entry_id: int, payload: EntryPayload) -> ActionResult:
    """把重复录入的投诉单挂到唯一主记录下，原单及其回访记录一并清除。"""
    try:
        master_id = int(payload.values.get("master_id"))
    except (TypeError, ValueError):
        return ActionResult(ok=False, message="请选择要并入的主记录编号")
    entry, message = service.mark_duplicate(entry_id, master_id)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
