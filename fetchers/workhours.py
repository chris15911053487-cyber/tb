"""获取任务的实际工时和计划工时。"""
from dataclasses import dataclass


@dataclass
class WorkHours:
    task_id: str
    actual_hours: float = 0.0
    planned_hours: float = 0.0


class WorkHoursFetcher:
    def __init__(self, client):
        self.client = client

    def fetch_for_task(self, task_id):
        actual = self._sum_hours(f"/worktime/list/task/{task_id}", "worktime")
        return WorkHours(
            task_id=task_id,
            actual_hours=actual,
        )

    def _sum_hours(self, path, field):
        try:
            total = 0.0
            for item in self.client.paginate(path):
                total += item.get(field, 0) / 3600000  # API 返回毫秒
            return total
        except Exception:
            return 0.0
