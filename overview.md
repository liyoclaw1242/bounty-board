# Bounty Board — Overview

> 全局視圖文件。ARCH agent 首次接單時建立，後續接單時須先讀此文件。
> 最後更新：2026-03-21 by `arch-20260321-081744`

## 項目簡介

Bounty Board 是一個**多 agent 軟體開發協作平台**。核心理念：

- 以 **GitHub Issues** 作為任務看板（bounty）
- 以 **REST API** 作為控制平面，管理 repo 註冊、任務建立、互斥鎖
- 以 **autonomous agent processes** 消費任務，透過 Claude Code 實作並開 PR

人類負責啟停 agent、建立任務、review PR。系統自動處理任務分派、並行控制、依賴解鎖。

## 架構全貌

```
┌─────────────────────────────────────────────────────────────────┐
│                        Human Operator                           │
│   Starts/stops agents · Creates bounties · Reviews PRs          │
└────────────────┬───────────────────────────────┬────────────────┘
                 │                               │
        ┌────────▼────────┐             ┌────────▼────────┐
        │  Agent Process  │ ...N        │  Agent Process  │
        │  (BE/FE/QA/PM/  │             │  (ARCH/DESIGN/  │
        │   OPS/DEBUG)    │             │   DEBUG/PM)     │
        └────────┬────────┘             └────────┬────────┘
                 │  HTTP (poll/claim)             │
        ┌────────▼────────────────────────────────▼───────┐
        │              API Server (FastAPI :8000)          │
        │                                                  │
        │  /repos      — CRUD target repos                │
        │  /bounties   — CRUD tasks (GitHub Issues)       │
        │  /claims     — atomic mutex (prevent dup work)  │
        │  /health     — system status                    │
        │                                                  │
        │  Storage: SQLite (WAL mode)                     │
        │  Tables: repos, claims                          │
        └────────┬────────────────────────────────────────┘
                 │  GitHub REST API
        ┌────────▼────────┐    ┌────────────────┐
        │  target repo A  │    │  target repo B  │  ...N
        │  (Issues=tasks) │    │  (Issues=tasks) │
        └─────────────────┘    └─────────────────┘
```

## 模組說明

### `app/` — API Server（控制平面）

| 檔案 | 職責 |
|------|------|
| `main.py` | FastAPI 入口，lifespan 管理 DB 連線與 GitHub client 快取 |
| `config.py` | 環境設定（Pydantic Settings，`BOUNTY_` prefix） |
| `database.py` | Thread-safe SQLite wrapper（single writer via lock） |
| `models.py` | Pydantic request/response models |
| `state.py` | AppState singleton（DB + cached GitHub clients） |
| `routers/repos.py` | `/repos` — 註冊 repo（clone + 建立 labels） |
| `routers/bounties.py` | `/bounties` — 建立/查詢/更新任務（GitHub Issues） |
| `routers/claims.py` | `/claims` — atomic mutex（INSERT OR IGNORE） |

### `agents/` — Agent Processes（執行平面）

| 檔案 | 職責 |
|------|------|
| `base_agent.py` | 共用 polling loop + claim logic + Claude Code subprocess |
| `be_agent.py` | Backend agent — 實作後端任務 → push branch → open PR |
| `fe_agent.py` | Frontend agent — 繼承 BE，prompt 專注 React/TS |
| `qa_agent.py` | QA agent — review agent PRs，approve / request changes |
| `pm_agent.py` | PM agent — 解鎖 blocked issues（dependency tracking） |

### `lib/` — 共用函式庫

| 檔案 | 職責 |
|------|------|
| `github_client.py` | GitHub REST API wrapper（ETag conditional request + rate limit retry） |
| `git_ops.py` | Git 操作（branch / commit / push / clean） |
| `logger.py` | 結構化 JSONL event logging（`~/.bounty/agent.log`） |
| `claims.py` | SQLite claim mutex（agent-side，與 API-side 互通） |

### `db/` — Database Schema

| 檔案 | 職責 |
|------|------|
| `schema.sql` | SQLite schema — `repos` + `claims` 兩張表 |

### `scripts/` — CLI Utilities

| 檔案 | 職責 |
|------|------|
| `query_claims.sh` | 查詢 claims / logs / rate limits |

## 主要入口點

| 入口 | 用途 | 啟動方式 |
|------|------|---------|
| API Server | 控制平面 | `uvicorn app.main:app --port 8000` |
| BE Agent | 後端實作 | `python3 agents/be_agent.py` |
| FE Agent | 前端實作 | `python3 agents/fe_agent.py` |
| QA Agent | PR Review | `python3 agents/qa_agent.py` |
| PM Agent | 依賴管理 | `python3 agents/pm_agent.py` |
| Docker | 全套啟動 | `docker compose up -d` |
| Swagger UI | API 文件 | `http://localhost:8000/docs` |

## 任務生命週期

```
                    ┌─ deps provided ──→ status:blocked
POST /bounties ─────┤                        │
                    └─ no deps ────→ status:ready    ◄── PM unblocks
                                         │
                                    Agent claims (mutex)
                                         │
                                    status:in-progress
                                         │
                                    Agent implements
                                    (Claude Code → git push → PR)
                                         │
                                    status:review
                                         │
                                    QA Agent reviews
                                         │
                                  ┌──────┴──────┐
                                  │             │
                              APPROVE     REQUEST_CHANGES
                                  │             │
                              Merge PR    Agent rework (future)
```

## 資料流

### Claim Mutex 機制

```
Agent A → POST /claims {issue: 5} → 201 Created  ✓
Agent B → POST /claims {issue: 5} → 409 Conflict ✗
Agent A → DELETE /claims/.../5    → 204 Released
Agent B → POST /claims {issue: 5} → 201 Created  ✓ (retry succeeds)
```

- 以 `(repo_slug, issue_number)` 為複合主鍵
- TTL 機制：預設 2 小時，agent crash 後自動過期
- Agent-side 與 API-side 各有實作，共用同一張表

### 依賴追蹤

```
Issue body: <!-- deps: 10, 12 -->
PM Agent: parse deps → check if #10 and #12 are closed → unblock
```

## 相關 Repo

| Repo | 關係 | 說明 |
|------|------|------|
| `liyoclaw1242/bounty-board` | **self** | 本 repo，同時是平台本身與第一個 target repo |

> 系統支援多 repo（`POST /repos` 註冊），目前僅此一個。

## Label Schema

| Label | 用途 |
|-------|------|
| `agent:be` / `fe` / `qa` / `devops` / `arch` / `design` / `debug` / `pm` | 指定負責角色 |
| `status:ready` | 可被 claim |
| `status:blocked` | 等待依賴 |
| `status:in-progress` | agent 正在處理 |
| `status:review` | PR 已開，等待 QA |

## ADR 目錄

| ADR | 標題 | 狀態 |
|-----|------|------|
| [ADR-0001](docs/adr/0001-repo-slug-role-confirmation-impact.md) | Repo Slug + 角色確認環節的影響範圍評估 | Accepted |

## 技術棧

| 元件 | 技術 |
|------|------|
| API | Python 3.12 + FastAPI + Pydantic |
| Database | SQLite (WAL mode) |
| Agent Runtime | Python subprocess → Claude Code CLI |
| Git | Local git CLI + GitHub REST API |
| Container | Docker + docker-compose |
| CI/CD | (尚未設置) |
