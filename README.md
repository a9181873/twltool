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

## 架構與上線文件

- 架構藍圖：`docs/architecture-blueprint.md`
- 部署說明：`docs/deployment.md`
- 第一版上線檢查清單：`docs/go-live-checklist.md`

## 建議排程

正式環境建議：

- 每 12 小時執行一次完整巡檢。
- Email 僅在 `fail` 或 `warn` 發生時寄送。
- 若未來要提高頻率，先和 WAF/SOC 團隊確認來源 IP、User-Agent 與流量上限。
