"""FastAPI Web 服务器：前端页面 + 分步查询 API + SSE 进度推送。"""
import asyncio
import json
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Request, Form, HTTPException, Query
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates

from auth import TeambitionAuth, AuthError
from api_client import APIClient
from engine import QueryEngine, QueryCancelled, assemble
from exporter import Exporter

app = FastAPI(title="Teambition 查询工具")
templates = Jinja2Templates(directory="templates")

query_store: dict[str, "QueryState"] = {}


class QueryState:
    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.projects = []
        self.stages = []
        self.tasklist_map = {}
        self.tasks = []
        self.work_hours = []
        self.results = None
        self.error = None
        self.steps_done = 0
        self.cancelled = False
        self.token_pushed = False


def _get_state(query_id: str) -> QueryState:
    state = query_store.get(query_id)
    if not state:
        raise HTTPException(status_code=404, detail="查询不存在")
    return state


def _push_event(loop, query_id, type_, **kwargs):
    """线程安全地将 SSE 事件推入查询的队列。"""
    state = query_store[query_id]
    asyncio.run_coroutine_threadsafe(
        state.queue.put({"type": type_, **kwargs}), loop
    )


_API_NAMES = {
    "/v3/project/query": "获取项目列表",
    "/tasklist/search": "获取任务列表(Stage)",
    "/task/query": "获取任务",
    "/worktime/list/task/": "获取实际工时",
    "/org/owners": "获取企业拥有者",
    "/appToken": "获取 Access Token",
}


def _api_name(path):
    for prefix, name in _API_NAMES.items():
        if prefix in path:
            return name
    return path


def _make_client(loop, query_id):
    """创建带 API 日志回调的 APIClient。"""
    state = query_store[query_id]
    auth = TeambitionAuth(state.app_id, state.app_secret, state.org_id)
    token = auth.get_token()

    if not state.token_pushed:
        state.token_pushed = True
        _push_event(loop, query_id, "token_info", token=token)
        # 将 /appToken 请求也写入 API 日志
        _push_event(loop, query_id, "api_log",
                    name="获取 Access Token",
                    method="POST", path="/appToken",
                    url=f"{auth.base_url}/appToken",
                    req_params=None,
                    req_body={"appId": state.app_id, "appSecret": "***"},
                    req_headers={"Content-Type": "application/json"},
                    success=True,
                    status_code=200, api_code=0, error="")

    def log_callback(method, path, url, req_params, req_body, req_headers, status_code, api_code, error):
        success = (api_code in (0, 200) and status_code < 400)
        _push_event(loop, query_id, "api_log",
                    name=_api_name(path),
                    method=method, path=path, url=url,
                    req_params=req_params, req_body=req_body, req_headers=req_headers,
                    success=success,
                    status_code=status_code, api_code=api_code, error=error)

    return APIClient(auth, log_callback=log_callback)


def _run_step(loop, query_id, step_fn, *args):
    """在线程中运行单个步骤，通过 SSE 推送事件。loop 必须是主线程的事件循环。"""
    state = query_store[query_id]

    def push(type_, **kwargs):
        _push_event(loop, query_id, type_, **kwargs)

    try:
        result = step_fn(
            *args,
            on_step_start=lambda s, ts, d, t: push(
                "step_start", step=s, total_steps=ts, description=d, total=t
            ),
            on_step_item=lambda s, d, c, t: push(
                "step_item", step=s, description=d, current=c, total=t
            ),
            on_step_done=lambda s, c: push("step_done", step=s, count=c),
            on_step_error=lambda s, n, e: push(
                "step_error", step=s, item=n, error=e
            ),
            should_cancel=lambda: state.cancelled,
        )
        return result
    except QueryCancelled:
        push("cancelled", message="查询已取消")
        raise


def _run_projects_step(loop, query_id, include_archived, page_size, project_name):
    state = query_store[query_id]
    try:
        client = _make_client(loop, query_id)
        engine = QueryEngine(client)
        state.projects = _run_step(
            loop, query_id, engine.fetch_projects, include_archived, page_size,
            project_name or None
        )
        state.steps_done = 1
    except QueryCancelled:
        return
    except AuthError as e:
        _push_error(loop, state, f"鉴权失败: {e}")
    except Exception as e:
        _push_error(loop, state, str(e))


def _run_stages_step(loop, query_id, page_size):
    state = query_store[query_id]
    try:
        client = _make_client(loop, query_id)
        engine = QueryEngine(client)
        state.stages, state.tasklist_map = _run_step(
            loop, query_id, engine.fetch_stages, state.projects, page_size
        )
        state.steps_done = 2
    except QueryCancelled:
        return
    except Exception as e:
        _push_error(loop, state, str(e))


def _run_tasks_step(loop, query_id, page_size):
    state = query_store[query_id]
    try:
        client = _make_client(loop, query_id)
        engine = QueryEngine(client)
        state.tasks = _run_step(
            loop, query_id, engine.fetch_tasks, state.stages, page_size
        )
        state.steps_done = 3
    except QueryCancelled:
        return
    except Exception as e:
        _push_error(loop, state, str(e))


def _run_workhours_step(loop, query_id):
    state = query_store[query_id]
    try:
        client = _make_client(loop, query_id)
        engine = QueryEngine(client)
        state.work_hours = _run_step(
            loop, query_id, engine.fetch_workhours, state.tasks
        )
        state.steps_done = 4
        state.results = assemble(state.projects, state.stages, state.tasks, state.work_hours, state.tasklist_map)
        asyncio.run_coroutine_threadsafe(
            state.queue.put({"type": "all_done"}), loop
        )
    except QueryCancelled:
        return
    except Exception as e:
        _push_error(loop, state, str(e))


def _push_error(loop, state, message):
    state.error = message
    asyncio.run_coroutine_threadsafe(
        state.queue.put({"type": "query_error", "message": message}), loop
    )


# ------------------------------------------------------------------
# 页面
# ------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request, name="index.html",
        context={
            "app_id": os.environ.get("TB_APP_ID", ""),
            "app_secret": os.environ.get("TB_APP_SECRET", ""),
            "org_id": os.environ.get("TB_ORG_ID", ""),
        }
    )


# ------------------------------------------------------------------
# Step 1: 获取项目
# ------------------------------------------------------------------

@app.post("/api/step/projects")
async def start_projects(
    app_id: str = Form(...),
    app_secret: str = Form(...),
    org_id: str = Form(...),
    page_size: int = Form(50),
    include_archived: bool = Form(False),
    project_name: str = Form(""),
):
    query_id = uuid.uuid4().hex[:12]
    state = QueryState()
    state.app_id = app_id
    state.app_secret = app_secret
    state.org_id = org_id
    query_store[query_id] = state

    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        None, _run_projects_step, loop, query_id,
        include_archived, page_size, project_name
    )

    return {"query_id": query_id}


# ------------------------------------------------------------------
# Step 2: 获取任务列表(Stage)
# ------------------------------------------------------------------

@app.post("/api/step/{query_id}/stages")
async def start_stages(query_id: str, page_size: int = Form(50)):
    state = _get_state(query_id)
    if state.steps_done < 1:
        raise HTTPException(status_code=400, detail="请先完成项目获取步骤")
    state.cancelled = False

    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _run_stages_step, loop, query_id, page_size)

    return {"status": "started"}


# ------------------------------------------------------------------
# Step 3: 获取任务
# ------------------------------------------------------------------

@app.post("/api/step/{query_id}/tasks")
async def start_tasks(query_id: str, page_size: int = Form(50)):
    state = _get_state(query_id)
    if state.steps_done < 2:
        raise HTTPException(status_code=400, detail="请先完成任务列表获取步骤")
    state.cancelled = False

    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _run_tasks_step, loop, query_id, page_size)

    return {"status": "started"}


# ------------------------------------------------------------------
# Step 4: 获取工时
# ------------------------------------------------------------------

@app.post("/api/step/{query_id}/workhours")
async def start_workhours(query_id: str):
    state = _get_state(query_id)
    if state.steps_done < 3:
        raise HTTPException(status_code=400, detail="请先完成任务获取步骤")
    state.cancelled = False

    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _run_workhours_step, loop, query_id)

    return {"status": "started"}


# ------------------------------------------------------------------
# SSE 进度流
# ------------------------------------------------------------------

@app.get("/api/step/{query_id}/stream")
async def stream_progress(query_id: str):
    state = _get_state(query_id)

    async def event_generator():
        while True:
            event = await state.queue.get()
            event_type = event.pop("type")
            yield f"event: {event_type}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
            if event_type in ("all_done", "query_error", "cancelled"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ------------------------------------------------------------------
# 取消当前步骤
# ------------------------------------------------------------------

@app.delete("/api/step/{query_id}")
async def cancel_step(query_id: str):
    state = _get_state(query_id)
    state.cancelled = True
    return {"status": "cancelled"}


# ------------------------------------------------------------------
# 获取结果
# ------------------------------------------------------------------

@app.get("/api/step/{query_id}/result")
async def get_result(query_id: str):
    state = _get_state(query_id)
    results = assemble(state.projects, state.stages, state.tasks, state.work_hours, state.tasklist_map)
    return {
        "steps_done": state.steps_done,
        "error": state.error,
        "results": results,
    }


# ------------------------------------------------------------------
# 下载
# ------------------------------------------------------------------

@app.get("/api/step/{query_id}/download")
async def download_result(query_id: str, format: str = Query("json")):
    state = _get_state(query_id)
    if state.steps_done < 4:
        raise HTTPException(status_code=400, detail="请先完成全部四个步骤")

    results = state.results or assemble(state.projects, state.stages, state.tasks, state.work_hours, state.tasklist_map)
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    filepath = out_dir / f"result_{query_id}"

    if format == "csv":
        filepath = filepath.with_suffix(".csv")
        media_type = "text/csv"
        rows = []
        for task in results.get("tasks", []):
            rows.append({
                "project_id": task["project_id"],
                "project_name": task["project_name"],
                "stage_id": task["stage_id"],
                "task_id": task["task_id"],
                "task_content": task["content"],
                "task_done": task["is_done"],
                "task_executor": task["executor_id"],
                "actual_hours": task.get("actual_hours", 0),
                "planned_hours": task.get("planned_hours", 0),
            })
        Exporter.to_csv(rows, str(filepath))
    elif format == "xlsx":
        filepath = filepath.with_suffix(".xlsx")
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        Exporter.to_excel(results, str(filepath))
    else:
        filepath = filepath.with_suffix(".json")
        media_type = "application/octet-stream"
        Exporter.to_json(results, str(filepath))

    return FileResponse(
        str(filepath),
        filename=filepath.name,
        media_type=media_type,
    )
