# 台灣人壽官網巡檢架構藍圖

## 目標

建立公司內部可維運的 synthetic monitoring 工具，定期從指定主機模擬真實瀏覽器使用台灣人壽官網，發現網頁失效、物件壞掉、搜尋異常、TLS 憑證即將到期等問題時立即 Email 告警。

## 建議架構

```text
n8n Schedule Trigger
  -> Execute Command 或 SSH Node
  -> Python Playwright 巡檢器
  -> JSON/Markdown/截圖報表
  -> IF 判斷 fail/warn
  -> Send Email SMTP 告警
```

第一版建議先採「Python 巡檢器 + n8n 排程告警」：

- Python 負責瀏覽器自動化、資源錯誤擷取、連結抽查與報表。
- n8n 負責排程、條件判斷、Email、後續串 Teams/LINE/工單。
- 報表落地保存，方便事故追查與誤報調校。

## 檢查層級

### L1 可用性

- 首頁 HTTP 200。
- 標題包含 `台灣人壽`。
- TLS 憑證剩餘天數。
- 主要子頁可載入。

### L2 頁面完整性

- 首頁關鍵文字：商品資訊、保戶服務、投資資訊、網路投保、商品快搜、最新消息、服務據點。
- 子頁關鍵文字：壽險保障、理賠申請、宣告利率、服務據點、新聞中心。
- 載入過程擷取 4xx/5xx 的 JS、CSS、圖片、字型、XHR、Fetch。

### L3 功能性

- 站內搜尋輸入 `壽險`，確認有搜尋結果或相關文字。
- 抽查內部連結，避免首頁或重要子頁連到 404/500。
- 截圖保存，讓值班人員快速判斷是網站問題、WAF 問題或巡檢主機問題。

## 部署模式

### 模式 A：n8n 與巡檢器同主機

適合小型第一版。n8n 使用 Execute Command：

```bash
cd /opt/taiwanlife-monitor
./venv/bin/python -m taiwanlife_monitor.monitor --config config/taiwanlife.json --output-dir reports
```

優點是簡單；缺點是 n8n 主機需要安裝 Python、Playwright 與 Chromium。

### 模式 B：n8n 透過 SSH 呼叫巡檢主機

正式環境較建議此模式。n8n 不直接具備瀏覽器與 shell 權限，只透過受限 SSH key 呼叫巡檢主機上的固定腳本。

優點是權限隔離較好；缺點是多一台巡檢主機要維護。

### 模式 C：容器化巡檢器

用 `Dockerfile` 建立固定 image，n8n 呼叫：

```bash
docker run --rm --env-file .env -v /opt/taiwanlife-monitor/reports:/app/reports taiwanlife-monitor:local
```

優點是一致性高；缺點是 Chromium image 較大，CI/CD 與 image 更新要管好。

## 告警策略

第一版：

- `fail > 0` 立即寄信。
- `warn > 0` 可先寄給維運群組，觀察一週後調整。
- Email 內容放摘要、報表路徑、截圖路徑，不在信件內塞大量原始 log。

第二版：

- 同一錯誤 12 小時內只寄一次或只在狀態改變時寄送，避免信件風暴。
- 連續 2 次失敗才升級為正式事故，降低暫時性網路抖動誤報。
- 串接 Teams/Slack/LINE Notify 替代方案或 ITSM 工單。

## 報表保存

建議：

- JSON/Markdown 保存 90 天。
- 截圖保存 14-30 天。
- 異常截圖保存 180 天。
- 報表目錄不應公開掛在 Web server。

## 正式上線最低需求

- 一組專用 Linux 服務帳號，例如 `site-monitor`。
- 只允許該帳號讀寫巡檢資料夾與報表資料夾。
- SMTP 憑證放環境變數、Vault 或 n8n credential，不寫入 Git。
- n8n 啟用 workflow 權限控管與 2FA。
- 巡檢頻率預設每 12 小時一次，避免對官網造成額外壓力。
- 第一週每日檢查誤報，調整 selectors、timeout 與忽略清單。

## 已參考資訊

- 台灣人壽官網首頁目前可見四大主導覽、商品快搜、熱門活動、最新消息與頁尾關鍵連結。
- n8n 官方文件：Schedule Trigger 可依固定間隔或 Cron 執行 workflow；Send Email 使用 SMTP 寄送；Execute Command 在 n8n 2.0 起預設停用，且在 Docker 內會執行於 n8n container。
- Playwright 官方文件：支援 Chromium/WebKit/Firefox，適合端對端測試與一般瀏覽器自動化。
