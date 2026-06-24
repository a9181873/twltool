# twltool 程式審查、截圖封存與 Windows/Microsoft 部署評估

> 歷史文件：此文件保留 2026-06-23 當時的審查結論。最新排程/通知分工請以 `docs/scheduler-integration.md`、`docs/deployment.md`、`docs/go-live-checklist.md` 為準；RPA84 需求對照請看 `docs/rpa84-requirements.md`。

審查日期：2026-06-23  
Git 版本：`0896198`  
範圍：`a9181873/twltool` 最新 `main`

## 執行摘要

- 單元測試通過：`python3 -B -m unittest discover -s tests -v`，12 tests OK。
- 健康檢查通過：`python3 -m taiwanlife_monitor.monitor --health-check`。
- 2026-06-23 完整巡檢已實跑，`run_id=20260623_233646`，結果 `PASS 12 / WARN 0 / FAIL 1`。
- 唯一 FAIL 是壽險保障頁的 Facebook pixel `connect.facebook.net//log/error` 因 `csp` request failed；主頁面本身 HTTP 200、內部連結 120 條全數通過。
- 近期截圖已打包：`reports/downloads/twltool-screenshots-20260619-20260623.zip`，共 21 張 PNG。
- 本次稽核包已打包：`reports/downloads/twltool-run-20260623_233646-audit.zip`，含 JSON、Markdown 與 7 張截圖。

## 專案白話說明

一句話：這個專案是一個「網站自動巡檢機器人」。它會定時打開台灣人壽官網，像人一樣檢查首頁、重要子頁、搜尋功能、內部連結、TLS 憑證與畫面截圖，最後產出報表，必要時通知維運人員。

實際流程：

1. 讀取 `config/taiwanlife.json`，知道要檢查哪些頁面、文字、連結與憑證。
2. 檢查 TLS 憑證還有幾天到期。
3. 用瀏覽器自動打開網站，檢查 HTTP 狀態、標題、關鍵文字。
4. 監聽頁面載入過程，抓壞掉的圖片、JS、CSS、字型、API 請求。
5. 操作站內搜尋，確認搜尋功能有回應。
6. 抽查站內連結，避免重要頁面連到 404/500。
7. 截圖留證，方便人員快速判斷是真異常還是誤報。
8. 輸出 JSON 與 Markdown 報表。
9. watchdog 讀取 `reports/latest.json`，判斷是否漏跑或巡檢異常。
10. 後續可接 Email、Teams、Power Automate、SharePoint 或 Google Drive。

## 使用技術與套件

| 技術/套件 | 用在哪裡 | 白話用途 | 可代替人類做什麼 | 目前注意事項 |
|---|---|---|---|---|
| Python | `taiwanlife_monitor/monitor.py` | 主程式語言，負責串起所有檢查流程 | 不用人每天手動開網站、複製結果、寫報表 | Docker 使用 Python 3.12，本機/OCI 可能是 3.13/3.14，正式環境建議統一版本 |
| Playwright | `requirements.txt` | 自動控制 Chromium 瀏覽器 | 像真人一樣開網頁、點搜尋、截圖 | 已列入依賴；正式機要執行 `playwright install chromium` |
| Chromium | Playwright 啟動 | 實際被操控的瀏覽器 | 模擬使用者看到的畫面 | 容器需足夠 shared memory 與中文字型 |
| JSON 設定檔 | `config/taiwanlife.json` | 把檢查目標集中管理 | 非工程人員也較容易調整頁面清單與關鍵字 | 建議未來補 config schema 驗證 |
| Python 標準函式庫 | `json/pathlib/ssl/smtplib/email/datetime` | 讀寫報表、檢查憑證、寄信、處理時間 | 自動整理資料、產生報告、寄出告警 | 標準函式庫免安裝，穩定性高 |
| OpenSSL CLI | TLS 檢查 | 解析憑證到期日 | 不用人工到瀏覽器點憑證資訊 | Windows 需額外安裝 `openssl.exe` 並放入 PATH |
| Docker / Docker Compose | `Dockerfile`, `docker-compose.yml` | 把執行環境包起來 | 減少「我電腦能跑、正式機不能跑」問題 | Google Drive 腳本目前尚未納入 Docker image |
| n8n | `n8n/taiwanlife-monitor.workflow.json` | 排程、判斷是否告警、寄信 | 不用人工每天看報表再轉寄 | Docker n8n 不能直接跑 host Python，正式環境建議 SSH 或改 Windows/Power Automate |
| Bash watchdog | `scripts/taiwanlife_watchdog.sh` | 檢查最新報表是否過舊或異常 | 自動發現「巡檢沒跑」或「巡檢跑了但失敗」 | 已部署到 OCI；Windows 需改寫成 PowerShell 版 |
| Google Drive API | `scripts/upload_to_drive.py` | 上傳截圖到 Google Drive | 不用人工下載、整理、上傳截圖 | 目前缺 `google-api-python-client` 等依賴，且路徑寫死 `/opt/data/...` |
| SMTP Email | `send_email_alert()` / n8n Email node | 寄送異常通知 | 不用人工通知維運群組 | Python 直寄目前受 `alerts.email.enabled=false` 影響 |
| Power Automate / Teams | 未來建議 | 公司 Microsoft 生態通知與流程自動化 | 自動發 Teams、Email、工單或核准流程 | 建議作為正式遷移方向 |
| Microsoft Graph / SharePoint / OneDrive | 未來建議 | 企業內部檔案保存與通知 API | 自動保存報表截圖到 M365 權限邊界 | 需 Entra App、權限與憑證治理 |
| Git / GitHub | 專案版本控管 | 保存程式修改紀錄 | 方便追蹤誰改了什麼、快速回復 | OCI 曾有 remote URL 內嵌 PAT，需輪替並改安全認證方式 |

## 可以代替人類做到的事情

這個專案最適合代替「固定、重複、容易漏掉」的人工檢查。

可以自動化：

- 每天定時打開台灣人壽官網與重要子頁。
- 確認頁面是否 HTTP 200、標題是否正常、指定文字是否存在。
- 檢查壞圖、壞 JS、壞 CSS、壞字型、API 請求失敗。
- 操作站內搜尋，確認搜尋功能沒有明顯壞掉。
- 抽查內部連結，找出 404/500。
- 檢查 TLS 憑證剩餘天數，避免憑證過期才發現。
- 自動截圖，保留事故當下畫面。
- 產出 JSON/Markdown 報表，方便機器讀取與人類閱讀。
- 判斷是否異常，正常時安靜，異常時通知。
- 將截圖與報表打包或上傳到雲端資料夾。
- 發現巡檢漏跑，例如 14 小時內沒有新報表。

仍需要人類判斷：

- 官網改版後，哪些關鍵字、頁面與流程才算「正確」。
- 第三方追蹤像素、廣告、社群 SDK 失敗時，是否真的影響客戶。
- 截圖畫面是否符合品牌、法遵、使用者體驗要求。
- 異常是否需要開事故、通知哪個單位、是否要升級處理。
- 登入後流程、保戶個資流程、交易流程等高風險操作，需另行設計權限與測試資料。

## 未來優化建議

### 短期：先把暫時任務跑穩

- 補 PowerShell wrapper，讓 Windows Task Scheduler 可直接使用。
- 把 `problem_checks` 加到 stdout payload，讓 Power Automate/Teams 通知可直接顯示異常明細。
- 把 Google Drive API 套件補進 `requirements.txt`，或先停用 Drive upload，避免排程因缺套件失敗。
- 將 Facebook pixel、Google Analytics 等第三方追蹤錯誤改成 warn 或忽略，不要讓主頁面因此 fail。
- 搜尋檢查改成確認 URL 改變、結果列表出現或結果容器可見，降低 false positive。
- 讓 watchdog 成為每次巡檢後的固定步驟。

### 中期：移到公司 Microsoft 生態

- Windows Task Scheduler 每 12 小時跑一次 PowerShell wrapper。
- PowerShell wrapper 讀 `reports/latest.json`，整理出 `ok/summary/problem_checks/report_path/screenshots`。
- 異常時 POST 到 Power Automate webhook。
- Power Automate 發 Teams channel message，必要時寄 Email 或建工單。
- 截圖與報表改存 SharePoint/OneDrive，取代 Google Drive。
- 若公司不允許 webhook，可改成「檔案新增到 SharePoint 後觸發 Flow」。

### 長期：讓它更像正式監控系統

- 加 config schema，啟動前先檢查設定檔格式，避免 typo 讓巡檢失效。
- 失敗時保存 Playwright trace 或 video，方便還原操作過程。
- 加截圖差異比對，偵測畫面大幅跑版。
- 加歷史趨勢報表，例如連續失敗次數、平均載入時間、最常壞的頁面。
- 加 CI/CD：每次改程式自動跑單元測試、JSON 檢查、Docker build。
- 加封存 manifest：每包報表記錄 run_id、commit hash、Python/Playwright 版本、SHA256。
- 把通知分級：warn 給維運群組，fail 連續兩次才升級事故，避免告警疲勞。
- 逐步接 ITSM 工單系統，讓重大異常自動開單、追蹤、結案。

## 主要程式正確性發現

### P0: Google Drive 上傳功能尚未端到端可用

`README.md` 說巡檢後會自動上傳截圖，但目前實作沒有完整串起來：

- `requirements.txt` 只有 `playwright`，但 `scripts/upload_to_drive.py` 需要 `google-api-python-client`、`google-auth`、`google-auth-oauthlib`。
- 實測 `python3 scripts/upload_to_drive.py` 與 `./venv/bin/python scripts/upload_to_drive.py` 都會因 `ModuleNotFoundError: No module named 'google'` 失敗。
- `Dockerfile` 沒有複製 `scripts/`，Docker image 內無法執行上傳腳本。
- n8n workflow 只執行 monitor，沒有在巡檢後呼叫 `scripts/upload_to_drive.py`。
- `scripts/upload_to_drive.py` 寫死 `/opt/data/...`，和 repo 預設 `reports/screenshots`、Docker `/app/reports` 不一致。

補充定位：Google Drive 上傳是 OCI/Hermes 過渡期的便利功能，主要解決「不方便直接查看 OCI 主機檔案」的問題。未來若改部署到公司內部 Windows 電腦，截圖與報表可直接存本機、網路磁碟或 SharePoint/OneDrive，不需要保留 Google Drive 作為核心依賴。

建議：先決定上傳責任歸屬。若保留 Python 腳本，補 dependencies、Dockerfile、環境變數路徑、n8n/cron 後置步驟與測試。

### P0: n8n Docker Execute Command 容易照抄即失敗

workflow 預設 `cd ${MONITOR_WORKDIR:-/opt/taiwanlife-monitor}` 後跑 Python；但 compose 的 n8n service 沒有掛整個 repo 到 `/opt/taiwanlife-monitor`，只有掛 `n8n` 與 `reports`。文件雖建議 Docker n8n 改用 SSH，但 compose 同時提供 `MONITOR_WORKDIR` 等變數，容易造成誤解。

建議：拆成兩份 workflow：`ssh` 正式版與 `local-execute-command` 開發版，並在 README 明確標註 Docker n8n 不直接跑 host Python。

### P1: Python Email 與文件的告警語意不一致

- `config/taiwanlife.json` 的 `alerts.email.enabled=false`，所以單靠 `--email-on-fail` 不會寄信。
- `report["ok"]` 只看 `fail == 0`，warn-only 不會觸發 Python Email。
- README 寫正式環境 `fail` 或 `warn` 都寄送；n8n 有處理 warn，但 Python 端沒有。

建議：統一語意為 `fail > 0 || warn > 0`，或明確標示 Python 直寄只處理 fail。

### P1: n8n 告警明細拿不到 checks

n8n Code node 嘗試從 stdout payload 的 `checks` 組異常明細，但 `monitor.py` 最後印出的 payload 沒有 `checks`，只有完整報表 JSON 內才有。實務上 Email 會有摘要，但缺少失敗項目細節。

建議：stdout payload 加上 `problem_checks` 前 10 筆，讓 n8n、Power Automate 或 Teams 通知都能直接顯示異常明細。

### P1: 搜尋檢查有誤判風險

搜尋後只要 body/title/url 含任一 expected text 就 pass，但 `壽險`、`壽險保障` 可能在首頁或導覽原本就存在。若搜尋沒有真的送出，也可能被判通過。

建議：至少檢查 `after_url != before_url`、搜尋結果容器、結果列表筆數，或明確等待結果頁 selector。

### P2: TLS 檢查依賴 `openssl` CLI

`run_ssl_check()` 使用 `ssl.get_server_certificate()` 取 PEM 後呼叫 `openssl x509`。Windows 原生部署必須安裝 `openssl.exe` 並放入 `PATH`；若 `openssl` timeout 或不存在，暫存檔清理也建議改成 `try/finally`。

建議：短期補 Windows 文件與 `returncode` 檢查；中期改用 Python 憑證解析套件降低環境差異。

## 截圖與報表封存

已確認截圖皆為 1920x1080 PNG。

- 2026-06-19 兩輪：`20260619_214942_*`、`20260619_215104_*`，共 14 張。
- 2026-06-23 一輪：`20260623_233646_*`，共 7 張。
- 近期截圖包：`reports/downloads/twltool-screenshots-20260619-20260623.zip`
- 本次稽核包：`reports/downloads/twltool-run-20260623_233646-audit.zip`

SHA256:

- `032feed6f2d87db3f2a114b1a26d7410ac573efc6ab6cfbcbb6a8870b94c5f6e  reports/downloads/twltool-screenshots-20260619-20260623.zip`
- `4098b7fe36238b6bf4217967f1bd41df5a86b6fd5b9275bb23f3775ff5feddae  reports/downloads/twltool-run-20260623_233646-audit.zip`

建議下一步把封存流程正式化成腳本：每次巡檢產生 `<run_id>.zip`，內容含 JSON、Markdown、截圖、manifest、SHA256、Git commit、Python/Playwright 版本。

## Windows Task Scheduler 可行性

可行，建議 Task Scheduler 只負責啟動 PowerShell wrapper。

前置需求：

- Python 3.12 64-bit。
- `python -m venv venv`
- `venv\Scripts\python.exe -m pip install -r requirements.txt`
- `venv\Scripts\python.exe -m playwright install chromium`
- OpenSSL CLI 放入 `PATH`。
- 若保留 Google Drive upload，需額外安裝 Google API dependencies，並修正硬編 Linux 路徑。

建議 wrapper：

```powershell
Set-Location C:\twltool
.\venv\Scripts\python.exe -m taiwanlife_monitor.monitor --config config\taiwanlife.json --output-dir reports --fail-exit-code
$monitorExit = $LASTEXITCODE

# Windows 版可用 PowerShell 改寫同等檢查；Linux/Hermes 先用 shell watchdog。
# bash scripts/taiwanlife_watchdog.sh reports/latest.json

# 若已修正 dependencies 與路徑，再啟用
# .\venv\Scripts\python.exe scripts\upload_to_drive.py

exit $monitorExit
```

Task Scheduler 設定：

- Trigger：每 12 小時。
- Action：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\twltool\run-monitor.ps1`
- Start in：`C:\twltool`
- 勾選：Run whether user is logged on or not。
- 帳號：專用 AD/local service account，授予 Log on as batch job。
- Instance policy：Do not start a new instance，避免同時寫入 `reports/latest.json`、截圖與 token。
- Timeout：30 到 60 分鐘。

## Microsoft 內部通知整合建議

推薦路線：Power Automate / Teams Workflows 作為主要通知層，SMTP 作為備援，Graph sendMail 作為正式化 Email 通道。

方案比較：

| 方案 | 優點 | 風險/成本 | 建議 |
|---|---|---|---|
| SMTP Email | 專案已內建，n8n workflow 已支援 | Python 直寄目前被 config 關閉；需 SMTP send-only 帳號 | 短期備援 |
| Teams Incoming Webhook | HTTP POST 最簡單 | Microsoft 365 Connectors 逐步退場，新建受限 | 不建議新建 |
| Power Automate / Teams Workflows | 符合 M365 治理，可發 Teams、Email、工單 | Flow owner、DLP、授權要管 | 主要推薦 |
| Microsoft Graph sendMail | 不依賴 SMTP，可用 Entra App 管控 | 需 App Registration、Mail.Send、憑證輪替 | 正式化 Email |
| n8n Microsoft Teams node | 可沿用現有 n8n 編排 | Docker n8n 不適合直接 Execute Command host Python | 公司已有 n8n 時可用 |
| SharePoint/OneDrive via Graph | 截圖留在 M365 權限邊界 | 需實作上傳與權限設計 | 中期取代 Google Drive |

落地順序：

1. Windows Task Scheduler 跑 monitor，PowerShell wrapper 讀最後 JSON 或報表 JSON。
2. wrapper 在 `fail > 0 || warn > 0` 時 POST 到 Power Automate webhook。
3. Power Automate 發 Teams channel message，並視情況寄 Graph/Exchange Email。
4. 中期把 Google Drive upload 換成 SharePoint/OneDrive via Graph。
5. 若保留 n8n，建議讓 Task Scheduler 呼叫 n8n webhook，或 n8n 用 SSH 呼叫巡檢主機；不要讓 Docker n8n 直接 Execute Command 跑 host Python。

## OCI Hermes Agent 現況

檢查時間：2026-06-23 23:40 台北時間左右。

主機與容器狀態：

- OCI 主機：`UbuntuJY91818`，已連續運作約 74 天，load average 約 `0.00/0.01/0.00`。
- 磁碟：`/` 使用約 42%，可用約 114 GB。
- 記憶體：23 GiB，available 約 18 GiB；swap 8 GiB，已用約 798 MiB。
- `hermes` container：running，約 47 小時，restart count 0，掛載 `/home/ubuntu/.hermes -> /opt/data`。
- `hermes-chromium` container：running 且 health=healthy，已運作約 5 週。
- `twltool` 實際路徑：host `/home/ubuntu/.hermes/twltool`，container 內為 `/opt/data/twltool`。

twltool 狀態：

- 遠端 repo 版本：`0896198`，工作樹乾淨。
- 最新報表：`run_id=20260623_180050`。
- 最新巡檢時間：2026-06-23 18:00:50 至 18:02:41 台北時間。
- 結果：`PASS 13 / WARN 0 / FAIL 0`。
- 最新報表截圖：7 張。
- 最近報表持續產出，包含 2026-06-20 至 2026-06-23 多次結果。

Hermes cron 狀態：

- 排程名稱：`台壽官網巡檢（twltool 版）`。
- Job ID：`a2e1e02c3c6a`。
- 狀態：enabled、scheduled。
- 排程：UTC `0 1,10 * * *`，等於台北時間每日 09:00、18:00。
- 最近執行：2026-06-23 10:02:43 UTC，last_status=`ok`。
- 下一次執行：2026-06-24 01:00:00 UTC，也就是台北時間 2026-06-24 09:00。

OCI 端主要風險：

- Git remote URL 內嵌 GitHub Personal Access Token。這是高風險，應立即輪替該 token，並改成 SSH remote 或 Git credential helper。
- Hermes compose 使用 `network_mode: host`，Hermes dashboard 以 insecure 模式啟動，且 `9119` 監聽 `0.0.0.0`。n8n 也監聽 `*:5678`。即使 OCI Security List/防火牆可能有擋，仍建議改成 localhost bind 或只允許 Cloudflare Access/VPN/管理 IP。
- 原本 `/home/ubuntu/.hermes/scripts/taiwanlife_watchdog.sh` 是舊版 watchdog，仍檢查 `/opt/data/site-checks/taiwanlife/run.log`；2026-06-23 已改成讀 `twltool/reports/latest.json`，但仍需確認 Hermes cron 或後續 wrapper 會實際呼叫它。
- `twltool` container/venv 內可 import Playwright，但缺 `googleapiclient`。Hermes 日誌曾有 Drive 上傳成功紀錄，但目前依賴狀態不穩，下一次執行 `python3 scripts/upload_to_drive.py` 有機會因缺套件失敗。
- Hermes logs 有 DeepSeek API 連線 reset/stale stream、web extract backend、raft CLI not found、工具權限阻擋等 warning；不直接影響 twltool 最新巡檢，但應做日誌輪替與 provider fallback 觀察。

OCI 建議：

OCI Hermes 只建議當暫時執行端，不建議在此階段投入太多平台化工程。必要處理以安全、不中斷與可移植為原則：

1. 立即輪替 GitHub PAT，移除 remote URL 內嵌 token，改用 SSH deploy key 或 credential helper。
2. 收斂對外埠：`9119` Hermes dashboard、`5678` n8n 只允許 localhost、VPN、Cloudflare Access 或固定管理 IP。
3. 修 Drive upload 依賴：把 Google API 套件加入 `requirements.txt`，在 OCI `/opt/data/twltool/venv` 安裝，並把 Hermes cron 第 3 步改成 `./venv/bin/python scripts/upload_to_drive.py`。
4. 暫時版 watchdog 只需檢查 `/opt/data/twltool/reports/latest.json` 是否在 14 小時內更新，以及 `summary.fail/warn` 是否異常；不要在 Hermes 上擴充太多客製化邏輯。
5. 若要調整 Hermes cron，優先改成呼叫可攜式 shell wrapper，讓同一套流程未來可搬到 Windows PowerShell wrapper 或 Power Automate。
6. 保留目前每日 09:00/18:00 巡檢頻率；若要提升頻率，先和 WAF/SOC 確認來源 IP、User-Agent 與流量上限。

## Watchdog 改寫

已新增 `scripts/taiwanlife_watchdog.sh`，改讀 `reports/latest.json` 判斷是否漏跑或異常。2026-06-23 已同步部署到 OCI `/home/ubuntu/.hermes/scripts/taiwanlife_watchdog.sh`，舊版腳本已先備份。

檢查項目：

- `reports/latest.json` 是否存在且可解析。
- `finished_at` 或 `started_at` 是否超過 `MAX_AGE_HOURS`，預設 14 小時。
- `summary.fail` 是否大於 0。
- `summary.warn` 是否大於 0，預設視為異常，可用 `WARN_IS_FAILURE=0` 放寬。
- `screenshots` 數量是否小於 `MIN_SCREENSHOTS`，預設 7 張。

Hermes/OCI 用法：

```bash
cd /opt/data/twltool
MAX_AGE_HOURS=14 MIN_SCREENSHOTS=7 ./scripts/taiwanlife_watchdog.sh reports/latest.json
```

建議 Hermes cron 從 prompt 直接跑多段指令，逐步改成呼叫 wrapper：

```bash
cd /opt/data/twltool
./venv/bin/python -m taiwanlife_monitor.monitor --config config/taiwanlife.json --output-dir reports
./scripts/taiwanlife_watchdog.sh reports/latest.json
```

Windows 移植時，建議用 PowerShell 寫同等邏輯讀 `reports/latest.json`；不要長期依賴 bash。

## 鎖定 9119/5678 對外存取影響

目前觀察：

- `9119`：Hermes dashboard，正在 `0.0.0.0:9119` 監聽，且 compose 設 `HERMES_DASHBOARD_INSECURE=1`。
- `5678`：n8n UI/API，正在 `*:5678` 監聽。
- `80/443`：由 Caddy 對外服務，可能負責正式入口與反向代理。
- `9222`：Chromium CDP 只在 `127.0.0.1:9222`，目前較安全，不建議對外。

2026-06-23 外部探測：

- `http://144.24.11.149:9119`：外部連線逾時，推測 OCI Security List、防火牆或上游網路已阻擋。
- `http://144.24.11.149:5678`：外部可連，回 `HTTP 200 OK`，代表 n8n UI 目前可從公網直連。
- OCI localhost：`127.0.0.1:9119` 與 `127.0.0.1:5678` 都可連，表示只封外部不會影響本機健康檢查、Caddy 反代或 SSH tunnel。

鎖 `9119` 的影響：

- 會阻止外部直接打開 Hermes dashboard。
- 不應影響 Hermes gateway/container 本身執行、cron、twltool 巡檢或 Chromium sidecar。
- 若你平常從瀏覽器直接連 `http://OCI_IP:9119` 管理 Hermes，鎖定後需改用 SSH tunnel、VPN 或 Cloudflare Access。

鎖 `5678` 的影響：

- 會阻止外部直接打開 n8n UI、API 與 webhook。
- 若已有外部 webhook 指到 `http://OCI_IP:5678/...`，會中斷。
- 若 n8n 是透過 Caddy/Cloudflare Access 的正式網域進入，且 Caddy 在同機反代 `localhost:5678`，則建議讓 n8n 只綁 `127.0.0.1:5678`，外部只走 443。
- 以目前探測結果，`5678` 是真正需要優先收斂的外露面。

建議做法：

1. 先查是否有外部 webhook 直接打 `:5678`；若沒有，將 n8n bind 改成 `127.0.0.1` 或用防火牆只允許 localhost/管理 IP。若有 webhook，先改到 443/Caddy/Cloudflare Access 或 Power Automate 入口，再封 5678。
2. Hermes dashboard `9119` 建議預設不對公網開放；維運時用 SSH tunnel：

```bash
ssh -L 9119:127.0.0.1:9119 oci
```

3. 若需要遠端 UI，優先用 Cloudflare Access/VPN，避免裸露 insecure dashboard。
4. 變更前先保留一個 SSH session；變更後測：

```bash
curl -I http://127.0.0.1:9119
curl -I http://127.0.0.1:5678
```

5. 對外驗證應從非 OCI 主機測 `OCI_IP:9119`、`OCI_IP:5678` 是否拒絕連線。

## 過渡與移植策略

此專案目前屬於暫時任務。建議把 OCI Hermes 定位為「短期代跑與驗證環境」，最終交付形態以 Windows Task Scheduler 或 Power Automate 為主。

建議採用三層切分，讓遷移成本最低：

1. **核心巡檢層**：保留 `python -m taiwanlife_monitor.monitor`，只負責檢查、截圖、JSON/Markdown 報表。
2. **工作包裝層**：新增可攜式 wrapper，負責排程入口、lock、防重跑、打包、讀取結果、決定是否通知。
3. **通知與保存層**：短期 Google Drive/Email 可用；正式環境改 Power Automate/Teams/SharePoint 或 Graph。

Windows 目標路線：

- Phase 1：OCI Hermes 繼續每日 09:00/18:00 跑，補安全與 Drive upload 缺口。
- Phase 2：建立 Windows PowerShell wrapper，手動跑通一次完整流程。
- Phase 3：用 Windows Task Scheduler 每 12 小時觸發 wrapper。
- Phase 4：PowerShell wrapper 呼叫 Power Automate webhook，發 Teams/Email。
- Phase 5：將截圖與報表上傳目標從 Google Drive 改成 SharePoint/OneDrive。

Power Automate 目標路線：

- 若公司允許 HTTP webhook：Windows wrapper POST 巡檢摘要到 Power Automate，由 Flow 發 Teams 與 Email。
- 若公司不允許外部 webhook：改由 Windows 排程寫入 SharePoint/OneDrive 指定資料夾，Power Automate 以檔案新增事件觸發通知。
- 若要完全企業治理：使用 Entra App + Microsoft Graph 上傳檔案與 sendMail，但實作成本較高。

我建議先做「Windows Task Scheduler + PowerShell wrapper + Power Automate 通知」這條線，因為最符合公司內部 Microsoft 解決方案，且不需要長期依賴 Hermes agent 的 prompt 排程。

## 建議優先級

1. 先處理 OCI 安全缺口：輪替 GitHub PAT、收斂 `9119/5678` 對外存取。
2. 補一個可攜式 wrapper，讓 Hermes、Windows Task Scheduler 都能呼叫同一套巡檢流程。
3. 修告警契約：stdout payload 補 `problem_checks`，PowerShell/Power Automate 可直接讀。
4. 加封存腳本，固定產出可下載 zip 與 manifest。
5. 強化搜尋檢查，避免 false positive。
6. 補 Windows 部署文件：OpenSSL、Proxy、服務帳號、Task Scheduler、Power Automate webhook。
7. 中期改用 SharePoint/OneDrive + Graph 取代 Google Drive。
