"""获取指定项目下的全部任务。"""
from dataclasses import dataclass


@dataclass
class Task:
    id: str
    project_id: str
    content: str
    is_done: bool = False
    executor_id: str = ""
    stage_id: str = ""


class TasksFetcher:
    def __init__(self, client):
        self.client = client

    def fetch_for_project(self, project_id, page_size=50):
        tasks = []
        for raw in self.client.paginate(
            f"/v3/project/{project_id}/task/query",
            page_size=page_size,
        ):
            task = Task(
                id=raw.get("taskId") or raw.get("_id") or raw.get("id", ""),
                project_id=raw.get("projectId") or raw.get("_projectId", project_id),
                content=raw.get("content", ""),
                is_done=raw.get("isDone", False),
                executor_id=raw.get("executorId") or raw.get("_executorId", ""),
                stage_id=raw.get("stageId") or raw.get("_stageId", ""),
            )
            tasks.append(task)
        return tasks
