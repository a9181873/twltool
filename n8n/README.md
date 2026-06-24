# n8n 排程整合說明

## workflow 範本

- `taiwanlife-monitor.workflow.json`：只負責排程、執行與解析結果，不使用 n8n Email 節點。
- 適用於 n8n 與 Python 巡檢程式在同一台主機，或自製 n8n image 已內建 Python、Playwright 與本專案程式碼的情境。
- Docker Compose 會把本資料夾唯讀掛到 `/opt/n8n-workflows`，可在 n8n 匯入 workflow JSON。
- SSH 私鑰、n8n encryption key 都必須放在 `.env` 或 n8n credentials，不要寫進 workflow JSON。

## Execute Command 模式

workflow 的 Execute Command 節點會讀取下列環境變數：

```bash
MONITOR_WORKDIR=/opt/taiwanlife-monitor
MONITOR_PYTHON_BIN=./venv/bin/python
MONITOR_CONFIG=config/taiwanlife.json
MONITOR_OUTPUT_DIR=reports
MONITOR_ENABLE_RPA84=false
```

命令執行後，Code 節點會從 Python stdout 最後幾行尋找 JSON payload，並輸出 `summary`、`problem_checks`、`latest_json`、`latest_md`、`screenshots` 與 `should_notify_external`。

通知不放在 n8n workflow 內。建議由 Windows wrapper + Power Automate、Python SMTP、Teams Workflows 或公司既有告警系統處理。

## Docker n8n 建議

官方 n8n Docker 容器內的 Execute Command 只會在 n8n container 裡執行，不會進到 Docker host。預設 Compose 不再把整個 repo 掛進 n8n container；正式環境建議改用 SSH 呼叫巡檢主機。

## SSH 替代作法

1. 在巡檢主機部署本專案，建議路徑為 `/opt/taiwanlife-monitor`。
2. 在巡檢主機建立 Python venv 或使用 `docker compose run --rm taiwanlife-monitor` 驗證巡檢可執行。
3. 在 n8n 建立 SSH credential，私鑰或密碼只放 credential。
4. 將 workflow 的「執行 Python 巡檢」節點替換成 n8n SSH node，遠端命令使用：

```bash
cd "${MONITOR_SSH_WORKDIR:-/opt/taiwanlife-monitor}"
python -m taiwanlife_monitor.monitor --config config/taiwanlife.json --output-dir reports --scheduler n8n --fail-exit-code
```

5. SSH node 的 stdout 輸出接回「解析巡檢 stdout」節點。

若巡檢主機用容器執行，SSH 遠端命令可改成：

```bash
cd "${MONITOR_SSH_WORKDIR:-/opt/taiwanlife-monitor}"
docker compose run --rm taiwanlife-monitor
```

RPA84 場景已在 `config/taiwanlife.json` 的 `rpa84.scenarios`，不需要另行掛載舊 Word 文件或外部場景檔。

## 外部通知

n8n 只執行巡檢，不寄送通知。若公司仍想讓 n8n 串 Teams 或工單，建議在解析節點後新增專用節點讀取 `should_notify_external`，但不要使用 SMTP 密碼或收件人清單硬寫在 workflow JSON。
