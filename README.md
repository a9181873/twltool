# 台灣人壽官網巡檢工具

這個資料夾已整理成可部署的巡檢專案：Python 負責實際檢查，n8n 負責排程與 Email 通知。主程式在 `taiwanlife_monitor/monitor.py`。

## 監控內容

- 首頁與關鍵子頁 HTTP/標題/關鍵文字檢查
- 頁面載入過程的壞圖、壞 JS、壞 CSS、XHR/Fetch 失敗
- 站內搜尋流程，預設查詢 `壽險`
- 內部連結抽查，預設最多 120 條
- TLS 憑證到期天數
- JSON 與 Markdown 報表，並保留截圖
- SMTP Email 告警，也可交給 n8n Send Email 節點

## 技術與用途

這個專案是「官網自動巡檢機器人」。它會定時打開網站、檢查功能、截圖存證、產出報表，減少人工每天巡站。

| 技術/套件 | 用途 | 代替人工做到的事 |
|---|---|---|
| Python | 主程式與報表產生 | 自動執行巡檢流程、整理結果 |
| Playwright | 控制 Chromium 瀏覽器 | 像真人一樣開網頁、搜尋、截圖 |
| Chromium | 實際瀏覽器 | 呈現真實網頁畫面 |
| `config/taiwanlife.json` | 巡檢設定 | 集中管理頁面、關鍵字、憑證與連結檢查 |
| OpenSSL | TLS 憑證到期檢查 | 自動提醒憑證是否快過期 |
| JSON/Markdown | 報表格式 | 同時給機器讀、給人看 |
| `scripts/taiwanlife_watchdog.sh` | 漏跑與異常檢查 | 發現巡檢沒跑、報表過舊、fail/warn |
| Docker | 固定執行環境 | 降低部署環境差異 |
| n8n | 排程與 Email 告警 | 自動判斷是否通知 |
| Google Drive API | 截圖上傳 | 自動保存截圖到雲端資料夾 |
| Power Automate / Teams | 未來通知方案 | 異常時自動發 Teams、Email 或工單 |

目前 `requirements.txt` 只列 Playwright。`scripts/upload_to_drive.py` 需要 Google API 套件，正式使用前要補依賴或改成 SharePoint/OneDrive。

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

- 補 Windows PowerShell wrapper，方便 Windows Task Scheduler 執行。
- 通知改接 Power Automate / Teams。
- 報表與截圖改存 SharePoint/OneDrive。
- stdout 補 `problem_checks`，讓通知直接列出異常明細。
- Google Drive upload 補依賴，或改用 Microsoft Graph。
- 搜尋檢查改成確認結果頁或結果列表，降低誤判。
- 第三方追蹤像素錯誤改成 warn 或忽略，避免不必要 fail。
- 增加 ZIP/manifest 封存，方便稽核與交接。

## 本機安裝

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/playwright install chromium
```

執行：

```bash
./venv/bin/python -m taiwanlife_monitor.monitor --config config/taiwanlife.json --output-dir reports
```

異常時直接由 Python 寄信：

```bash
cp .env.example .env
set -a
. ./.env
set +a
./venv/bin/python -m taiwanlife_monitor.monitor --config config/taiwanlife.json --output-dir reports --email-on-fail
```

## n8n 整合

匯入 `n8n/taiwanlife-monitor.workflow.json`。流程是：

1. Schedule Trigger 每 12 小時啟動。
2. Execute Command 執行 Python 巡檢。
3. Code 節點解析 Python stdout 最後一行 JSON。
4. IF 節點判斷 `fail + warn > 0`。
5. Send Email 透過 SMTP 寄送告警。

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

## 報表位置

- 最新 JSON：`reports/latest.json`
- 最新 Markdown：`reports/latest.md`
- 歷史報表：`reports/results/`
- 截圖：`reports/screenshots/`
- 預設保留期限：報表 90 天、截圖 90 天，可在 `config/taiwanlife.json` 的 `retention` 調整。

## Watchdog 漏跑與異常檢查

`scripts/taiwanlife_watchdog.sh` 會讀取 `reports/latest.json`，檢查最新巡檢是否過舊、是否有 fail/warn、截圖數是否不足。適合放在 Hermes cron、Windows wrapper 或 Power Automate 前置檢查。

```bash
./scripts/taiwanlife_watchdog.sh reports/latest.json
```

可調整參數：

```bash
MAX_AGE_HOURS=14 MIN_SCREENSHOTS=7 WARN_IS_FAILURE=1 ./scripts/taiwanlife_watchdog.sh reports/latest.json
```

退出碼：

- `0`：最新報表正常。
- `1`：漏跑、JSON 無法解析、報表過舊、fail/warn 或截圖不足。

## 架構與上線文件

- 架構藍圖：`docs/architecture-blueprint.md`
- 部署說明：`docs/deployment.md`
- 第一版上線檢查清單：`docs/go-live-checklist.md`

## 截圖自動上傳 Google Drive

巡檢產生截圖後，`scripts/upload_to_drive.py` 會自動將新截圖上傳到 Google Drive 的「台壽巡檢截圖」資料夾。

這是過渡性功能：目前巡檢暫時跑在 OCI/Hermes 上，直接查看主機檔案不方便，所以先把截圖同步到 Google Drive 方便人工查看。未來若部署到公司內部 Windows 電腦，截圖與報表可直接存在本機、網路磁碟或 SharePoint/OneDrive，屆時可停用 Google Drive 上傳。

```
python3 scripts/upload_to_drive.py
```

機制：
- 使用既有 `google_token.json` OAuth 權杖（需含 `drive.file` scope）
- 自動刷新過期 token
- 依檔名去重，已上傳的略過
- 支援續傳（resumable upload）

## 建議排程

正式環境建議：

- 每 12 小時執行一次完整巡檢。
- 巡檢後執行 watchdog，確認 `reports/latest.json` 新鮮且無 fail/warn。
- 巡檢完成後自動上傳截圖到 Google Drive。
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
- TLS 憑證：檢查 `www.taiwanlife.com`、`ezbao.taiwanlife.com`、`customer.taiwanlife.com`、`consultancyservice.taiwanlife.com`、`accessibility.taiwanlife.com`。
