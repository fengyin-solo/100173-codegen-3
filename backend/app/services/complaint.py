"""投诉与回访业务规则：投诉单登记、回访结果登记、超期判定与撤销去重。

核心口径：
- 投诉单是主记录，回访记录挂在投诉单下（同一投诉只能挂到一条主记录下）。
- 回访时限自最早一次受理时间起算，超过时限仍未回访的标记为超期。
- 撤销投诉单时清空回访记录，不残留。
- 重复录入（来源+诉求描述相同）直接拦下，不产生第二条主记录。
- 历史投诉保留当时的回访结论，不事后改写。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.store import store

MODULE = "complaint"
REQUIRED_FIELDS = ["来源", "诉求描述", "受理人"]
# 回访时限：自最早一次受理时间起 7 个自然日内完成回访
VISIT_DEADLINE_DAYS = 7
STATUSES = ["待回访", "已回访", "已撤销"]
VISIT_RESULTS = ["满意", "基本满意", "不满意"]
VISIT_METHODS = ["电话", "上门", "信函"]
SOURCES = ["来电", "来访", "来信", "网络", "上级转办"]


def _now() -> datetime:
    """当前时间，抽成函数便于测试时替换。"""
    return datetime.now()


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _fmt_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M")


def _deadline(accepted_at: Any) -> datetime | None:
    """回访时限：按最早一次受理时间起算。"""
    dt = _parse_time(accepted_at)
    if dt is None:
        return None
    return dt + timedelta(days=VISIT_DEADLINE_DAYS)


def _is_overdue(row: dict[str, Any], now: datetime) -> bool:
    """待回访且已过回访时限 → 超期未回访。"""
    if row.get("status") != "待回访":
        return False
    deadline = _deadline(row.get("受理时间"))
    if deadline is None:
        return False
    return now > deadline


def _latest_visit(row: dict[str, Any]) -> dict[str, Any] | None:
    """取最近一次回访记录；历史结论保留在回访记录列表里，不覆盖。"""
    visits = row.get("回访记录") or []
    if not visits:
        return None
    return visits[-1]


def _enrich(row: dict[str, Any], now: datetime) -> dict[str, Any]:
    """在投诉单上补展示字段：回访结果、回访时间、回访时限、是否超期。"""
    visit = _latest_visit(row)
    enriched = dict(row)
    enriched["回访结果"] = visit.get("回访结果") if visit else None
    enriched["回访时间"] = visit.get("回访时间") if visit else None
    enriched["回访人"] = visit.get("回访人") if visit else None
    enriched["回访方式"] = visit.get("回访方式") if visit else None
    deadline = _deadline(row.get("受理时间"))
    enriched["回访时限"] = _fmt_time(deadline) if deadline else None
    enriched["是否超期"] = _is_overdue(row, now)
    return enriched


class ComplaintService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        overdue: bool | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        now = _now()
        # 读取时按当前时间刷新超期标记，运营概览与列表取同一份口径
        for row in rows:
            row["abnormal"] = _is_overdue(row, now)
        items = [_enrich(row, now) for row in rows]
        if keyword:
            items = [
                item for item in items
                if keyword in str(item.get("投诉编号", ""))
                or keyword in str(item.get("来源", ""))
                or keyword in str(item.get("受理人", ""))
                or keyword in str(item.get("诉求描述", ""))
            ]
        if status:
            items = [item for item in items if item.get("status") == status]
        if overdue is True:
            items = [item for item in items if item.get("是否超期")]
        elif overdue is False:
            items = [item for item in items if not item.get("是否超期")]
        total = len(items)
        start = max(page - 1, 0) * size
        return items[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        if row is None:
            return None
        now = _now()
        row["abnormal"] = _is_overdue(row, now)
        return _enrich(row, now)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        rows = store.rows(MODULE)
        source = str(values.get("来源") or "").strip()
        desc = str(values.get("诉求描述") or "").strip()
        # 同一投诉只能挂到一条主记录下：来源+诉求描述相同且未撤销的视为重复录入
        for row in rows:
            if row.get("status") == "已撤销":
                continue
            if str(row.get("来源", "")).strip() == source and str(row.get("诉求描述", "")).strip() == desc:
                return None, "该投诉单已存在，请勿重复录入"
        now = _now()
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry["投诉编号"] = str(values.get("投诉编号") or "").strip() or f"COMP-{entry['id']:04d}"
        entry["来源"] = source
        entry["诉求描述"] = desc
        entry["受理人"] = str(values.get("受理人") or "").strip()
        # 受理时间取最早一次受理；不提供则取当前时间，作为回访时限起算点
        entry["受理时间"] = str(values.get("受理时间") or "").strip() or _fmt_time(now)
        entry["status"] = "待回访"
        entry["pending"] = True
        entry["abnormal"] = _is_overdue(entry, now)
        entry["回访记录"] = []
        rows.append(entry)
        return _enrich(entry, now), None

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        row = store.find(MODULE, entry_id)
        if row is None:
            return None, f"投诉单 {entry_id} 不存在或已归档"
        now = _now()
        if action == "登记回访":
            return self._register_visit(row, values, now)
        if action == "撤销":
            return self._revoke(row, now)
        return None, f"动作「{action}」不属于投诉与回访可执行范围"

    def _register_visit(
        self, row: dict[str, Any], values: dict[str, Any], now: datetime
    ) -> tuple[dict[str, Any] | None, str]:
        if row.get("status") == "已撤销":
            return None, "该投诉单已撤销，不能登记回访"
        result = str(values.get("回访结果") or "").strip()
        if not result:
            return None, "缺少必填字段：回访结果"
        if result not in VISIT_RESULTS:
            return None, f"回访结果「{result}」不在允许范围内"
        visit = {
            "回访结果": result,
            "回访方式": str(values.get("回访方式") or "").strip() or None,
            "回访人": str(values.get("回访人") or "").strip() or None,
            "回访时间": _fmt_time(now),
        }
        # 历史结论保留：追加到回访记录列表，不覆盖已有结论
        row.setdefault("回访记录", []).append(visit)
        row["status"] = "已回访"
        row["pending"] = False
        row["abnormal"] = False
        return _enrich(row, now), "回访结果已登记"

    def _revoke(self, row: dict[str, Any], now: datetime) -> tuple[dict[str, Any] | None, str]:
        # 撤销时不得残留回访记录：清空回访记录，状态置为已撤销
        row["回访记录"] = []
        row["status"] = "已撤销"
        row["pending"] = False
        row["abnormal"] = False
        return _enrich(row, now), "投诉单已撤销"
