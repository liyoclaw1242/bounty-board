# BE Agent 接單規範

## 接單流程

1. 讀 `overview.md` 理解全局架構
2. 讀 issue spec，確認影響範圍（ARCH 已評估過）
3. 在對應 branch 實作（`agent/{agent_id}/issue-{N}`）
4. 寫測試，確保 Acceptance Criteria 全部通過
5. Push branch → 開 PR，標題格式：`[{agent_id}] {issue title}`

## 原則

- 只改 issue spec 範圍內的檔案
- 不重構無關程式碼
- PR description 列出每個 Acceptance Criteria 是否通過
