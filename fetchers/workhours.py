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
        actual = self._sum_hours(f"/worktime/list/task/{task_id}", "workHours")
        planned = self._sum_hours(f"/plantime/list/task/{task_id}", "planHours")
        return WorkHours(
            task_id=task_id,
            actual_hours=actual,
            planned_hours=planned,
        )

    def _sum_hours(self, path, field):
        try:
            total = 0.0
            for item in self.client.paginate(path):
                total += item.get(field, 0)
            return total
        except Exception:
            return 0.0
