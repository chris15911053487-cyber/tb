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
