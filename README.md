# 台灣人壽官網巡檢工具

這個資料夾已整理成可部署的巡檢專案：Python 負責實際檢查，排程可由 Windows Task Scheduler、Power Automate、n8n、Docker 或 cron 觸發。主程式在 `taiwanlife_monitor/monitor.py`，RPA84 官網功能需求也由同一套巡檢核心執行。

## 巡檢管理後台

不使用 LLM API。使用者可透過本機網頁管理頁面巡檢、搜尋檢查、SSL、連結檢查、自訂流程，並查看 `reports/latest.json` 與觸發試跑。

```powershell
.\scripts\run_flow_editor.ps1
```

Windows、OCI 與 Docker Compose 部署方式見 `docs/flow-editor-ui.md`。

## 監控內容

- 首頁與關鍵子頁 HTTP/標題/關鍵文字檢查
- 頁面載入過程的壞圖、壞 JS、壞 CSS、XHR/Fetch 失敗
- 站內搜尋流程，預設查詢 `壽險`
- 內部連結抽查，預設最多 120 條
- TLS 憑證到期天數
- JSON 與 Markdown 報表，並保留截圖
- SMTP Email 告警，也可由 Windows wrapper 轉送 Power Automate / Teams
- RPA84 官網功能自動檢查需求清單與可逐步啟用的場景設定

巡查不是單純寫死網址。現況採混合模式：

- `pages` 固定放必看頁面，確保首頁、商品、理賠、投資、據點、新聞等關鍵頁一定被檢查。
- `link_crawl` 從種子頁動態抓站內連結，預設最多抽查 120 條，官網新增連結也有機會被巡到。
- RPA84 是業務流程檢查，會用 `rpa84.scenarios` 描述「要怎麼點、怎麼填、怎麼判斷成功」。
- `allowed_hosts` 是共用主機清單；未設定 `ssl.hosts` 或 `link_crawl.include_hosts` 時會自動沿用它。
- `global_timeout_seconds` 預設 1800 秒；會在主要階段與各 browser check 之間停止後續工作，已進行中的 Playwright 操作仍由 browser timeout 控制。

## 技術與用途

這個專案是「官網自動巡檢機器人」。它會定時打開網站、檢查功能、截圖存證、產出報表，減少人工每天巡站。

| 技術/套件 | 用途 | 代替人工做到的事 |
|---|---|---|
| Python | 主程式與報表產生 | 自動執行巡檢流程、整理結果 |
| Playwright | 控制 Chromium 瀏覽器 | 像真人一樣開網頁、搜尋、截圖 |
| Chromium | 實際瀏覽器 | 呈現真實網頁畫面 |
| `config/taiwanlife.json` | 巡檢設定 | 集中管理頁面、關鍵字、憑證、連結檢查與 RPA84 場景 |
| OpenSSL | TLS 憑證到期檢查 | 自動提醒憑證是否快過期 |
| JSON/Markdown | 報表格式 | 同時給機器讀、給人看 |
| `scripts/taiwanlife_watchdog.sh` / `.ps1` | 漏跑與異常檢查 | 發現巡檢沒跑、報表過舊、fail/warn |
| Docker | 固定執行環境 | 降低部署環境差異 |
| n8n | 排程與執行 | 呼叫同一支 Python CLI，不負責寄信 |
| Windows Task Scheduler | 公司內部排程 | 定時啟動 PowerShell wrapper |
| Power Automate / Teams | 通知與後續流程 | 異常時自動發 Teams、Email 或工單 |

## 能取代的人工作業

- 定時開官網與重要子頁。
- 檢查頁面是否正常、文字是否存在。
- 檢查壞圖、壞 JS、壞 CSS、API 請求失敗。
- 操作站內搜尋。
- 抽查內部連結是否 404/500。
- 檢查 TLS 憑證剩餘天數。
- 截圖存證。
- 產生報表。
- 判斷是否漏跑或異常。
- 異常時通知維運人員。

仍需人工判斷：官網改版後檢查規則是否要調整、第三方追蹤錯誤是否影響客戶、異常是否需要升級事故。

## 後續優化方向

- 補齊 RPA84 其餘流程的自動點擊、輸入、驗證步驟，逐步打開更多功能場景。
- 報表與截圖改存 SharePoint/OneDrive。
- 搜尋檢查改成確認結果頁或結果列表，降低誤判。
- 第三方追蹤像素錯誤改成 warn 或忽略，避免不必要 fail。
- 增加 ZIP/manifest 封存，方便稽核與交接。
- 進一步建議見 `docs/optimization-recommendations.md`。

## 本機安裝

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/playwright install chromium
```

開發品質工具為選用：

```bash
./venv/bin/pip install -r dev-requirements.txt
```

基本回歸測試仍只依賴 Python 標準函式庫 `unittest`。

執行：

```bash
./venv/bin/python -m taiwanlife_monitor.monitor --config config/taiwanlife.json --output-dir reports
```

異常時直接由 Python 寄信需明確啟用 SMTP：

```bash
cp .env.example .env
set -a
. ./.env
set +a
export ALERT_EMAIL_ENABLED=true
./venv/bin/python -m taiwanlife_monitor.monitor --config config/taiwanlife.json --output-dir reports --email-on-fail
```

## RPA84 功能流程

RPA84 已直接整合進 `config/taiwanlife.json` 的 `rpa84.scenarios`。

- `monitor.py` 還是唯一巡檢核心。
- `config/taiwanlife.json` 同時管理一般巡檢與 RPA84 場景。
- `rpa84.enabled=false` 是正式排程保護開關，不代表需求不能做。
- 截圖是執行結果證據；自動化真正執行的是 `steps`，也就是開頁、點擊、輸入、送出、驗證文字或結果。
- 已有 `steps` 的場景可由現在架構執行；尚未有 `steps` 的場景會先列為需求項目，再補成可執行步驟。
- 可用 CLI 或環境變數啟用：

```bash
python -m taiwanlife_monitor.monitor --config config/taiwanlife.json --output-dir reports --enable-rpa84
```

或：

```bash
MONITOR_ENABLE_RPA84=true python -m taiwanlife_monitor.monitor --config config/taiwanlife.json --output-dir reports
```

第一版已把所有 RPA84 需求放進主設定，其中「搜尋全站：醫療」已具備可執行步驟。其餘商品、試算、查詢、收藏、匯出等流程會在同一套 `monitor.py` runner 內補齊點擊、輸入、驗證，以及測試帳號或副作用清理規則後啟用。

## n8n 整合

匯入 `n8n/taiwanlife-monitor.workflow.json`。流程是：

1. Schedule Trigger 每 12 小時啟動。
2. Execute Command 執行 Python 巡檢。
3. Code 節點解析 Python stdout 最後一行 JSON。
4. 將摘要留在 n8n execution log。

此 workflow 不使用 n8n Email 節點；通知建議交給 Python SMTP、Windows wrapper + Power Automate、Teams Workflows 或公司既有告警系統。

n8n 官方文件指出 Execute Command 會在 n8n 所在主機執行；如果 n8n 跑在 Docker 裡，命令會在 n8n container 內執行，不會在 Docker host 上執行。因此正式部署有兩個建議：

- n8n 與 Python 巡檢器同機非 Docker 部署：直接使用匯入範本。
- n8n 使用 Docker：用 SSH node 呼叫巡檢主機，或自製含 Python/Playwright 的 n8n image。

n8n 2.0 起 Execute Command 預設封鎖；若要啟用，`NODES_EXCLUDE` 要移除 `n8n-nodes-base.executeCommand`，範例 compose 已設為 `NODES_EXCLUDE=[]`。只建議在內部受控環境啟用。

## Docker

只跑 Python 巡檢：

```bash
docker compose run --rm taiwanlife-monitor
```

啟動 n8n：

```bash
docker compose up -d n8n
```

## Windows / Power Automate

Windows Task Scheduler 建議只負責呼叫 wrapper：

```powershell
.\scripts\run_taiwanlife_monitor.ps1
```

需要啟用 RPA84：

```powershell
.\scripts\run_taiwanlife_monitor.ps1 -EnableRpa84
```

若要由 Power Automate / Teams Workflows 通知，在環境變數設定：

```powershell
$env:POWER_AUTOMATE_WEBHOOK_URL="https://..."
.\scripts\run_taiwanlife_monitor.ps1
```

wrapper 只會在 `fail > 0` 或 `warn > 0` 時 POST 最新 stdout payload，payload 內含 `summary`、`problem_checks`、`latest_json`、`latest_md`、`screenshots`。

可用下列腳本建立 Windows 排程：

```powershell
.\scripts\register_windows_task.ps1 -TaskName TaiwanLifeWebsiteMonitor -HoursInterval 12
# 若要排程每次執行前先檢查上一份 latest.json：
.\scripts\register_windows_task.ps1 -TaskName TaiwanLifeWebsiteMonitor -HoursInterval 12 -RunWatchdogBefore
```

## 報表位置

- 最新 JSON：`reports/latest.json`
- 最新 Markdown：`reports/latest.md`
- 歷史報表：`reports/results/`
- 截圖：`reports/screenshots/`
- 預設保留期限：報表 90 天、截圖 90 天，可在 `config/taiwanlife.json` 的 `retention` 調整。

## 截圖邏輯

完整巡檢通常會產生 7 張截圖：6 個指定頁面各 1 張，加上站內搜尋結果 1 張。這 7 張是「固定巡檢畫面存證」，不是只在錯誤時才截。

檔名規則：

```text
reports/screenshots/<run_id>_<page_id>.png
```

範例：

- `20260623_233646_home.png`
- `20260623_233646_product-life.png`
- `20260623_233646_claim-online.png`
- `20260623_233646_interest-rate.png`
- `20260623_233646_service-location.png`
- `20260623_233646_news.png`
- `20260623_233646_search.png`

固定頁面截圖時間點：

1. 開啟頁面，等待頁面基本載入完成。
2. 嘗試等待網路閒置，預設最多 15 秒；等不到也會繼續。
3. 讀取頁面標題與文字。
4. 檢查標題、必要文字、HTTP 狀態、壞圖、壞 JS、壞 CSS、XHR/Fetch 失敗。
5. 截取目前瀏覽器視窗畫面。
6. 將截圖路徑寫入 JSON/Markdown 報表。

站內搜尋截圖時間點：

1. 開啟首頁。
2. 找到搜尋框。
3. 輸入預設關鍵字 `壽險` 並送出。
4. 等待搜尋結果或頁面回應。
5. 檢查搜尋後的網址、標題與預期文字。
6. 截取搜尋後目前瀏覽器視窗畫面。
7. 將截圖路徑寫入 JSON/Markdown 報表。

目前截圖是「目前視窗範圍」，不是整頁長截圖。`config/taiwanlife.json` 可用 `full_page_screenshot` 控制是否整頁截圖；目前設定皆等同 `false`。

異常證據目前怎麼留：

| 項目 | 目前證據 | 截圖狀態 | 下一步建議 |
|---|---|---|---|
| TLS 憑證檢查 | `host`、剩餘天數、到期門檻、錯誤訊息 | 不截圖，因為這不是網頁畫面問題 | 保留 JSON 證據即可 |
| 內部連結抽查 | 異常 URL、HTTP status、錯誤類型 | 目前不截目的頁，因為程式用 HTTP request 抽查，沒有開瀏覽器頁面 | 異常時補截前幾個壞連結的目的頁畫面 |
| console error | 來源頁面、console 錯誤文字 | 來源頁面已有固定截圖，但未針對 console error 另截一張 | 將 console error 明細綁到該頁 evidence |
| 壞圖、壞 JS、壞 CSS、XHR/Fetch 失敗 | 來源頁面、資源 URL、status、資源類型 | 來源頁面已有固定截圖，單一資源本身不一定有畫面 | 異常時在報表加強標示來源頁截圖 |

也就是說，錯誤一定要有證據；目前證據分成「畫面截圖」與「結構化錯誤資料」。最需要補強的是內部連結異常時的目的頁截圖，以及 console error 與來源截圖的對應關係。

截圖失敗時不會中斷整次巡檢，會記錄 `screenshot_error`，該檢查至少標記為 `warn`。

## Watchdog 漏跑與異常檢查

`scripts/taiwanlife_watchdog.sh` 會讀取 `reports/latest.json`，檢查最新巡檢是否過舊、是否有 fail/warn、截圖數是否不足。適合放在 Hermes cron、Windows wrapper 或 Power Automate 前置檢查。

```bash
./scripts/taiwanlife_watchdog.sh reports/latest.json
```

可調整參數：

```bash
MAX_AGE_HOURS=14 MIN_SCREENSHOTS=7 WARN_IS_FAILURE=1 ./scripts/taiwanlife_watchdog.sh reports/latest.json
```

Windows 可用 PowerShell 版：

```powershell
.\scripts\taiwanlife_watchdog.ps1 -ReportPath reports\latest.json -WarnIsFailure
.\scripts\run_taiwanlife_monitor.ps1 -RunWatchdogBefore
```

退出碼：

- `0`：最新報表正常。
- `1`：漏跑、JSON 無法解析、報表過舊、fail/warn 或截圖不足。

## 架構與上線文件

- 架構藍圖：`docs/architecture-blueprint.md`
- 部署說明：`docs/deployment.md`
- 第一版上線檢查清單：`docs/go-live-checklist.md`
- RPA84 步驟新增方式：`docs/rpa84-step-authoring.md`
- 優化建議：`docs/optimization-recommendations.md`

## 建議排程

正式環境建議：

- 每 12 小時執行一次完整巡檢。
- 巡檢後執行 watchdog，確認 `reports/latest.json` 新鮮且無 fail/warn。
- Email 僅在 `fail` 或 `warn` 發生時寄送。
- 若未來要提高頻率，先和 WAF/SOC 團隊確認來源 IP、User-Agent 與流量上限。

## 目前監視網頁列表與標題目錄

以下內容依據 `config/taiwanlife.json` 目前設定整理；若設定檔異動，這裡也要同步更新。

基準網址：`https://www.taiwanlife.com/`

| ID | 頁面/標題目錄 | 路徑 | 完整網址 | 預期標題包含 | 必須出現的文字 |
|---|---|---|---|---|---|
| `home` | 首頁 | `/` | `https://www.taiwanlife.com/` | `台灣人壽` | 商品資訊、保戶服務、投資資訊、網路投保、商品快搜、最新消息、服務據點 |
| `product-life` | 壽險保障 | `/product-personal-life-TermLife` | `https://www.taiwanlife.com/product-personal-life-TermLife` | `台灣人壽` | 壽險保障、篩選條件、定期壽險 |
| `claim-online` | 理賠申請 | `/service-claim-online-e-claimsservice-claim-file-person` | `https://www.taiwanlife.com/service-claim-online-e-claimsservice-claim-file-person` | `台灣人壽` | 理賠申請、線上申請、紙本申請 |
| `interest-rate` | 宣告利率 | `/investment-rate-interest-rate` | `https://www.taiwanlife.com/investment-rate-interest-rate` | `台灣人壽` | 宣告利率、投資資訊 |
| `service-location` | 服務據點 | `/service-center-service-location` | `https://www.taiwanlife.com/service-center-service-location` | `台灣人壽` | 服務據點、客戶協助 |
| `news` | 新聞中心 | `/news` | `https://www.taiwanlife.com/news` | `台灣人壽` | 新聞中心 |

其他檢查：

- 站內搜尋：查詢 `壽險`，預期看到 `壽險`、`搜尋結果`、`商品項目` 或 `壽險保障`。
- 內部連結抽查：從 `/`、`/product-personal-life-TermLife`、`/service-claim-online-e-claimsservice-claim-file-person`、`/news` 收集連結，預設最多抽查 120 條。
- TLS 憑證：未設定 `ssl.hosts` 時沿用 `allowed_hosts`，目前檢查 `www.taiwanlife.com`、`ezbao.taiwanlife.com`、`customer.taiwanlife.com`、`consultancyservice.taiwanlife.com`、`accessibility.taiwanlife.com`。
