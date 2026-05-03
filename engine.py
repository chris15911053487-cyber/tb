"""查询引擎：项目、任务、工时三级查询，可单步或一键执行。"""
from fetchers.projects import ProjectsFetcher
from fetchers.tasks import TasksFetcher
from fetchers.workhours import WorkHoursFetcher


class QueryCancelled(Exception):
    """查询被用户取消。"""


class QueryEngine:
    """执行项目-任务-工时级联查询，通过回调报告进度。"""

    def __init__(self, client):
        self.client = client

    # ------------------------------------------------------------------
    # 单步方法（供 Web 分步调用）
    # ------------------------------------------------------------------

    def fetch_projects(self, include_archived=False, page_size=50,
                       on_step_start=None, on_step_item=None, on_step_done=None,
                       on_step_error=None, should_cancel=None):
        """Step 1: 获取项目列表。"""
        cb = _Callbacks(on_step_start, on_step_item, on_step_done,
                        on_step_error, should_cancel)

        cb.start(1, 1, "获取项目列表", 0)
        projects = ProjectsFetcher(self.client).fetch_all(
            include_archived=include_archived, page_size=page_size
        )
        cb.check()
        cb.done(1, len(projects))
        return projects

    def fetch_tasks(self, projects, page_size=50,
                    on_step_start=None, on_step_item=None, on_step_done=None,
                    on_step_error=None, should_cancel=None):
        """Step 2: 获取每个项目的任务列表。"""
        cb = _Callbacks(on_step_start, on_step_item, on_step_done,
                        on_step_error, should_cancel)

        if not projects:
            cb.start(2, 1, "获取任务", 0)
            cb.done(2, 0)
            return []

        cb.start(2, 1, "获取任务", len(projects))
        task_fetcher = TasksFetcher(self.client)
        all_tasks = []
        for i, proj in enumerate(projects):
            cb.check()
            try:
                tasks = task_fetcher.fetch_for_project(
                    proj.id, page_size=page_size
                )
                all_tasks.extend(tasks)
            except Exception as e:
                cb.error(2, proj.name, str(e))
            cb.item(2, proj.name, i + 1, len(projects))
        cb.done(2, len(all_tasks))
        return all_tasks

    def fetch_workhours(self, tasks,
                        on_step_start=None, on_step_item=None, on_step_done=None,
                        on_step_error=None, should_cancel=None):
        """Step 3: 获取每个任务的工时。"""
        cb = _Callbacks(on_step_start, on_step_item, on_step_done,
                        on_step_error, should_cancel)

        if not tasks:
            cb.start(3, 1, "获取工时", 0)
            cb.done(3, 0)
            return []

        cb.start(3, 1, "获取工时", len(tasks))
        hours_fetcher = WorkHoursFetcher(self.client)
        all_hours = []
        for i, task in enumerate(tasks):
            cb.check()
            hours = hours_fetcher.fetch_for_task(task.id)
            all_hours.append(hours)
            if (i + 1) % 10 == 0 or i == len(tasks) - 1:
                cb.item(3, f"任务 {i + 1}/{len(tasks)}", i + 1, len(tasks))
        cb.done(3, len(all_hours))
        return all_hours

    # ------------------------------------------------------------------
    # 一键方法（CLI 使用）
    # ------------------------------------------------------------------

    def run(self, include_archived=False, page_size=50,
            on_step_start=None, on_step_item=None, on_step_done=None,
            on_step_error=None, should_cancel=None):
        """一键执行三步级联查询，返回完整结果 dict。"""
        projects = self.fetch_projects(
            include_archived=include_archived, page_size=page_size,
            on_step_start=on_step_start, on_step_item=on_step_item,
            on_step_done=on_step_done, on_step_error=on_step_error,
            should_cancel=should_cancel,
        )
        if not projects:
            return {"projects": []}

        tasks = self.fetch_tasks(
            projects, page_size=page_size,
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

        return assemble(projects, tasks, hours)


# ------------------------------------------------------------------
# 组装 & 回调辅助
# ------------------------------------------------------------------

def assemble(projects, tasks, work_hours):
    """将三个列表组装为嵌套结果 dict。"""
    results = {"projects": []}
    for proj in projects:
        proj_entry = {
            "project_id": proj.id,
            "project_name": proj.name,
            "project_description": proj.description,
            "is_archived": proj.is_archived,
            "tasks": [],
        }
        proj_tasks = [t for t in tasks if t.project_id == proj.id]
        for task in proj_tasks:
            task_entry = {
                "task_id": task.id,
                "content": task.content,
                "is_done": task.is_done,
                "executor_id": task.executor_id,
                "work_hours": None,
            }
            for wh in work_hours:
                if wh.task_id == task.id:
                    task_entry["work_hours"] = {
                        "actual": wh.actual_hours,
                        "planned": wh.planned_hours,
                    }
                    break
            proj_entry["tasks"].append(task_entry)
        results["projects"].append(proj_entry)
    return results


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
