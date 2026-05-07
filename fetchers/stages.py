"""获取项目下的任务列表（Stage/看板列）。"""
from dataclasses import dataclass


@dataclass
class Stage:
    id: str
    name: str
    project_id: str


class StagesFetcher:
    def __init__(self, client):
        self.client = client

    def fetch_for_project(self, project_id, page_size=50):
        stages = []
        for raw in self.client.paginate(
            f"/v3/project/{project_id}/stage/search",
            page_size=page_size,
        ):
            stage = Stage(
                id=raw.get("id", ""),
                name=raw.get("name", ""),
                project_id=raw.get("projectId", project_id),
            )
            stages.append(stage)
        return stages

    def fetch_tasklists_for_project(self, project_id, page_size=50):
        """获取项目下的任务分组（tasklist），返回 id->title 映射。"""
        tasklist_map = {}
        for raw in self.client.paginate(
            f"/v3/project/{project_id}/tasklist/search",
            page_size=page_size,
        ):
            tasklist_map[raw.get("id", "")] = raw.get("title", "")
        return tasklist_map
