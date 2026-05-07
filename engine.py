"""查询引擎：项目、Stage、任务、工时四级查询，可单步或一键执行。"""
from fetchers.projects import ProjectsFetcher
from fetchers.stages import StagesFetcher
from fetchers.tasks import TasksFetcher
from fetchers.workhours import WorkHoursFetcher


class QueryCancelled(Exception):
    """查询被用户取消。"""


TOTAL_STEPS = 4


class QueryEngine:
    """执行项目-Stage-任务-工时级联查询，通过回调报告进度。"""

    def __init__(self, client):
        self.client = client

    # ------------------------------------------------------------------
    # 单步方法（供 Web 分步调用）
    # ------------------------------------------------------------------

    def fetch_projects(self, include_archived=False, page_size=50,
                       name_filter=None,
                       on_step_start=None, on_step_item=None, on_step_done=None,
                       on_step_error=None, should_cancel=None):
        """Step 1: 获取项目列表，可选按名称模糊筛选。"""
        cb = _Callbacks(on_step_start, on_step_item, on_step_done,
                        on_step_error, should_cancel)

        cb.start(1, TOTAL_STEPS, "获取项目列表", 0)
        projects = ProjectsFetcher(self.client).fetch_all(
            include_archived=include_archived, page_size=page_size
        )
        if name_filter:
            kw = name_filter.lower()
            projects = [p for p in projects if kw in p.name.lower()]
        cb.check()
        cb.done(1, len(projects))
        return projects

    def fetch_stages(self, projects, page_size=50,
                     on_step_start=None, on_step_item=None, on_step_done=None,
                     on_step_error=None, should_cancel=None):
        """Step 2: 获取每个项目下的任务列表（Stage）+ 任务分组（Tasklist）。"""
        cb = _Callbacks(on_step_start, on_step_item, on_step_done,
                        on_step_error, should_cancel)

        if not projects:
            cb.start(2, TOTAL_STEPS, "获取任务列表", 0)
            cb.done(2, 0)
            return [], {}

        cb.start(2, TOTAL_STEPS, "获取任务列表", len(projects))
        stage_fetcher = StagesFetcher(self.client)
        all_stages = []
        tasklist_map = {}
        for i, proj in enumerate(projects):
            cb.check()
            try:
                stages = stage_fetcher.fetch_for_project(
                    proj.id, page_size=page_size
                )
                all_stages.extend(stages)
                tasklist_map.update(
                    stage_fetcher.fetch_tasklists_for_project(
                        proj.id, page_size=page_size
                    )
                )
            except Exception as e:
                cb.error(2, proj.name, str(e))
            cb.item(2, proj.name, i + 1, len(projects))
        cb.done(2, len(all_stages))
        return all_stages, tasklist_map

    def fetch_tasks(self, stages, page_size=50,
                    on_step_start=None, on_step_item=None, on_step_done=None,
                    on_step_error=None, should_cancel=None):
        """Step 3: 获取每个项目下的全部任务（按 project_id 去重）。"""
        cb = _Callbacks(on_step_start, on_step_item, on_step_done,
                        on_step_error, should_cancel)

        if not stages:
            cb.start(3, TOTAL_STEPS, "获取任务", 0)
            cb.done(3, 0)
            return []

        # 按项目去重，每个项目只调一次
        proj_ids = list(dict.fromkeys(s.project_id for s in stages))
        cb.start(3, TOTAL_STEPS, "获取任务", len(proj_ids))
        task_fetcher = TasksFetcher(self.client)
        all_tasks = []
        for i, proj_id in enumerate(proj_ids):
            cb.check()
            try:
                tasks = task_fetcher.fetch_for_project(proj_id, page_size=page_size)
                all_tasks.extend(tasks)
            except Exception as e:
                cb.error(3, proj_id, str(e))
            if (i + 1) % 5 == 0 or i == len(proj_ids) - 1:
                cb.item(3, f"项目 {i + 1}/{len(proj_ids)}", i + 1, len(proj_ids))
        cb.done(3, len(all_tasks))
        return all_tasks

    def fetch_workhours(self, tasks,
                        on_step_start=None, on_step_item=None, on_step_done=None,
                        on_step_error=None, should_cancel=None):
        """Step 4: 获取每个任务的工时。"""
        cb = _Callbacks(on_step_start, on_step_item, on_step_done,
                        on_step_error, should_cancel)

        if not tasks:
            cb.start(4, TOTAL_STEPS, "获取工时", 0)
            cb.done(4, 0)
            return []

        cb.start(4, TOTAL_STEPS, "获取工时", len(tasks))
        hours_fetcher = WorkHoursFetcher(self.client)
        all_hours = []
        for i, task in enumerate(tasks):
            cb.check()
            hours = hours_fetcher.fetch_for_task(task.id)
            all_hours.append(hours)
            if (i + 1) % 10 == 0 or i == len(tasks) - 1:
                cb.item(4, f"任务 {i + 1}/{len(tasks)}", i + 1, len(tasks))
        cb.done(4, len(all_hours))
        return all_hours

    # ------------------------------------------------------------------
    # 一键方法（CLI 使用）
    # ------------------------------------------------------------------

    def run(self, include_archived=False, page_size=50,
            on_step_start=None, on_step_item=None, on_step_done=None,
            on_step_error=None, should_cancel=None):
        """一键执行四级级联查询，返回完整结果 dict。"""
        projects = self.fetch_projects(
            include_archived=include_archived, page_size=page_size,
            on_step_start=on_step_start, on_step_item=on_step_item,
            on_step_done=on_step_done, on_step_error=on_step_error,
            should_cancel=should_cancel,
        )
        if not projects:
            return {"projects": []}

        stages, tasklist_map = self.fetch_stages(
            projects, page_size=page_size,
            on_step_start=on_step_start, on_step_item=on_step_item,
            on_step_done=on_step_done, on_step_error=on_step_error,
            should_cancel=should_cancel,
        )

        tasks = self.fetch_tasks(
            stages, page_size=page_size,
            on_step_start=on_step_start, on_step_item=on_step_item,
            on_step_done=on_step_done, on_step_error=on_step_error,
            should_cancel=should_cancel,
        )

        hours = self.fetch_workhours(
            tasks,
            on_step_start=on_step_start, on_step_item=on_step_item,
            on_step_done=on_step_done, on_step_error=on_step_error,
            should_cancel=should_cancel,
        )

        return assemble(projects, stages, tasks, hours, tasklist_map)


# ------------------------------------------------------------------
# 组装 & 回调辅助
# ------------------------------------------------------------------

def assemble(projects, stages, tasks, work_hours, tasklist_map=None):
    """将四个列表组装为嵌套结果 dict，供前端页签渲染。"""
    if tasklist_map is None:
        tasklist_map = {}

    # 构建工时查找表
    wh_map = {}
    for wh in work_hours:
        wh_map[wh.task_id] = {"actual": wh.actual_hours, "planned": wh.planned_hours}

    # 项目清单
    projects_data = []
    for proj in projects:
        proj_tasks = [t for t in tasks if t.project_id == proj.id]
        proj_actual = sum(
            wh_map.get(t.id, {}).get("actual", 0) for t in proj_tasks
        )
        proj_planned = sum(
            wh_map.get(t.id, {}).get("planned", 0) for t in proj_tasks
        )
        projects_data.append({
            "project_id": proj.id,
            "project_name": proj.name,
            "project_description": proj.description,
            "is_archived": proj.is_archived,
            "task_count": len(proj_tasks),
            "actual_hours": proj_actual,
            "planned_hours": proj_planned,
        })

    # Stage 清单（保留所属项目名）
    proj_map = {p.id: p for p in projects}
    stages_data = []
    for stage in stages:
        proj = proj_map.get(stage.project_id)
        stages_data.append({
            "stage_id": stage.id,
            "stage_name": stage.name,
            "project_id": stage.project_id,
            "project_name": proj.name if proj else "",
        })

    # 任务清单
    tasks_data = []
    for task in tasks:
        wh = wh_map.get(task.id, {})
        proj = proj_map.get(task.project_id)
        tasks_data.append({
            "task_id": task.id,
            "project_id": task.project_id,
            "project_name": proj.name if proj else "",
            "stage_id": task.stage_id,
            "stage_name": tasklist_map.get(task.stage_id, ""),
            "content": task.content,
            "is_done": task.is_done,
            "executor_id": task.executor_id,
            "actual_hours": wh.get("actual", 0),
            "planned_hours": wh.get("planned", 0),
        })

    return {
        "projects": projects_data,
        "stages": stages_data,
        "tasks": tasks_data,
    }


class _Callbacks:
    """统一处理回调的 noop 默认值和 cancel 检查。"""

    def __init__(self, on_start, on_item, on_done, on_error, should_cancel):
        self.on_start = on_start or _noop
        self.on_item = on_item or _noop
        self.on_done = on_done or _noop
        self.on_error = on_error or _noop
        self.should_cancel = should_cancel or (lambda: False)

    def start(self, step, total_steps, desc, total):
        self.on_start(step, total_steps, desc, total)

    def item(self, step, desc, current, total):
        self.on_item(step, desc, current, total)

    def done(self, step, count):
        self.on_done(step, count)

    def error(self, step, item_name, error_msg):
        self.on_error(step, item_name, error_msg)

    def check(self):
        if self.should_cancel():
            raise QueryCancelled()


def _noop(*args):
    pass
