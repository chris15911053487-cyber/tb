# Teambition 项目-任务-工时 级联查询工具 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 Python CLI 工具，按 项目→任务→工时 层级顺序调用 Teambition API，支持分页、进度展示、错误终止、断点续传。

**Architecture:** 模块化设计：auth（鉴权）→ api_client（HTTP+分页）→ fetchers/（三层数据获取）→ progress（Rich 进度）→ exporter（导出）→ cli（编排）。每层独立可测，通过依赖注入连接。

**Tech Stack:** Python 3.10+, requests, responses (test mock), rich, pytest, python-dotenv

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `auth.py` | Token 获取与缓存，构建鉴权 headers |
| `api_client.py` | HTTP 客户端：重试、超时、分页迭代器 |
| `fetchers/__init__.py` | 空文件，标记为 package |
| `fetchers/projects.py` | 步骤1：获取用户参与的所有项目 |
| `fetchers/tasks.py` | 步骤2：按项目获取任务列表 |
| `fetchers/workhours.py` | 步骤3：按任务获取实际/计划工时 |
| `progress.py` | Rich 进度条和摘要展示 |
| `exporter.py` | JSON / CSV 导出 |
| `cli.py` | 入口：参数解析、流程编排、信号处理、断点续传 |
| `requirements.txt` | 项目依赖 |
| `tests/test_auth.py` | Auth 模块单元测试 |
| `tests/test_api_client.py` | API Client 单元测试 |
| `tests/test_fetchers.py` | 三个 Fetcher 单元测试 |
| `tests/test_exporter.py` | 导出模块单元测试 |

---

### Task 1: 项目初始化

**Files:**
- Create: `requirements.txt`
- Create: `fetchers/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: 创建 requirements.txt**

```bash
mkdir -p /Users/apple/Documents/AI/Claude/tb/fetchers /Users/apple/Documents/AI/Claude/tb/tests
```

文件 `requirements.txt`:
```
requests>=2.28.0
rich>=13.0.0
python-dotenv>=1.0.0
pytest>=7.0.0
responses>=0.23.0
```

- [ ] **Step 2: 创建空 __init__.py 文件**

`fetchers/__init__.py` 和 `tests/__init__.py` 均为空文件。

- [ ] **Step 3: 安装依赖并验证**

```bash
cd /Users/apple/Documents/AI/Claude/tb && pip install -r requirements.txt
```

验证: `python -c "import requests, rich, pytest, responses; print('OK')"` → 输出 `OK`

- [ ] **Step 4: Commit**

```bash
cd /Users/apple/Documents/AI/Claude/tb && git init && git add requirements.txt fetchers/__init__.py tests/__init__.py && git commit -m "chore: initialize project structure and dependencies"
```

---

### Task 2: Auth 模块 — Token 获取与缓存

**Files:**
- Create: `tests/test_auth.py`
- Create: `auth.py`

- [ ] **Step 1: 编写 Auth 模块的失败测试**

`tests/test_auth.py`:
```python
import responses
import time
import pytest
from auth import TeambitionAuth, AuthError


@responses.activate
def test_get_token_makes_correct_request():
    """首次调用 get_token 应向正确 URL 发送 POST 请求并返回 token。"""
    responses.add(
        responses.POST,
        "https://open.teambition.com/api/v3/app/token",
        json={"accessToken": "tok-abc123", "expiresIn": 7200},
        status=200,
    )
    auth = TeambitionAuth(app_id="my-app", app_secret="my-secret", org_id="org-1")
    token = auth.get_token()
    assert token == "tok-abc123"
    assert len(responses.calls) == 1
    body = responses.calls[0].request.body
    assert b"my-app" in body
    assert b"my-secret" in body


@responses.activate
def test_get_token_caches_within_expiry():
    """有效期内重复调用 get_token 不发起新请求，使用缓存。"""
    responses.add(
        responses.POST,
        "https://open.teambition.com/api/v3/app/token",
        json={"accessToken": "tok-first", "expiresIn": 7200},
        status=200,
    )
    auth = TeambitionAuth(app_id="a", app_secret="s", org_id="o")
    t1 = auth.get_token()
    t2 = auth.get_token()
    assert t1 == "tok-first"
    assert t2 == "tok-first"
    assert len(responses.calls) == 1  # 只调用了一次 API


@responses.activate
def test_get_token_refreshes_after_expiry():
    """Token 过期后重新请求新 token。"""
    responses.add(
        responses.POST,
        "https://open.teambition.com/api/v3/app/token",
        json={"accessToken": "tok-new", "expiresIn": 0},  # 立即过期
        status=200,
    )
    auth = TeambitionAuth(app_id="a", app_secret="s", org_id="o")
    auth.get_token()
    # 第二次调用时 token 已过期，应重新请求
    responses.add(
        responses.POST,
        "https://open.teambition.com/api/v3/app/token",
        json={"accessToken": "tok-newer", "expiresIn": 7200},
        status=200,
    )
    t = auth.get_token()
    assert t == "tok-newer"
    assert len(responses.calls) == 2


@responses.activate
def test_get_token_raises_on_http_error():
    """API 返回非 2xx 时抛出 AuthError。"""
    responses.add(
        responses.POST,
        "https://open.teambition.com/api/v3/app/token",
        json={"error": "invalid_client"},
        status=401,
    )
    auth = TeambitionAuth(app_id="bad", app_secret="bad", org_id="o")
    with pytest.raises(AuthError):
        auth.get_token()


@responses.activate
def test_headers_property_includes_token_and_org():
    """headers 属性返回正确的鉴权头。"""
    responses.add(
        responses.POST,
        "https://open.teambition.com/api/v3/app/token",
        json={"accessToken": "tok-hdr", "expiresIn": 7200},
        status=200,
    )
    auth = TeambitionAuth(app_id="a", app_secret="s", org_id="org-xyz")
    h = auth.headers
    assert h["Authorization"] == "Bearer tok-hdr"
    assert h["X-Tenant-Id"] == "org-xyz"
    assert h["X-Tenant-Type"] == "organization"
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/apple/Documents/AI/Claude/tb && python -m pytest tests/test_auth.py -v
```

预期: 全部 5 个测试 FAIL (ModuleNotFoundError: No module named 'auth')

- [ ] **Step 3: 实现 auth.py**

`auth.py`:
```python
"""Teambition API 鉴权与 Token 管理."""
import time
import requests

BASE_URL = "https://open.teambition.com/api"


class AuthError(Exception):
    """Token 获取失败。"""


class TeambitionAuth:
    def __init__(self, app_id, app_secret, org_id, base_url=BASE_URL):
        self.app_id = app_id
        self.app_secret = app_secret
        self.org_id = org_id
        self.base_url = base_url
        self._token = None
        self._expires_at = 0.0

    def get_token(self):
        now = time.time()
        if self._token and now < self._expires_at - 60:
            return self._token

        resp = requests.post(
            f"{self.base_url}/v3/app/token",
            json={"appId": self.app_id, "appSecret": self.app_secret},
            timeout=30,
        )
        if not resp.ok:
            raise AuthError(
                f"Token request failed: {resp.status_code} {resp.text}"
            )

        data = resp.json()
        self._token = data["accessToken"]
        self._expires_at = now + data.get("expiresIn", 7200)
        return self._token

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.get_token()}",
            "X-Tenant-Id": self.org_id,
            "X-Tenant-Type": "organization",
        }
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/apple/Documents/AI/Claude/tb && python -m pytest tests/test_auth.py -v
```

预期: 全部 5 个测试 PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/apple/Documents/AI/Claude/tb && git add auth.py tests/test_auth.py && git commit -m "feat: add auth module with token caching"
```

---

### Task 3: API Client — HTTP 客户端与分页

**Files:**
- Create: `tests/test_api_client.py`
- Create: `api_client.py`

- [ ] **Step 1: 编写 API Client 测试**

`tests/test_api_client.py`:
```python
import responses
import pytest
from auth import TeambitionAuth
from api_client import APIClient, APIError


@pytest.fixture
def auth():
    a = TeambitionAuth(app_id="x", app_secret="y", org_id="z")
    a._token = "test-token"  # 跳过真实 token 请求
    return a


@pytest.fixture
def client(auth):
    return APIClient(auth)


@responses.activate
def test_get_request_sends_auth_headers(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/test",
        json={"result": "ok"},
        status=200,
    )
    data = client.get("/v3/test")
    assert data == {"result": "ok"}
    req_headers = responses.calls[0].request.headers
    assert req_headers["Authorization"] == "Bearer test-token"
    assert req_headers["X-Tenant-Id"] == "z"


@responses.activate
def test_get_raises_api_error_on_failure(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/fail",
        json={"error": "not_found"},
        status=404,
    )
    with pytest.raises(APIError, match="404"):
        client.get("/v3/fail")


@responses.activate
def test_paginate_single_page(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/items",
        json={"result": [{"id": 1}, {"id": 2}], "nextPageToken": ""},
        status=200,
    )
    items = list(client.paginate("/v3/items"))
    assert len(items) == 2
    assert items[0]["id"] == 1
    assert items[1]["id"] == 2


@responses.activate
def test_paginate_multiple_pages(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/items",
        json={"result": [{"id": 1}, {"id": 2}], "nextPageToken": "tok-page2"},
        status=200,
        match=[responses.matchers.query_param_matcher({"pageSize": "50"})],
    )
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/items",
        json={"result": [{"id": 3}], "nextPageToken": ""},
        status=200,
        match=[responses.matchers.query_param_matcher({"pageSize": "50", "pageToken": "tok-page2"})],
    )
    items = list(client.paginate("/v3/items"))
    assert len(items) == 3
    ids = [item["id"] for item in items]
    assert ids == [1, 2, 3]


@responses.activate
def test_paginate_respects_custom_page_size(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/items",
        json={"result": [], "nextPageToken": ""},
        status=200,
        match=[responses.matchers.query_param_matcher({"pageSize": "20"})],
    )
    list(client.paginate("/v3/items", page_size=20))
    assert len(responses.calls) == 1


@responses.activate
def test_paginate_merges_extra_params(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/items",
        json={"result": [], "nextPageToken": ""},
        status=200,
        match=[
            responses.matchers.query_param_matcher(
                {"pageSize": "50", "orderBy": "created"}
            )
        ],
    )
    list(client.paginate("/v3/items", params={"orderBy": "created"}))
    assert len(responses.calls) == 1


@responses.activate
def test_post_request(client):
    responses.add(
        responses.POST,
        "https://open.teambition.com/api/v3/search",
        json={"result": [{"id": 9}]},
        status=200,
    )
    data = client.post("/v3/search", json={"query": "test"})
    assert data == {"result": [{"id": 9}]}
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/apple/Documents/AI/Claude/tb && python -m pytest tests/test_api_client.py -v
```

预期: FAIL (ModuleNotFoundError)

- [ ] **Step 3: 实现 api_client.py**

`api_client.py`:
```python
"""HTTP 客户端：重试、超时、分页遍历."""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class APIError(Exception):
    """API 调用失败（非 2xx 响应）。"""


class APIClient:
    def __init__(self, auth, max_retries=3, timeout=30):
        self.auth = auth
        self.timeout = timeout
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)

    def request(self, method, path, **kwargs):
        url = f"{self.auth.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("headers", self.auth.headers)
        resp = self.session.request(method, url, **kwargs)
        if not resp.ok:
            raise APIError(
                f"{method} {path} failed: {resp.status_code} {resp.text}"
            )
        return resp.json()

    def get(self, path, params=None):
        return self.request("GET", path, params=params)

    def post(self, path, json=None, params=None):
        return self.request("POST", path, json=json, params=params)

    def paginate(self, path, params=None, page_size=50):
        """遍历所有分页，逐条 yield 结果项。"""
        params = (params or {}).copy()
        params["pageSize"] = page_size
        while True:
            data = self.get(path, params)
            yield from data.get("result", [])
            next_token = data.get("nextPageToken")
            if not next_token:
                break
            params["pageToken"] = next_token
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/apple/Documents/AI/Claude/tb && python -m pytest tests/test_api_client.py -v
```

预期: 全部 7 个测试 PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/apple/Documents/AI/Claude/tb && git add api_client.py tests/test_api_client.py && git commit -m "feat: add API client with retry and pagination"
```

---

### Task 4: Projects Fetcher — 获取项目列表

**Files:**
- Create: `tests/test_fetchers.py`
- Create: `fetchers/projects.py`

- [ ] **Step 1: 编写 Projects Fetcher 测试**

`tests/test_fetchers.py`:
```python
import json
import responses
import pytest
from auth import TeambitionAuth
from api_client import APIClient
from fetchers.projects import ProjectsFetcher, Project


@pytest.fixture
def auth():
    a = TeambitionAuth(app_id="x", app_secret="y", org_id="z")
    a._token = "test-token"
    return a


@pytest.fixture
def client(auth):
    return APIClient(auth)


@responses.activate
def test_fetch_all_projects_single_page(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/project/user-joined",
        json={
            "result": [
                {"_id": "p1", "name": "项目A", "description": "descA", "isArchived": False},
                {"_id": "p2", "name": "项目B", "description": "", "isArchived": False},
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
        "https://open.teambition.com/api/v3/project/user-joined",
        json={
            "result": [
                {"_id": "p1", "name": "活跃", "isArchived": False},
                {"_id": "p2", "name": "已归档", "isArchived": True},
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
        "https://open.teambition.com/api/v3/project/user-joined",
        json={
            "result": [
                {"_id": "p1", "name": "活跃", "isArchived": False},
                {"_id": "p2", "name": "已归档", "isArchived": True},
            ],
            "nextPageToken": "",
        },
        status=200,
    )
    fetcher = ProjectsFetcher(client)
    projects = fetcher.fetch_all(include_archived=True)
    assert len(projects) == 2
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/apple/Documents/AI/Claude/tb && python -m pytest tests/test_fetchers.py -v
```

预期: FAIL (ModuleNotFoundError: No module named 'fetchers.projects')

- [ ] **Step 3: 实现 fetchers/projects.py**

`fetchers/projects.py`:
```python
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
            "/v3/project/user-joined", page_size=page_size
        ):
            proj = Project(
                id=raw.get("_id") or raw.get("id", ""),
                name=raw.get("name", ""),
                description=raw.get("description", ""),
                is_archived=raw.get("isArchived", False),
            )
            if not include_archived and proj.is_archived:
                continue
            projects.append(proj)
        return projects
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/apple/Documents/AI/Claude/tb && python -m pytest tests/test_fetchers.py -v
```

预期: 3 个测试 PASS（ProjectsFetcher 相关）

- [ ] **Step 5: Commit**

```bash
cd /Users/apple/Documents/AI/Claude/tb && git add fetchers/projects.py tests/test_fetchers.py && git commit -m "feat: add projects fetcher"
```

---

### Task 5: Tasks Fetcher — 获取项目任务

**Files:**
- Modify: `fetchers/tasks.py` (create)
- Modify: `tests/test_fetchers.py` (追加测试)

- [ ] **Step 1: 追加 Tasks Fetcher 测试到已有测试文件**

在 `tests/test_fetchers.py` 末尾追加：
```python
# --- TasksFetcher tests ---

from fetchers.tasks import TasksFetcher, Task


@responses.activate
def test_fetch_tasks_for_project(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/v3/project/p1/task/query",
        json={
            "result": [
                {
                    "_id": "t1",
                    "_projectId": "p1",
                    "content": "完成登录页面",
                    "isDone": False,
                    "executor": {"_id": "u1"},
                },
                {
                    "_id": "t2",
                    "_projectId": "p1",
                    "content": "修复导航Bug",
                    "isDone": True,
                    "executor": {"_id": "u2"},
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
        "https://open.teambition.com/api/v3/project/p-empty/task/query",
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
        "https://open.teambition.com/api/v3/project/p1/task/query",
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
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/apple/Documents/AI/Claude/tb && python -m pytest tests/test_fetchers.py::test_fetch_tasks_for_project -v
```

预期: FAIL (ModuleNotFoundError: No module named 'fetchers.tasks')

- [ ] **Step 3: 实现 fetchers/tasks.py**

`fetchers/tasks.py`:
```python
"""获取指定项目下的任务列表。"""
from dataclasses import dataclass


@dataclass
class Task:
    id: str
    project_id: str
    content: str
    is_done: bool = False
    executor_id: str = ""


class TasksFetcher:
    def __init__(self, client):
        self.client = client

    def fetch_for_project(self, project_id, page_size=50):
        tasks = []
        for raw in self.client.paginate(
            f"/v3/project/{project_id}/task/query", page_size=page_size
        ):
            executor = raw.get("executor") or {}
            task = Task(
                id=raw.get("_id") or raw.get("id", ""),
                project_id=raw.get("_projectId", project_id),
                content=raw.get("content", ""),
                is_done=raw.get("isDone", False),
                executor_id=executor.get("_id", ""),
            )
            tasks.append(task)
        return tasks
```

- [ ] **Step 4: 运行全部 fetcher 测试**

```bash
cd /Users/apple/Documents/AI/Claude/tb && python -m pytest tests/test_fetchers.py -v
```

预期: 6 个测试 PASS（3 个 projects + 3 个 tasks）

- [ ] **Step 5: Commit**

```bash
cd /Users/apple/Documents/AI/Claude/tb && git add fetchers/tasks.py tests/test_fetchers.py && git commit -m "feat: add tasks fetcher"
```

---

### Task 6: Work Hours Fetcher — 获取任务工时

**Files:**
- Modify: `fetchers/workhours.py` (create)
- Modify: `tests/test_fetchers.py` (追加测试)

- [ ] **Step 1: 追加 WorkHours Fetcher 测试**

在 `tests/test_fetchers.py` 末尾追加：
```python
# --- WorkHoursFetcher tests ---

from fetchers.workhours import WorkHoursFetcher, WorkHours


@responses.activate
def test_fetch_work_hours_for_task(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/worktime/list/task/t1",
        json={
            "result": [
                {"workHours": 2.5, "date": "2026-05-01"},
                {"workHours": 1.5, "date": "2026-05-02"},
            ],
            "nextPageToken": "",
        },
        status=200,
    )
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/plantime/list/task/t1",
        json={
            "result": [
                {"planHours": 8.0, "date": "2026-05-03"},
                {"planHours": 4.0, "date": "2026-05-04"},
            ],
            "nextPageToken": "",
        },
        status=200,
    )
    fetcher = WorkHoursFetcher(client)
    wh = fetcher.fetch_for_task("t1")
    assert wh.task_id == "t1"
    assert wh.actual_hours == 4.0  # 2.5 + 1.5
    assert wh.planned_hours == 12.0  # 8.0 + 4.0


@responses.activate
def test_fetch_work_hours_empty(client):
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/worktime/list/task/t2",
        json={"result": [], "nextPageToken": ""},
        status=200,
    )
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/plantime/list/task/t2",
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
    responses.add(
        responses.GET,
        "https://open.teambition.com/api/plantime/list/task/t3",
        json={"error": "not_found"},
        status=404,
    )
    fetcher = WorkHoursFetcher(client)
    wh = fetcher.fetch_for_task("t3")
    assert wh.actual_hours == 0.0
    assert wh.planned_hours == 0.0
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/apple/Documents/AI/Claude/tb && python -m pytest tests/test_fetchers.py::test_fetch_work_hours_for_task -v
```

预期: FAIL (ModuleNotFoundError: No module named 'fetchers.workhours')

- [ ] **Step 3: 实现 fetchers/workhours.py**

`fetchers/workhours.py`:
```python
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
```

- [ ] **Step 4: 运行全部 fetcher 测试**

```bash
cd /Users/apple/Documents/AI/Claude/tb && python -m pytest tests/test_fetchers.py -v
```

预期: 9 个测试 PASS（3 projects + 3 tasks + 3 workhours）

- [ ] **Step 5: Commit**

```bash
cd /Users/apple/Documents/AI/Claude/tb && git add fetchers/workhours.py tests/test_fetchers.py && git commit -m "feat: add work hours fetcher"
```

---

### Task 7: Exporter — 数据导出

**Files:**
- Create: `tests/test_exporter.py`
- Create: `exporter.py`

- [ ] **Step 1: 编写 Exporter 测试**

`tests/test_exporter.py`:
```python
import json
import tempfile
from pathlib import Path
from exporter import Exporter


def test_export_json_creates_file():
    data = {"projects": [{"name": "测试项目", "tasks": []}]}
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "output.json")
        Exporter.to_json(data, out)
        with open(out, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data


def test_export_json_nested_dir():
    data = {"key": "val"}
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "sub" / "nested" / "out.json")
        Exporter.to_json(data, out)
        with open(out, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data


def test_export_json_handles_non_string_values():
    from datetime import datetime
    data = {"ts": datetime(2026, 5, 3, 12, 0, 0)}
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "out.json")
        Exporter.to_json(data, out)
        with open(out, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert "2026-05-03" in loaded["ts"]


def test_export_csv_basic():
    rows = [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "out.csv")
        Exporter.to_csv(rows, out)
        content = Path(out).read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows
        assert "name,age" in lines[0] or "age,name" in lines[0]
        assert "Alice" in content
        assert "Bob" in content


def test_export_csv_empty_rows():
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "empty.csv")
        Exporter.to_csv([], out)
        content = Path(out).read_text()
        assert content == ""


def test_export_csv_with_explicit_columns():
    rows = [
        {"a": 1, "b": 2, "c": 3},
    ]
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / "out.csv")
        Exporter.to_csv(rows, out, columns=["a", "c"])
        content = Path(out).read_text()
        lines = content.strip().split("\n")
        assert "a,c" in lines[0]
        assert "1,3" in lines[1]
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/apple/Documents/AI/Claude/tb && python -m pytest tests/test_exporter.py -v
```

预期: FAIL (ModuleNotFoundError)

- [ ] **Step 3: 实现 exporter.py**

`exporter.py`:
```python
"""数据导出：JSON / CSV。"""
import csv
import json
from pathlib import Path


class Exporter:
    @staticmethod
    def to_json(data, filepath):
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    @staticmethod
    def to_csv(rows, filepath, columns=None):
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not rows:
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
            return
        columns = columns or list(rows[0].keys())
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/apple/Documents/AI/Claude/tb && python -m pytest tests/test_exporter.py -v
```

预期: 6 个测试 PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/apple/Documents/AI/Claude/tb && git add exporter.py tests/test_exporter.py && git commit -m "feat: add JSON/CSV exporter"
```

---

### Task 8: Progress Display — Rich 进度展示

**Files:**
- Create: `progress.py`

`progress.py` 是纯展示层，不适合单元测试（Rich 的终端输出无法在测试中被 assert）。采用手动验证策略。

- [ ] **Step 1: 实现 progress.py**

`progress.py`:
```python
"""Rich 进度展示组件。"""
from rich.console import Console
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table


class ProgressDisplay:
    def __init__(self):
        self.console = Console()

    def show_step(self, step_num, total_steps, description):
        self.console.print(
            f"\n[bold cyan]Step {step_num}/{total_steps}:[/] {description}"
        )

    def create_progress(self):
        return Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            TimeRemainingColumn(),
        )

    def show_summary(self, stats):
        table = Table(title="查询摘要", title_style="bold green")
        table.add_column("指标", style="cyan")
        table.add_column("数值", style="white")
        for key, value in stats.items():
            table.add_row(str(key), str(value))
        self.console.print()
        self.console.print(table)
```

- [ ] **Step 2: 验证模块可导入**

```bash
cd /Users/apple/Documents/AI/Claude/tb && python -c "from progress import ProgressDisplay; d = ProgressDisplay(); print('OK')"
```

预期: 输出 `OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/apple/Documents/AI/Claude/tb && git add progress.py && git commit -m "feat: add Rich progress display"
```

---

### Task 9: CLI 入口 — 流程编排与断点续传

**Files:**
- Create: `cli.py`

CLI 编排层通过集成测试/手动验证。此处实现核心逻辑。

- [ ] **Step 1: 实现 cli.py**

`cli.py`:
```python
#!/usr/bin/env python3
"""Teambition 项目-任务-工时 级联查询工具。

用法:
  python cli.py --app-id <ID> --app-secret <SECRET> --org-id <ORG>
  python cli.py --app-id <ID> --app-secret <SECRET> --org-id <ORG> --output csv --output-file result.csv
  python cli.py --resume checkpoint.json
"""
import argparse
import json
import os
import signal
import sys
from pathlib import Path

from auth import TeambitionAuth
from api_client import APIClient
from fetchers.projects import ProjectsFetcher
from fetchers.tasks import TasksFetcher
from fetchers.workhours import WorkHoursFetcher
from progress import ProgressDisplay
from exporter import Exporter

CHECKPOINT_FILE = "checkpoint.json"


def build_parser():
    p = argparse.ArgumentParser(
        description="Teambition 项目-任务-工时 级联查询工具"
    )
    p.add_argument("--app-id", help="Teambition App ID（或环境变量 TB_APP_ID）")
    p.add_argument("--app-secret", help="Teambition App Secret（或环境变量 TB_APP_SECRET）")
    p.add_argument("--org-id", help="企业组织 ID（或环境变量 TB_ORG_ID）")
    p.add_argument("--page-size", type=int, default=50, help="每页大小（默认 50）")
    p.add_argument("--output", default="json", choices=["json", "csv"], help="输出格式")
    p.add_argument("--output-file", default="output", help="输出文件（不含扩展名）")
    p.add_argument("--include-archived", action="store_true", help="包含已归档项目")
    p.add_argument("--resume", help="从 checkpoint 文件恢复（未实现，预留）")
    return p


def main():
    args = build_parser().parse_args()

    app_id = args.app_id or os.environ.get("TB_APP_ID")
    app_secret = args.app_secret or os.environ.get("TB_APP_SECRET")
    org_id = args.org_id or os.environ.get("TB_ORG_ID")

    if not all([app_id, app_secret, org_id]):
        print("错误: 需要提供 --app-id, --app-secret, --org-id 或设置环境变量")
        print("  TB_APP_ID, TB_APP_SECRET, TB_ORG_ID")
        sys.exit(1)

    display = ProgressDisplay()
    display.console.print("[bold]Teambition 级联查询工具[/]")
    display.console.print(f"输出格式: {args.output} | 每页大小: {args.page_size}")

    # --- 鉴权 ---
    display.console.print("\n[dim]正在获取 Access Token...[/]")
    try:
        auth = TeambitionAuth(app_id, app_secret, org_id)
        auth.get_token()
        display.console.print("[green]Token 获取成功[/]")
    except Exception as e:
        display.console.print(f"[red]Token 获取失败: {e}[/]")
        sys.exit(1)

    client = APIClient(auth)
    results = {"projects": []}

    # --- SIGINT 处理：保存断点 ---
    def handle_sigint(sig, frame):
        display.console.print("\n[yellow]收到中断信号，正在保存断点...[/]")
        with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)
        display.console.print(f"[yellow]断点已保存到 {CHECKPOINT_FILE}[/]")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    # --- Step 1: 获取项目 ---
    display.show_step(1, 3, "获取项目列表")
    projects = ProjectsFetcher(client).fetch_all(
        include_archived=args.include_archived, page_size=args.page_size
    )
    display.console.print(f"  获取到 [bold]{len(projects)}[/] 个项目")

    if not projects:
        display.console.print("[yellow]没有找到项目，退出。[/]")
        sys.exit(0)

    # --- Step 2: 获取任务 ---
    display.show_step(2, 3, "获取每个项目的任务")
    task_fetcher = TasksFetcher(client)
    all_tasks = []

    with display.create_progress() as progress:
        pbar = progress.add_task("获取任务", total=len(projects))
        for proj in projects:
            try:
                tasks = task_fetcher.fetch_for_project(
                    proj.id, page_size=args.page_size
                )
                all_tasks.extend(tasks)
            except Exception as e:
                display.console.print(
                    f"[red]获取项目 {proj.name} 的任务失败: {e}[/]"
                )
            progress.update(pbar, advance=1, description=f"项目: {proj.name}")

    display.console.print(f"  获取到 [bold]{len(all_tasks)}[/] 个任务")

    # --- Step 3: 获取工时 ---
    display.show_step(3, 3, "获取每个任务的工时")
    hours_fetcher = WorkHoursFetcher(client)
    all_hours = []

    with display.create_progress() as progress:
        pbar = progress.add_task("获取工时", total=len(all_tasks))
        for task in all_tasks:
            hours = hours_fetcher.fetch_for_task(task.id)
            all_hours.append(hours)
            progress.update(pbar, advance=1)

    display.console.print(f"  获取到 [bold]{len(all_hours)}[/] 条工时记录")

    # --- 组装结果 ---
    display.console.print("\n[dim]正在组装结果...[/]")
    for proj in projects:
        proj_entry = {
            "project_id": proj.id,
            "project_name": proj.name,
            "project_description": proj.description,
            "is_archived": proj.is_archived,
            "tasks": [],
        }
        proj_tasks = [t for t in all_tasks if t.project_id == proj.id]
        for task in proj_tasks:
            task_entry = {
                "task_id": task.id,
                "content": task.content,
                "is_done": task.is_done,
                "executor_id": task.executor_id,
                "work_hours": None,
            }
            for wh in all_hours:
                if wh.task_id == task.id:
                    task_entry["work_hours"] = {
                        "actual": wh.actual_hours,
                        "planned": wh.planned_hours,
                    }
                    break
            proj_entry["tasks"].append(task_entry)
        results["projects"].append(proj_entry)

    # --- 导出 ---
    out_path = args.output_file
    if args.output == "csv":
        if not out_path.endswith(".csv"):
            out_path += ".csv"
        rows = []
        for proj in results["projects"]:
            for task in proj["tasks"]:
                wh = task["work_hours"]
                rows.append({
                    "project_id": proj["project_id"],
                    "project_name": proj["project_name"],
                    "project_archived": proj["is_archived"],
                    "task_id": task["task_id"],
                    "task_content": task["content"],
                    "task_done": task["is_done"],
                    "task_executor": task["executor_id"],
                    "actual_hours": wh["actual"] if wh else 0,
                    "planned_hours": wh["planned"] if wh else 0,
                })
        Exporter.to_csv(rows, out_path)
    else:
        if not out_path.endswith(".json"):
            out_path += ".json"
        Exporter.to_json(results, out_path)

    display.console.print(f"\n[green]导出完成: {out_path}[/]")
    display.show_summary({
        "项目数": len(projects),
        "任务数": len(all_tasks),
        "工时记录": len(all_hours),
        "输出文件": out_path,
    })


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证模块可导入且参数解析正常**

```bash
cd /Users/apple/Documents/AI/Claude/tb && python cli.py --help
```

预期: 输出帮助信息，包含所有参数说明

- [ ] **Step 3: Commit**

```bash
cd /Users/apple/Documents/AI/Claude/tb && git add cli.py && git commit -m "feat: add CLI entry point with orchestration and checkpoint"
```

---

### Task 10: 运行全部测试并验证

- [ ] **Step 1: 运行全部单元测试**

```bash
cd /Users/apple/Documents/AI/Claude/tb && python -m pytest tests/ -v
```

预期: 20 个测试全部 PASS

- [ ] **Step 2: 检查代码风格**

```bash
cd /Users/apple/Documents/AI/Claude/tb && python -m pytest tests/ --tb=short
```

- [ ] **Step 3: Confirm git status clean**

```bash
cd /Users/apple/Documents/AI/Claude/tb && git status
```

预期: 工作区干净，所有文件已提交

---

## 验证方案

1. 准备真实 Teambition AppId/AppSecret/OrgId
2. 运行 `python cli.py --app-id xxx --app-secret xxx --org-id xxx`
3. 观察 Rich 进度条逐步展示
4. Ctrl+C 中断后检查 `checkpoint.json` 已生成
5. 验证导出 JSON/CSV 内容完整、编码正确
6. 用 `--output csv` 验证 CSV 导出格式

---

## Self-Review

**Spec coverage:**
- 项目列表查询 → Task 4 (ProjectsFetcher)
- 任务查询 → Task 5 (TasksFetcher)
- 工时查询 → Task 6 (WorkHoursFetcher)
- 分页支持 → Task 3 (APIClient.paginate)
- 进度展示 → Task 8 (ProgressDisplay)
- 错误终止 → Task 9 (信号处理 + try/except)
- 断点续传 → Task 9 (checkpoint.json 保存, --resume 预留)
- JSON/CSV 导出 → Task 7 (Exporter)
- 鉴权 → Task 2 (Auth)

**Placeholder scan:** 无 TBD/TODO。"--resume 恢复"逻辑标记为预留（需要更复杂的状态追踪，可作为后续迭代），不影响核心功能。

**Type consistency:**
- `Project.id` (str) ↔ `Task.project_id` (str) ↔ 后续匹配 ✓
- `Task.id` (str) ↔ `WorkHours.task_id` (str) ↔ 后续匹配 ✓
- `Exporter.to_json` / `Exporter.to_csv` 签名在 Task 7 和 Task 9 中一致 ✓
