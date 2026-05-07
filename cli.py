#!/usr/bin/env python3
"""Teambition 项目-任务-工时 级联查询工具（CLI 模式）。

用法:
  python cli.py --app-id <ID> --app-secret <SECRET> --org-id <ORG>
  python cli.py --app-id <ID> --app-secret <SECRET> --org-id <ORG> --output csv --output-file result.csv
"""
import argparse
import os
import signal
import sys

from auth import TeambitionAuth
from api_client import APIClient
from engine import QueryEngine
from progress import ProgressDisplay
from exporter import Exporter


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
    engine = QueryEngine(client)

    # --- Rich 进度回调适配 ---
    def on_step_start(step, total_steps, description, total_items):
        display.show_step(step, total_steps, description)

    def on_step_item(step, description, current, total):
        pass  # 进度条更新由 Progress context manager 处理

    def on_step_done(step, count):
        display.console.print(f"  获取到 [bold]{count}[/] 条记录")

    def on_step_error(step, item_name, error_msg):
        display.console.print(f"[red]  {item_name} 失败: {error_msg}[/]")

    # --- SIGINT 处理 ---
    def handle_sigint(sig, frame):
        display.console.print("\n[yellow]收到中断信号，退出。[/]")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    # --- 执行查询 ---
    results = engine.run(
        include_archived=args.include_archived,
        page_size=args.page_size,
        on_step_start=on_step_start,
        on_step_item=on_step_item,
        on_step_done=on_step_done,
        on_step_error=on_step_error,
    )

    if not results["projects"]:
        display.console.print("[yellow]没有找到项目，退出。[/]")
        sys.exit(0)

    # --- 统计 ---
    project_count = len(results["projects"])
    stage_count = len(results["stages"])
    task_count = len(results["tasks"])
    hours_count = sum(
        1 for t in results["tasks"]
        if t.get("actual_hours", 0) > 0 or t.get("planned_hours", 0) > 0
    )

    # --- 导出 ---
    out_path = args.output_file
    if args.output == "csv":
        if not out_path.endswith(".csv"):
            out_path += ".csv"
        rows = []
        for task in results["tasks"]:
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
        Exporter.to_csv(rows, out_path)
    else:
        if not out_path.endswith(".json"):
            out_path += ".json"
        Exporter.to_json(results, out_path)

    display.console.print(f"\n[green]导出完成: {out_path}[/]")
    display.show_summary({
        "项目数": project_count,
        "任务列表(Stage)": stage_count,
        "任务数": task_count,
        "工时记录": hours_count,
        "输出文件": out_path,
    })


if __name__ == "__main__":
    main()
