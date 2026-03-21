# ARCH Agent 接單規範

## 首次接單（repo 尚無 `/overview`）

1. **探索 repo** — 讀取所有主要目錄與檔案，理解全局架構
2. **建立 `overview.md`** — 於 repo 根目錄產出全局視圖，格式如下：
   - 項目簡介
   - 架構圖（ASCII 或 Mermaid）
   - 模組說明（每個目錄/檔案的職責）
   - 主要入口點
   - 任務生命週期 / 資料流
   - 相關 repo（如有跨 repo 耦合）
   - ADR 目錄（連結至 `docs/adr/`）
   - 技術棧
3. **完成原始任務** — 在理解全局後，執行 issue spec 中的分析或設計工作

## 後續接單（repo 已有 `/overview`）

1. **先讀 `overview.md`** — 快速建立全局上下文
2. **讀相關 ADR** — 查看 `docs/adr/` 中與本次任務相關的決策記錄
3. **執行任務** — 根據 issue spec 產出設計 artifact
4. **更新 `overview.md`**（如有重大變更）：
   - 新增模組 → 更新模組說明
   - 架構變動 → 更新架構圖
   - 新增 ADR → 更新 ADR 目錄
   - 新增 repo → 更新相關 repo

## `/overview` 與 `docs/adr/` 的互補關係

| 文件 | 角色 | 內容 |
|------|------|------|
| `overview.md` | 全局視圖（What） | 這個項目是什麼、架構全貌、模組關係 |
| `docs/adr/*.md` | 決策記錄（Why） | 為什麼這樣決定、替代方案、影響評估 |

- `overview.md` 是**活文件**，隨架構演進而更新
- ADR 是**不可變記錄**，反映決策歷史（status 可從 Proposed → Accepted → Superseded）

## ADR 格式

```markdown
# ADR-NNNN: {標題}

- **Status:** Proposed | Accepted | Deprecated | Superseded
- **Date:** YYYY-MM-DD
- **Author:** Agent `{AGENT_ID}`
- **Issue:** #{N}

## Context
[為什麼需要這個決策]

## Decision
[做了什麼決定]

## Consequences
[正面與負面影響]
```
