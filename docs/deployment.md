# 部署說明

本工具建議部署在公司內部 VM 或受控容器主機，讓 n8n 每 12 小時觸發一次巡檢。正式環境優先採用「n8n SSH node 呼叫巡檢主機」；若環境很單純，也可用 Docker Compose 直接執行。

## 一、準備 GitHub 專案

```bash
git clone https://github.com/a9181873/twltool.git
cd twltool
```

若是在既有主機更新：

```bash
cd /opt/taiwanlife-monitor
git pull
```

## 二、部署模式建議

### 模式 A：Docker Compose 執行巡檢器

適合最簡單的第一版。

```bash
cp .env.example .env
docker compose build taiwanlife-monitor
docker compose run --rm taiwanlife-monitor
```

健康檢查：

```bash
docker compose run --rm taiwanlife-monitor python -m taiwanlife_monitor.monitor --health-check
```

成功時 stdout 最後會出現類似：

```json
{"ok": true, "summary": {"total": 9, "pass": 9, "warn": 0, "fail": 0}}
```

報表位置：

- `reports/latest.json`
- `reports/latest.md`
- `reports/results/`
- `reports/screenshots/`

### 模式 B：n8n Docker + SSH 呼叫巡檢主機

正式環境建議使用此模式，n8n 不直接開 Execute Command 權限。

1. 巡檢主機部署本專案到 `/opt/taiwanlife-monitor`。
2. 巡檢主機先確認 Docker 模式可跑：

```bash
cd /opt/taiwanlife-monitor
docker compose build taiwanlife-monitor
docker compose run --rm taiwanlife-monitor
```

3. n8n 建立 SSH credential。
4. 匯入 `n8n/taiwanlife-monitor.workflow.json` 後，將「執行 Python 巡檢」節點改成 SSH node。
5. SSH 遠端命令填：

```bash
cd /opt/taiwanlife-monitor
docker compose run --rm taiwanlife-monitor
```

6. SSH node 的 stdout 接回「解析巡檢 stdout」節點。

### 模式 C：n8n Execute Command 同機執行

僅建議內網受控主機使用。

`.env` 內保留：

```bash
N8N_NODES_EXCLUDE=[]
MONITOR_WORKDIR=/opt/taiwanlife-monitor
MONITOR_PYTHON_BIN=./venv/bin/python
MONITOR_CONFIG=config/taiwanlife.json
MONITOR_OUTPUT_DIR=reports
```

在巡檢主機安裝 Python 依賴：

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/playwright install chromium
```

測試：

```bash
./venv/bin/python -m taiwanlife_monitor.monitor --config config/taiwanlife.json --output-dir reports
```

## 三、n8n 設定

啟動 n8n：

```bash
cp .env.example .env
docker compose up -d n8n
```

n8n 預設只綁 `127.0.0.1:5678`。若要讓內網使用者連線，請用反向代理或 VPN，不建議直接開到 Internet。

匯入 workflow：

1. 開啟 n8n。
2. Import from File。
3. 選 `n8n/taiwanlife-monitor.workflow.json`。
4. 確認 Schedule Trigger 是每 12 小時。
5. 建立 SMTP credential。
6. 設定 Email node 的寄件人與收件人，或使用 `.env`：

```bash
ALERT_FROM=monitor@example.com
ALERT_TO=web-admin@example.com,ops@example.com
```

## 四、正式上線檢查

```bash
python3 -B -m unittest discover -s tests -v
docker compose config
docker compose build taiwanlife-monitor
docker compose run --rm taiwanlife-monitor
```

巡檢成功代表：

- TLS 憑證檢查通過。
- 首頁與關鍵子頁 HTTP/標題/關鍵字通過。
- 站內搜尋 `壽險` 有回應。
- 內部連結抽查通過。
- 報表與截圖正常產出。

## 五、權限與資安

- `.env` 不得 commit。
- `N8N_ENCRYPTION_KEY` 正式環境要換成長隨機字串。
- SMTP 帳號使用 send-only 權限。
- `reports/` 不應公開掛 Web server。
- n8n UI 限 VPN、堡壘機或管理網段。
- 若使用 SSH node，建議用專用 key、限制來源 IP、禁用互動 shell。

## 六、排程

目前需求為每 12 小時巡檢一次，workflow 已設定：

```json
{
  "field": "hours",
  "hoursInterval": 12
}
```

若未來要提高頻率，請先與 WAF/SOC 團隊確認來源 IP 與流量上限。
