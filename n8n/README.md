# n8n 部署整合說明

## workflow 範本

- `taiwanlife-monitor.workflow.json`：適用於 n8n 與 Python 巡檢程式在同一台主機，或自製 n8n image 已內建 Python、Playwright 與本專案程式碼的情境。
- Docker Compose 會把本資料夾唯讀掛到 `/opt/n8n-workflows`，可在 n8n 匯入 workflow JSON。
- SMTP 密碼、SSH 私鑰、n8n encryption key 都必須放在 `.env` 或 n8n credentials，不要寫進 workflow JSON。

## Execute Command 模式

workflow 的 Execute Command 節點會讀取下列環境變數：

```bash
MONITOR_WORKDIR=/opt/taiwanlife-monitor
MONITOR_PYTHON_BIN=./venv/bin/python
MONITOR_CONFIG=config/taiwanlife.json
MONITOR_OUTPUT_DIR=reports
```

命令執行後，Code 節點會從 Python stdout 最後幾行尋找 JSON payload，並把 `fail`、`warn`、`stderr`、非 0 exit code、stdout 無法解析等狀況轉成 Email 告警。

## Docker n8n 建議

官方 n8n Docker 容器內的 Execute Command 只會在 n8n container 裡執行，不會進到 Docker host。預設 Compose 不再把整個 repo 掛進 n8n container；正式環境建議改用 SSH 呼叫巡檢主機。

## SSH 替代作法

1. 在巡檢主機部署本專案，建議路徑為 `/opt/taiwanlife-monitor`。
2. 在巡檢主機建立 Python venv 或使用 `docker compose run --rm taiwanlife-monitor` 驗證巡檢可執行。
3. 在 n8n 建立 SSH credential，私鑰或密碼只放 credential。
4. 將 workflow 的「執行 Python 巡檢」節點替換成 n8n SSH node，遠端命令使用：

```bash
cd "${MONITOR_SSH_WORKDIR:-/opt/taiwanlife-monitor}"
python -m taiwanlife_monitor.monitor --config config/taiwanlife.json --output-dir reports
```

5. SSH node 的 stdout 輸出接回「解析巡檢 stdout」節點；後續 IF 與 Email 節點可沿用。

若巡檢主機用容器執行，SSH 遠端命令可改成：

```bash
cd "${MONITOR_SSH_WORKDIR:-/opt/taiwanlife-monitor}"
docker compose run --rm taiwanlife-monitor
```

## Email 設定

Email 節點的寄件人與收件人會讀取：

```bash
ALERT_FROM=monitor@example.com
ALERT_TO=web-admin@example.com,ops@example.com
```

SMTP host、port、帳號、密碼請在 n8n SMTP credential 內設定；也可以用 n8n credential expression 讀取 `.env` 的 `SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`、`SMTP_PASSWORD`。
