"""获取用户参与的项目列表。"""
from dataclasses import dataclass, field


@dataclass
class Project:
    id: str
    name: str
    description: str = ""
    is_archived: bool = False


class ProjectsFetcher:
    def __init__(self, client):
        self.client = client

    def fetch_all(self, include_archived=False, page_size=50):
        projects = []
        for raw in self.client.paginate(
            "/v3/project/query", page_size=page_size
        ):
            proj = Project(
                id=raw.get("id", ""),
                name=raw.get("name", ""),
                description=raw.get("description", ""),
                is_archived=raw.get("isArchived", False),
            )
            if not include_archived and proj.is_archived:
                continue
            projects.append(proj)
        return projects
