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
        # Step 1: 获取项目 ID 列表
        project_ids = list(self.client.paginate(
            "/v3/project/user-joined", page_size=page_size
        ))

        if not project_ids:
            return []

        # Step 2: 批量获取项目详情（每次最多 50 个）
        projects = []
        batch_size = 50
        for i in range(0, len(project_ids), batch_size):
            batch = project_ids[i:i + batch_size]
            ids_param = ",".join(batch)
            data = self.client.get(f"/v3/project/query", params={"projectIds": ids_param})
            for raw in data.get("result", []):
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
