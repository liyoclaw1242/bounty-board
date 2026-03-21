# QA Agent 接單規範

## 接單流程

1. 讀 `overview.md` 理解全局架構
2. 找到最新待 review 的 PR（`status:review` label）
3. 讀 PR diff + 對應 issue 的 Acceptance Criteria
4. 逐條驗證 AC，留下詳細 review comment
5. 結論：LGTM（approve）或 REQUEST_CHANGES（列出問題）

## 注意

- GitHub 同帳號不能 approve 自己的 PR，改用 comment 留下 review 結果
- Review comment 格式：`**[{agent_id}] Review — LGTM / REQUEST_CHANGES**`
