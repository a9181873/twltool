# 優化建議

本文件整理目前功能可延伸的優化方向。排程器仍只負責觸發，巡檢核心維持 `taiwanlife_monitor/monitor.py`，通知不使用 n8n Email。

## P0：先做

1. RPA84 頁面元素辨識
   - 優先使用 Playwright 語意 locator，例如 role、label、text；必要時再要求官網加 `data-testid`。
   - 避免只依賴很長的 CSS 路徑或頁面版位。
   - 來源：<https://playwright.dev/python/docs/locators>

2. 失敗證據包
   - fail/warn 時保留 full-page screenshot、stdout payload、`reports/latest.json`。
   - 後續可加入 Playwright trace zip，方便用 Trace Viewer 重播失敗當下。
   - 來源：<https://playwright.dev/python/docs/trace-viewer>、<https://playwright.dev/python/docs/screenshots>

3. Windows 防重入與重試
   - Task Scheduler 已設定 `MultipleInstances=IgnoreNew`，避免慢回應時新舊巡檢重疊。
   - 可再評估 `RestartCount` / `RestartInterval`，只補救短暫網路或瀏覽器啟動失敗；業務驗證 fail 應直接告警。
   - 來源：<https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-multipleinstances>、<https://learn.microsoft.com/en-us/windows/win32/taskschd/tasksettings-restartcount>

4. Secret 與 Git remote
   - Power Automate webhook、SMTP、SSH key、n8n encryption key 不寫入 Git。
   - OCI/GitHub remote 不得含 PAT；改用 deploy key 或 credential helper。
   - 來源：<https://docs.n8n.io/external-secrets/>、<https://docs.docker.com/compose/how-tos/use-secrets/>

## P1：穩定化

1. n8n 執行模式收斂
   - n8n 可排程與執行，但不寄通知。
   - Docker n8n 正式環境建議用 SSH node 呼叫巡檢主機；Execute Command 只適合同機受控環境。
   - 來源：<https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.ssh/>、<https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executecommand/>

2. 告警降噪
   - 以 `problem_checks.id`、URL、scenario id 或錯誤訊息建立錯誤指紋。
   - 同一錯誤可設定冷卻時間，或連續 N 次失敗才升級事故。
   - n8n 若只作編排，可用 Error Workflow 轉接既有告警系統，但不存 SMTP 密碼。
   - 來源：<https://docs.n8n.io/flow-logic/error-handling/>

3. Docker/OCI image 穩定性
   - 後續可評估改用官方 Playwright Python image 並 pin 版本，減少 `playwright install --with-deps` 的系統相依差異。
   - 容器長期服務才使用 restart policy；一次性巡檢維持 scheduler 觸發即可。
   - 來源：<https://playwright.dev/python/docs/docker>、<https://docs.docker.com/engine/containers/start-containers-automatically/>

4. Power Automate 時區與併發
   - Scheduled cloud flow 明確設定 Time zone。
   - 若改由 Power Automate 觸發 webhook，要確認 trigger concurrency 與佇列限制。
   - 來源：<https://learn.microsoft.com/en-us/power-automate/run-scheduled-tasks>、<https://learn.microsoft.com/en-us/power-automate/limits-and-config>

## P2：治理與稽核

1. Artifact manifest
   - 每次巡檢輸出 manifest，列出 JSON、Markdown、截圖、trace、版本、commit、scheduler。
   - 可再打包 zip，方便稽核或事故回溯。

2. RPA84 分級啟用
   - L1/L2/L3 每 12 小時跑一次。
   - RPA84 計算、收藏、匯出、寄送等副作用流程改成較低頻率，並使用測試帳號或可回復資料。

3. 報表保存正式化
   - 目前報表與截圖都是 90 天。
   - 若要異常截圖 180 天，需要先標記 abnormal artifact，再調整 retention 清理。
