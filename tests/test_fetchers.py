import json
import responses
import pytest
from auth import TeambitionAuth
from api_client import APIClient
from fetchers.projects import ProjectsFetcher, Project
from fetchers.stages import StagesFetcher, Stage


@pytest.fixture
def auth():
    a = TeambitionAuth(app_id="x", app_secret="y", org_id="z")
    a._token = "test-token"
    a._expires_at = float("inf")
    a._operator_id = "op-1"
    return a


@pytest.fixture
def client(auth):
    return APIClient(auth)


@responses.activate
def test_fetch_all_projects_single_page(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/project/query?pageSize=50",
        json={
            "result": [
                {"id": "p1", "name": "项目A", "description": "descA", "isArchived": False},
                {"id": "p2", "name": "项目B", "description": "", "isArchived": False},
            ],
            "nextPageToken": "",
        },
        status=200,
    )
    fetcher = ProjectsFetcher(client)
    projects = fetcher.fetch_all()
    assert len(projects) == 2
    assert projects[0].id == "p1"
    assert projects[0].name == "项目A"
    assert projects[1].id == "p2"


@responses.activate
def test_fetch_all_projects_excludes_archived_by_default(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/project/query?pageSize=50",
        json={
            "result": [
                {"id": "p1", "name": "活跃", "isArchived": False},
                {"id": "p2", "name": "已归档", "isArchived": True},
            ],
            "nextPageToken": "",
        },
        status=200,
    )
    fetcher = ProjectsFetcher(client)
    projects = fetcher.fetch_all()
    assert len(projects) == 1
    assert projects[0].id == "p1"


@responses.activate
def test_fetch_all_projects_include_archived(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/project/query?pageSize=50",
        json={
            "result": [
                {"id": "p1", "name": "活跃", "isArchived": False},
                {"id": "p2", "name": "已归档", "isArchived": True},
            ],
            "nextPageToken": "",
        },
        status=200,
    )
    fetcher = ProjectsFetcher(client)
    projects = fetcher.fetch_all(include_archived=True)
    assert len(projects) == 2


# --- StagesFetcher tests ---


@responses.activate
def test_fetch_stages_for_project(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/project/p1/stage/search?pageSize=50",
        json={
            "result": [
                {"id": "s1", "name": "待处理", "projectId": "p1"},
                {"id": "s2", "name": "进行中", "projectId": "p1"},
            ],
            "nextPageToken": "",
        },
        status=200,
    )
    fetcher = StagesFetcher(client)
    stages = fetcher.fetch_for_project("p1")
    assert len(stages) == 2
    assert stages[0].id == "s1"
    assert stages[0].name == "待处理"
    assert stages[0].project_id == "p1"


@responses.activate
def test_fetch_stages_empty(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/project/p-empty/stage/search?pageSize=50",
        json={"result": [], "nextPageToken": ""},
        status=200,
    )
    fetcher = StagesFetcher(client)
    stages = fetcher.fetch_for_project("p-empty")
    assert stages == []


@responses.activate
def test_fetch_tasklists_for_project(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/project/p1/tasklist/search?pageSize=50",
        json={
            "result": [
                {"id": "tl1", "title": "实施项目", "projectId": "p1"},
                {"id": "tl2", "title": "项目状况", "projectId": "p1"},
            ],
            "nextPageToken": "",
        },
        status=200,
    )
    fetcher = StagesFetcher(client)
    tasklist_map = fetcher.fetch_tasklists_for_project("p1")
    assert tasklist_map == {"tl1": "实施项目", "tl2": "项目状况"}


# --- TasksFetcher tests ---

from fetchers.tasks import TasksFetcher, Task


@responses.activate
def test_fetch_tasks_for_project(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/project/p1/task/query?pageSize=50",
        json={
            "result": [
                {
                    "_id": "t1",
                    "_projectId": "p1",
                    "content": "完成登录页面",
                    "isDone": False,
                    "_executorId": "u1",
                },
                {
                    "_id": "t2",
                    "_projectId": "p1",
                    "content": "修复导航Bug",
                    "isDone": True,
                    "_executorId": "u2",
                },
            ],
            "nextPageToken": "",
        },
        status=200,
    )
    fetcher = TasksFetcher(client)
    tasks = fetcher.fetch_for_project("p1")
    assert len(tasks) == 2
    assert tasks[0].id == "t1"
    assert tasks[0].content == "完成登录页面"
    assert tasks[0].is_done is False
    assert tasks[0].executor_id == "u1"
    assert tasks[1].is_done is True


@responses.activate
def test_fetch_tasks_empty_project(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/project/p-empty/task/query?pageSize=50",
        json={"result": [], "nextPageToken": ""},
        status=200,
    )
    fetcher = TasksFetcher(client)
    tasks = fetcher.fetch_for_project("p-empty")
    assert tasks == []


@responses.activate
def test_fetch_tasks_missing_executor(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/project/p1/task/query?pageSize=50",
        json={
            "result": [
                {"_id": "t1", "_projectId": "p1", "content": "无执行者任务", "isDone": False}
            ],
            "nextPageToken": "",
        },
        status=200,
    )
    fetcher = TasksFetcher(client)
    tasks = fetcher.fetch_for_project("p1")
    assert tasks[0].executor_id == ""


# --- WorkHoursFetcher tests ---

from fetchers.workhours import WorkHoursFetcher, WorkHours


@responses.activate
def test_fetch_work_hours_for_task(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/worktime/list/task/t1",
        json={
            "result": [
                {"worktime": 9000000, "date": "2026-05-01"},   # 2.5h  in ms
                {"worktime": 5400000, "date": "2026-05-02"},   # 1.5h in ms
            ],
            "nextPageToken": "",
        },
        status=200,
    )
    fetcher = WorkHoursFetcher(client)
    wh = fetcher.fetch_for_task("t1")
    assert wh.task_id == "t1"
    assert wh.actual_hours == 4.0  # 2.5 + 1.5
    assert wh.planned_hours == 0.0


@responses.activate
def test_fetch_work_hours_empty(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/worktime/list/task/t2",
        json={"result": [], "nextPageToken": ""},
        status=200,
    )
    fetcher = WorkHoursFetcher(client)
    wh = fetcher.fetch_for_task("t2")
    assert wh.actual_hours == 0.0
    assert wh.planned_hours == 0.0


@responses.activate
def test_fetch_work_hours_handles_api_error_gracefully(client):
    """工时 API 出错时返回 0，不阻断整体流程。"""
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/worktime/list/task/t3",
        json={"error": "not_found"},
        status=404,
    )
    fetcher = WorkHoursFetcher(client)
    wh = fetcher.fetch_for_task("t3")
    assert wh.actual_hours == 0.0
    assert wh.planned_hours == 0.0
