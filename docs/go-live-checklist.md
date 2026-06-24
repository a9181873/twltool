# 第一版上線檢查清單

## 主機

- [ ] 建立專用 VM 或容器主機。
- [ ] 安裝 Python 3.12+。
- [ ] 安裝 Playwright 與 Chromium。
- [ ] 確認主機可解析並連線 `www.taiwanlife.com:443`。
- [ ] 確認主機可連線公司 SMTP 或 Power Automate webhook。
- [ ] 系統時區設定為 `Asia/Taipei`。

## 帳號與權限

- [ ] 建立專用帳號 `site-monitor`。
- [ ] `/opt/taiwanlife-monitor` 僅允許維運與該帳號存取。
- [ ] 報表資料夾不可公開下載。
- [ ] SMTP 密碼、Power Automate webhook、SSH 私鑰不可寫入 Git、workflow JSON 或 README。
- [ ] 若使用 SSH node，只允許執行固定 command 或受限 shell。

## 巡檢器

- [ ] `config/taiwanlife.json` 的重要子頁確認符合實際官網路由。
- [ ] 搜尋測試 query 使用業務接受的關鍵字，例如 `壽險`。
- [ ] `ignore_url_keywords` 已排除第三方追蹤、社群與 App Store。
- [ ] `reports/latest.json` 與 `reports/latest.md` 可正常產出。
- [ ] 異常時 Python stdout 最後一行仍是排程器可解析 JSON。
- [ ] stdout payload 包含 `scheduler`、`summary`、`problem_checks`、`latest_json`、`latest_md`、`screenshots`。
- [ ] `config/rpa84_scenarios.json` 已對照 RPA84 文件確認。
- [ ] 若啟用 RPA84，先用截圖或 headful 模式確認 selector 穩定。

## Windows / Power Automate

- [ ] `scripts/run_taiwanlife_monitor.ps1` 可手動執行。
- [ ] Windows Task Scheduler 使用專用帳號執行 wrapper。
- [ ] 排程設定為每 12 小時，且不允許平行 instance。
- [ ] 若使用 Power Automate，`POWER_AUTOMATE_WEBHOOK_URL` 放在環境變數或安全設定。
- [ ] fail/warn 時 Power Automate 能收到 `problem_checks` 並發 Teams/Email/工單。

## n8n

- [ ] Schedule timezone 設為 `Asia/Taipei`。
- [ ] Schedule Trigger 已設定為每 12 小時執行一次。
- [ ] Workflow 只排程、執行、解析 stdout，不使用 n8n Email node。
- [ ] 若用 Execute Command，已確認 n8n 2.x `NODES_EXCLUDE` 未封鎖該節點。
- [ ] 若 n8n 跑 Docker，已確認命令是在 container 內執行，或改用 SSH 呼叫巡檢主機。
- [ ] 測試 fail/warn 條件能輸出 `should_notify_external=true`。

## 告警

- [ ] 收件人包含網站維運、應用系統窗口、值班群組。
- [ ] 主旨包含 `fail`、`warn` 數量。
- [ ] 信件內容包含報表與截圖路徑。
- [ ] 通知內容包含前 10 筆 `problem_checks`。
- [ ] 已定義誤報處理與告警冷卻規則。

## 上線觀察

- [ ] 第一週維持每 12 小時一次，確認告警與報表穩定。
- [ ] 每日檢視 fail/warn 與實際官網狀態。
- [ ] 將穩定誤報加入 ignore list 或調整 timeout。
- [ ] 一週後再提高頻率或增加更多流程測試。
