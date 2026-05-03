# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Teambition 项目-任务-工时 级联查询工具。按 Projects → Tasks → WorkHours 层级调用 Teambition Open API，支持 CLI 和 Web 两种使用模式。

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 运行 CLI
python cli.py --app-id <ID> --app-secret <SECRET> --org-id <ORG>
python cli.py --app-id <ID> --app-secret <SECRET> --org-id <ORG> --output csv --output-file result

# 启动 Web 服务 (开发)
uvicorn web_server:app --reload --port 8080

# Docker 方式
docker compose up

# 运行所有测试
python -m pytest tests/ -v

# 运行单个测试文件
python -m pytest tests/test_fetchers.py -v

# 运行单个测试函数
python -m pytest tests/test_fetchers.py::test_fetch_all_projects_single_page -v
```

环境变量（`.env` 文件或直接设置）：`TB_APP_ID`, `TB_APP_SECRET`, `TB_ORG_ID`

## 架构

```
auth.py          ── Token 获取与缓存，构建鉴权 headers
api_client.py    ── HTTP 客户端（重试、超时）+ 分页迭代器
fetchers/
  projects.py    ── Step 1: 获取用户参与的项目列表
  tasks.py       ── Step 2: 按项目获取任务列表
  workhours.py   ── Step 3: 按任务获取实际/计划工时
engine.py        ── 查询引擎：编排三步级联查询，通过回调报告进度（CLI 和 Web 共用）
exporter.py      ── JSON / CSV 导出
progress.py      ── Rich 终端进度展示（CLI 专用）
cli.py           ── CLI 入口：参数解析、流程编排
web_server.py    ── FastAPI Web 服务：前端页面 + 分步 API + SSE 进度推送
```

## 关键设计决策

- **回调模式**：`engine.py` 通过 `on_step_start/on_step_item/on_step_done/on_step_error/should_cancel` 回调解耦进度报告。CLI 端连到 Rich 进度条，Web 端连到 SSE 事件推送。
- **API 响应格式**：Teambition API 在 HTTP 200 的 JSON body 中返回错误码（`code` 字段），不是用 HTTP 状态码。`api_client.py` 检查 `data.get("code", 0)` 判断成功/失败。
- **Projects 获取是两步的**：先 `paginate("/v3/project/user-joined")` 拿 ID 列表，再 `GET /v3/project/query?projectIds=...` 批量拿详情（每次最多 50 个）。
- **Token 端点**：`POST /appToken`（非标准 RESTful 路径），响应字段为 `appToken` 和 `expire`（秒）。

## 测试

测试使用 `responses` 库 mock HTTP 请求。`fetchers` 和 `api_client` 的测试共用一个 `auth`/`client` fixture，手动注入 `auth._token` 跳过真实 token 请求。

`progress.py` 无单元测试（纯终端输出不适合断言），`cli.py` 和 `web_server.py` 无单元测试（集成层）。
