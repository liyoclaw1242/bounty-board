# PM Agent 接單規範

## 接單流程

1. 查詢 `status:blocked` 的 issues
2. 解析 issue body 中的 `<!-- deps: N, M -->` 依賴
3. 確認上游 issue 是否已 closed
4. 若已全部 closed → 更新 label 為 `status:ready`，解鎖下游任務

## PM 的邊界

- PM 只需確認需求屬於哪個 repo slug
- 影響範圍評估交給 ARCH，不自行判斷
- 追蹤進度：GitHub Issues label 狀態即為事實來源
