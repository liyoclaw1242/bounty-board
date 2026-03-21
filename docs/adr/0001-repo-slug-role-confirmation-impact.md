# ADR-0001: 「Repo Slug + 角色確認」環節的影響範圍評估

- **Status:** Accepted
- **Date:** 2026-03-21
- **Author:** Agent `arch-20260321-081744`
- **Issue:** #1

## Context

PM 在建立 bounty 任務時需指定 `repo_slug`（目標 repo）與 `agent_type`（負責角色），
後續由 ARCH 負責判斷該流程環節對系統架構的影響度。本文件記錄對此流程的全面評估。

## 系統全局架構摘要

Bounty Board 為多 agent 軟體開發協作平台，由以下三層組成：

1. **Control Plane** — FastAPI API Server（port 8000），SQLite 儲存 repos + claims
2. **Execution Agents** — BE / FE / QA / PM 等長駐 polling 程序，透過 GitHub API + 本地 git + Claude Code 執行任務
3. **Task Model** — GitHub Issues 作為任務載體，Labels 控制狀態與指派，HTML comments 記錄依賴關係

### 核心流程

```
PM 建立 bounty（指定 repo_slug + agent_type）
  → API 建立 GitHub Issue（標記 agent:{type} + status:ready/blocked）
  → 對應 Agent 透過 polling 發現任務 → claim → 實作 → PR
  → QA Agent review PR
  → PM Agent 處理 dependency unblocking
```

## 受影響的 Repo Slug

| Repo Slug | 影響程度 | 說明 |
|-----------|---------|------|
| `liyoclaw1242/bounty-board` | **直接** | 唯一已註冊的 repo，所有任務流經此 repo |

> **備註：** 系統設計為多 repo 架構。`POST /repos` 可註冊多個 repo，每個 repo 獨立擁有 GitHub Issue 任務空間。
> 目前僅一個 repo，但架構已支援多 repo 場景。

## 受影響的角色（agent_type）

「repo slug + 角色確認」環節涉及以下角色的交互：

| 角色 | agent_type | 影響方式 |
|------|-----------|---------|
| **PM** | `pm` | **發起者** — 建立 bounty 時指定 repo_slug 與 agent_type，決定任務路由 |
| **ARCH** | `arch` | **評估者** — 確認影響範圍，產出設計文件 |
| **BE** | `be` | **下游消費者** — 根據 PM 指定的 repo_slug polling 對應 label 的任務 |
| **FE** | `fe` | **下游消費者** — 同 BE，但關注前端任務 |
| **OPS** | `devops` | **下游消費者** — 同 BE，但關注基礎設施任務 |
| **QA** | `qa` | **間接影響** — review 所有 agent branch 的 PR，不直接受 repo_slug 路由影響 |
| **DEBUG** | `debug` | **下游消費者** — polling debug 類型任務 |
| **DESIGN** | `design` | **下游消費者** — polling design 類型任務 |

### 關鍵路徑

```
PM (建立) → API (路由) → Agent (polling + claim) → QA (review)
                ↑
            ARCH (評估影響範圍，產出 ADR)
```

PM 的 `repo_slug` 決定任務落在哪個 repo 的 issue tracker；
PM 的 `agent_type` 決定哪類 agent 能發現並 claim 該任務。
若任一指定錯誤，任務將無法被正確 agent 接收。

## 跨 Repo 耦合分析

### 目前狀態：無跨 Repo 耦合

| 耦合點 | 說明 | 風險等級 |
|--------|------|---------|
| Claims 資料庫 | `(repo_slug, issue_number)` 複合鍵，已正確隔離 | 低 |
| GitHub Token | 每個 repo 獨立儲存 token（`repos.github_token`） | 低 |
| Agent Polling | Agent 以 `repo_slug` + `agent_type` 作為 filter，天然隔離 | 低 |
| Label 命名 | 所有 repo 使用相同 label 命名慣例，但這是 convention 非 coupling | 低 |
| Branch 命名 | `agent/{id}/issue-{N}` 模式在各 repo 獨立，無衝突 | 低 |
| 依賴追蹤 | `<!-- deps: N, M -->` 僅引用同 repo 內的 issue number | 低 |

### 潛在風險（未來多 repo 場景）

1. **跨 repo 依賴** — 目前 `<!-- deps -->` 格式只支援同 repo 的 issue number。若未來需要跨 repo 依賴（如 `repo-a#10` 依賴 `repo-b#5`），需擴展 PM Agent 的 `parse_deps()` 與 dependency 格式。

2. **Agent 配置** — 目前每個 agent process 透過 env var 綁定單一 repo。若需要單一 agent 服務多 repo，需改造 `BaseAgent` 的 polling 邏輯。

3. **GitHub Rate Limit** — 多 repo 共用同一 token 時可能遭遇 rate limit，但目前 `github_client.py` 已有 rate limit handling。

## Decision

「repo slug + 角色確認」環節是任務路由的核心，其影響為：

1. **影響範圍有限但關鍵** — 僅影響任務的 label 標記與 agent 的 polling filter，但若指定錯誤將導致任務無法被正確接收。
2. **無跨 repo 耦合** — 目前單 repo 運作，架構已為多 repo 做好隔離設計。
3. **ARCH 的角色定位明確** — ARCH 負責在 PM 指定 repo 後，評估技術影響範圍並產出設計文件，作為下游 BE/FE/OPS 的實作依據。

## Consequences

- PM 只需做一個決策：「這個需求屬於哪個 repo + 哪種角色」
- ARCH 讀取全局架構後補充：「影響哪些模組、是否有跨 repo 耦合」
- 下游 agent 根據 label 自動接收任務，無需人工介入
- 若未來新增 repo，此流程無需修改，只需 `POST /repos` 註冊即可
