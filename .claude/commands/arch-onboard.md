# ARCH Agent 接單規範

## 首次接單（repo 尚無 `overview.md`）

1. **探索 repo** — 讀取所有主要目錄與檔案，理解全局架構
2. **建立 `overview.md`** — 於 repo 根目錄產出全局視圖：
   - 項目簡介
   - 架構圖（ASCII 或 Mermaid）
   - 模組說明（每個目錄/檔案的職責）
   - 主要入口點
   - 任務生命週期 / 資料流
   - 相關 repo（如有跨 repo 耦合）
   - ADR 目錄（連結至 `docs/adr/`）
   - 技術棧
3. **完成原始任務** — 在理解全局後，執行 issue spec 中的分析或設計工作

## 後續接單（repo 已有 `overview.md`）

1. **先讀 `overview.md`** — 快速建立全局上下文
2. **讀相關 ADR** — 查看 `docs/adr/` 中與本次任務相關的決策記錄
3. **執行任務** — 根據 issue spec 產出設計 artifact
4. **更新 `overview.md`**（如有重大架構變更）

## 輸出格式

每次接單必須產出包含以下欄位的 artifact（PR 或 issue comment）：

```
- 受影響 repo slug：
- 受影響角色（agent_type）：
- 跨 repo 耦合：有 / 無（若有，列出）
- ADR 編號（若有新決策）：
```

## ADR 格式

```markdown
# ADR-NNNN: {標題}

- **Status:** Proposed | Accepted | Deprecated | Superseded
- **Date:** YYYY-MM-DD
- **Author:** Agent `{AGENT_ID}`
- **Issue:** #{N}

## Context
## Decision
## Consequences
```
