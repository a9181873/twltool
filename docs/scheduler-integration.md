# 排程與通知整合設計

## 原則

- Python `taiwanlife_monitor.monitor` 是唯一巡檢核心。
- Windows Task Scheduler、Power Automate、n8n、Docker、cron 都只負責觸發同一支 CLI。
- 通知層與排程層分離；n8n workflow 預設不寄信。
- stdout 最後一行固定輸出 JSON，供所有排程器解析。

## 共用 CLI

```bash
python -m taiwanlife_monitor.monitor --config config/taiwanlife.json --output-dir reports --scheduler manual
```

啟用 RPA84：

```bash
python -m taiwanlife_monitor.monitor --config config/taiwanlife.json --output-dir reports --scheduler manual --enable-rpa84
```

stdout payload 主要欄位：

- `ok`
- `scheduler`
- `summary`
- `problem_checks`
- `latest_json`
- `latest_md`
- `screenshots`

## Windows Task Scheduler

建議動作：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\path\to\twltool\scripts\run_taiwanlife_monitor.ps1
```

建議設定：

- 每 12 小時執行一次。
- 不允許平行執行新 instance。
- 執行逾時 1 小時。
- 使用專用服務帳號。

可用腳本建立排程：

```powershell
.\scripts\register_windows_task.ps1 -TaskName TaiwanLifeWebsiteMonitor -HoursInterval 12
```

## Power Automate / Teams

推薦路線：

1. Windows Task Scheduler 執行 `scripts/run_taiwanlife_monitor.ps1`。
2. wrapper 讀取 monitor stdout JSON。
3. 若 `fail > 0` 或 `warn > 0`，POST 到 `POWER_AUTOMATE_WEBHOOK_URL`。
4. Power Automate 發 Teams channel message、Email 或建立工單。

範例：

```powershell
$env:POWER_AUTOMATE_WEBHOOK_URL="https://..."
.\scripts\run_taiwanlife_monitor.ps1
```

## n8n

`n8n/taiwanlife-monitor.workflow.json` 只做三件事：

1. Schedule Trigger。
2. Execute Command 或改成 SSH node 執行 monitor。
3. 解析 stdout JSON 留在 execution log。

Docker 版 n8n 不會自動進到 host 執行 Python，正式環境建議用 SSH node 呼叫巡檢主機。

## RPA84 場景

RPA84 需求直接在 `config/taiwanlife.json` 的 `rpa84.scenarios`。原 Word RPA 流程文件已由本專案取代；目前以主設定作為正式需求與執行來源。

RPA84 整體預設不啟用，避免 selector 尚未校準前誤報。啟用後只會執行場景內 `enabled=true` 的項目。

啟用方式：

```powershell
.\scripts\run_taiwanlife_monitor.ps1 -EnableRpa84
```

或：

```bash
MONITOR_ENABLE_RPA84=true python -m taiwanlife_monitor.monitor --config config/taiwanlife.json --output-dir reports
```

## Watchdog

Linux/Hermes 可用：

```bash
MAX_AGE_HOURS=14 MIN_SCREENSHOTS=7 WARN_IS_FAILURE=1 ./scripts/taiwanlife_watchdog.sh reports/latest.json
```

Windows 可用：

```powershell
.\scripts\taiwanlife_watchdog.ps1 -ReportPath reports\latest.json -WarnIsFailure
.\scripts\run_taiwanlife_monitor.ps1 -RunWatchdogBefore
```
