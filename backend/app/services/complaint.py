"""投诉与回访业务规则：投诉登记、重复合并、回访、撤销与超期判断都收在这里。

几个关键口径：

- 同一条投诉只能挂在一条主记录下：按「来源 + 诉求描述」判重，重复登记不新建单，
  而是把新的受理痕迹追加到已有主记录；已经存在的重复单也可以通过「标记重复」合并。
- 回访时限按最早一次受理时间起算（VISIT_LIMIT_HOURS），重复登记不会把期限顺延。
- 投诉撤销或重复单被合并时，其名下不得残留回访记录：回访记录随单一起清理，
  只有主记录下挂着的回访（含历史回访结论）会被保留。
- 历史投诉按当时的回访结论保留：再次回访是追加而不是覆盖，列表展示最新一次。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.store import store

MODULE = "complaint"
REQUIRED_FIELDS = ["来源", "诉求描述", "受理人"]
STATUS_PENDING = "待回访"
STATUS_DONE = "已回访"
STATUS_REVOKED = "已撤销"
STATUS_DUPLICATE = "重复录入"
ACTIVE_STATUSES = [STATUS_PENDING, STATUS_DONE]

# 回访时限：自最早一次受理起 48 小时内完成。
VISIT_LIMIT_HOURS = 48
TIME_FORMATS = ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _normalize_text(value: Any) -> str:
    return "".join(str(value or "").split()).lower()


class ComplaintService:
    def __init__(self) -> None:
        # 概览卡片在任何页面打开前都可能被请求，先把依赖当前时间的超期标记刷一遍。
        store.on_overview(self.refresh_overdue_flags)

    # ---------- 派生状态 ----------

    def _deadline(self, entry: dict[str, Any]) -> datetime | None:
        first = _parse_time(entry.get("首次受理时间"))
        if first is None:
            return None
        return first + timedelta(hours=VISIT_LIMIT_HOURS)

    def refresh_overdue_flags(self) -> None:
        """按当前时间刷新待回访单的超期标记；已回访/已撤销不再算超期。"""
        now = datetime.now()
        for entry in store.rows(MODULE):
            overdue = False
            if entry.get("status") == STATUS_PENDING:
                deadline = self._deadline(entry)
                overdue = deadline is not None and now > deadline
            entry["abnormal"] = overdue

    def _snapshot(self, entry: dict[str, Any]) -> dict[str, Any]:
        """给前端的视图：在同一份投诉记录上带出最新回访结果、回访时间与分组、超期信息。"""
        self.refresh_overdue_flags()
        visits = entry.get("回访记录") or []
        latest = visits[-1] if visits else {}
        deadline = self._deadline(entry)
        if entry.get("status") == STATUS_PENDING:
            group = "pending"
        elif entry.get("status") == STATUS_DONE:
            group = "visited"
        else:
            group = "closed"
        return {
            **entry,
            "分组": group,
            "最新回访结果": latest.get("结果", ""),
            "最新回访时间": latest.get("时间", ""),
            "回访时限": deadline.strftime("%Y-%m-%d %H:%M") if deadline else "",
            "超期": bool(entry.get("abnormal")),
            "待回访": entry.get("status") == STATUS_PENDING,
        }

    # ---------- 查询 ----------

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        group: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        self.refresh_overdue_flags()
        rows = list(store.rows(MODULE))
        if keyword:
            needle = keyword.strip()
            rows = [
                row for row in rows
                if needle in str(row.get("投诉单号", ""))
                or needle in str(row.get("来源", ""))
                or needle in str(row.get("诉求描述", ""))
                or needle in str(row.get("受理人", ""))
            ]
        if group:
            rows = [row for row in rows if self._snapshot(row)["分组"] == group]
        # 待回访在最前（超期优先），其次已回访，撤销与重复录入沉底；组内按最早受理时间倒序。
        order = {STATUS_PENDING: 0, STATUS_DONE: 1, STATUS_REVOKED: 2, STATUS_DUPLICATE: 2}
        rows.sort(
            key=lambda row: (
                order.get(str(row.get("status")), 3),
                0 if row.get("abnormal") else 1,
                -(_parse_time(row.get("首次受理时间")) or datetime.min).timestamp(),
            )
        )
        items = [self._snapshot(row) for row in rows]
        total = len(items)
        start = max(page - 1, 0) * size
        return items[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return self._snapshot(entry) if entry is not None else None

    # ---------- 登记与合并 ----------

    def _find_master(self, source: str, demand: str) -> dict[str, Any] | None:
        """按来源+诉求描述找仍有效的主记录；撤销/重复单不再作为合并目标。"""
        source_key = _normalize_text(source)
        demand_key = _normalize_text(demand)
        for row in store.rows(MODULE):
            if row.get("status") not in ACTIVE_STATUSES:
                continue
            if (
                _normalize_text(row.get("来源")) == source_key
                and _normalize_text(row.get("诉求描述")) == demand_key
            ):
                return row
        return None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, ""

        source = str(values["来源"]).strip()
        demand = str(values["诉求描述"]).strip()
        handler = str(values["受理人"]).strip()
        accepted_at = str(values.get("受理时间") or "").strip() or _now_text()

        # 同一投诉只能挂到一条主记录下：重复录入不新建单，只追加一次受理痕迹。
        master = self._find_master(source, demand)
        if master is not None:
            acceptances = master.setdefault("受理记录", [])
            acceptances.append({"时间": accepted_at, "受理人": handler, "来源": source})
            master["最新受理时间"] = accepted_at
            message = f"与主记录 {master.get('投诉单号')} 内容重复，已并入该投诉单，未新建记录"
            return self._snapshot(master), [], message

        rows = store.rows(MODULE)
        entry_id = max((int(row.get("id", 0)) for row in rows), default=0) + 1
        entry: dict[str, Any] = {
            "id": entry_id,
            "status": STATUS_PENDING,
            "pending": True,
            "abnormal": False,
            "投诉单号": f"COMP-{entry_id:04d}",
            "来源": source,
            "诉求描述": demand,
            "受理人": handler,
            "首次受理时间": accepted_at,
            "最新受理时间": accepted_at,
            "受理记录": [{"时间": accepted_at, "受理人": handler, "来源": source}],
            "回访记录": [],
        }
        rows.append(entry)
        return self._snapshot(entry), [], "投诉单已登记，进入待回访"

    def mark_duplicate(
        self, entry_id: int, master_id: int
    ) -> tuple[dict[str, Any] | None, str]:
        """把重复录入的单子并入主记录：重复单整条删除（含其回访记录，不允许残留）。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"投诉单 {entry_id} 不存在或已归档"
        if entry.get("status") not in ACTIVE_STATUSES:
            return None, f"投诉单 {entry_id} 已{entry.get('status')}，不能再标记重复"
        master = store.find(MODULE, master_id)
        if master is None or master.get("status") not in ACTIVE_STATUSES:
            return None, f"主记录 {master_id} 不存在或不是有效投诉单"
        if entry_id == master_id:
            return None, "不能把投诉单合并到自身"

        # 回访时限按最早一次受理时间算：保留两边更早的受理痕迹与受理时间。
        acceptances = master.setdefault("受理记录", [])
        acceptances.extend(entry.get("受理记录") or [])
        acceptances.sort(key=lambda item: _parse_time(item.get("时间")) or datetime.min)
        if acceptances:
            master["首次受理时间"] = acceptances[0]["时间"]
            master["最新受理时间"] = acceptances[-1]["时间"]

        # 历史回访按当时结论保留：重复单若已有回访，结论并入主记录而不是丢弃。
        visits = master.setdefault("回访记录", [])
        visits.extend(entry.get("回访记录") or [])
        visits.sort(key=lambda item: _parse_time(item.get("时间")) or datetime.min)

        if visits:
            master["status"] = STATUS_DONE
            master["pending"] = False
        # 删除重复单本体，连同其名下回访记录一起清掉，避免挂在两条记录下。
        store.rows(MODULE).remove(entry)
        return self._snapshot(master), f"投诉单已并入主记录 {master.get('投诉单号')}，原记录不再保留"

    # ---------- 回访与撤销 ----------

    def add_visit(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"投诉单 {entry_id} 不存在或已归档"
        if entry.get("status") not in ACTIVE_STATUSES:
            return None, f"投诉单{entry.get('status')}，不再接受回访登记"
        result = str(values.get("回访结果") or "").strip()
        if not result:
            return None, "请填写回访结果"
        visitor = str(values.get("回访人") or "").strip() or str(entry.get("受理人") or "")
        visited_at = str(values.get("回访时间") or "").strip() or _now_text()

        # 历史投诉按当时的回访结论保留：追加一条，而不是改掉上一次结论。
        visits = entry.setdefault("回访记录", [])
        visits.append({"结果": result, "时间": visited_at, "回访人": visitor})
        entry["status"] = STATUS_DONE
        entry["pending"] = False
        entry["abnormal"] = False
        return self._snapshot(entry), "回访结果已登记"

    def revoke(self, entry_id: int) -> tuple[dict[str, Any] | None, str]:
        """撤销投诉：撤销后不再需要回访，挂在单上的回访记录一并清掉，不留残。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"投诉单 {entry_id} 不存在或已归档"
        if entry.get("status") == STATUS_REVOKED:
            return None, "该投诉单已撤销，请勿重复操作"
        entry["status"] = STATUS_REVOKED
        entry["pending"] = False
        entry["abnormal"] = False
        entry["回访记录"] = []
        return self._snapshot(entry), "投诉单已撤销，相关回访记录已清理"
