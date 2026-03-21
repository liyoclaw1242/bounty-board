# Bounty Board — Agent 全局規則

> 所有 agent 啟動時自動載入此文件。

## 必讀清單（每次接單前）

1. **`overview.md`** — 全局架構視圖（若存在）
2. **`docs/adr/`** — 與本次任務相關的架構決策記錄

## 角色專屬規範

根據你的 `agent_type`，讀取對應的接單規範：

| 角色 | 規範文件 |
|------|---------|
| `arch` | `.claude/commands/arch-onboard.md` |
| `be` | `.claude/commands/be-onboard.md` |
| `fe` | `.claude/commands/fe-onboard.md` |
| `qa` | `.claude/commands/qa-onboard.md` |
| `pm` | `.claude/commands/pm-onboard.md` |

## 通用原則

- 接單前先確認 `overview.md` 是否存在，存在就讀
- 產出 artifact 必須以 PR 或 issue comment 形式交付
- 不要自行決定影響範圍，以 ARCH 的評估結果為依據
- 有跨 repo 疑慮時，停下來發 issue 請 ARCH 評估
