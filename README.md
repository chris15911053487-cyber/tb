# Teambition 级联查询工具

按 项目 → 任务 → 工时 层级调用 Teambition Open API，支持 CLI 和 Web 两种使用方式。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置凭证

通过环境变量或 `.env` 文件：

```bash
export TB_APP_ID=your_app_id
export TB_APP_SECRET=your_app_secret
export TB_ORG_ID=your_org_id
```

### 3. 使用

**CLI 模式：**

```bash
# JSON 输出（默认）
python cli.py

# CSV 输出
python cli.py --output csv --output-file result

# 包含已归档项目
python cli.py --include-archived
```

**Web 模式：**

```bash
uvicorn web_server:app --reload --port 8080
# 浏览器打开 http://localhost:8080
```

**Docker：**

```bash
docker compose up
# 访问 http://localhost:8080
```

## 功能

- 三级联查：项目 → 任务 → 工时，自动分页
- 双模式：CLI（Rich 进度条） / Web（SSE 实时进度，分步执行）
- 导出：JSON / CSV
- Web 端支持搜索、排序、在线下载

## 测试

```bash
# 全部
python -m pytest tests/ -v

# 单文件
python -m pytest tests/test_fetchers.py -v
```
