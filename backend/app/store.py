"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
"""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from app.seed import SEED_ROWS


class Store:
    def __init__(self) -> None:
        # 投诉单这类记录内嵌受理/回访历史列表，必须深拷贝，否则改动会串到示例数据常量上。
        self._tables: dict[str, list[dict[str, Any]]] = {
            name: deepcopy(rows) for name, rows in SEED_ROWS.items()
        }
        # 概览汇总前的刷新钩子：像「超期未回访」这种依赖当前时间的标记，
        # 先由各业务模块刷新成最新值，保证概览卡片和明细页读的是同一份数据。
        self._overview_hooks: list[Callable[[], None]] = []

    def on_overview(self, hook: Callable[[], None]) -> None:
        self._overview_hooks.append(hook)

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def overview(self) -> dict[str, object]:
        for hook in self._overview_hooks:
            hook()
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
