# 巡檢管理後台

這個 UI 不使用 LLM API。使用者透過表單管理巡檢設定，系統用固定規則驗證後寫回 `config/taiwanlife.json`，再交給既有 Playwright 巡檢器執行。

## 可管理項目

- 總覽：目前啟用的頁面、搜尋、連結、SSL、自訂流程與 latest 結果。
- 頁面巡檢：管理頁面 ID、名稱、路徑、title 規則、必要文字與截圖模式。
- 搜尋檢查：管理搜尋字、觸發按鈕 selector、輸入框 selector、送出 selector 與預期結果文字。
- SSL / 連結：管理憑證天數門檻、檢查主機、連結抽查數量、種子路徑與忽略規則。
- 自訂流程：管理開頁、點擊物件、輸入欄位、鍵盤操作、驗證文字、等待與截圖。
- 結果 / 試跑：讀取 `reports/latest.json`，並可從 UI 觸發一次巡檢。

## Windows 本機

```powershell
cd C:\path\to\twltool
.\scripts\run_flow_editor.ps1
```

預設網址：

```text
http://127.0.0.1:8787/
```

若要開給同網段使用，必須設定 token：

```powershell
$env:FLOW_UI_TOKEN="replace-with-random-token"
.\scripts\run_flow_editor.ps1 -HostName 0.0.0.0 -NoBrowser
```

## OCI / Docker Compose

先在 `.env` 設定：

```dotenv
FLOW_UI_BIND_ADDR=127.0.0.1
FLOW_UI_PORT=8787
FLOW_UI_TOKEN=replace-with-random-editor-token
FLOW_UI_UID=1000
FLOW_UI_GID=1000
```

啟動：

```bash
docker compose --profile tools up -d flow-editor
```

建議在 OCI 上優先用 SSH tunnel：

```bash
ssh -L 8787:127.0.0.1:8787 ubuntu@<oci-host>
```

然後在本機瀏覽器開：

```text
http://127.0.0.1:8787/
```

若要放到反向代理後方，建議：

- 只允許 VPN 或可信來源 IP。
- 保留 `FLOW_UI_TOKEN`。
- 使用 HTTPS。
- 不要直接把 `FLOW_UI_BIND_ADDR=0.0.0.0` 暴露到公網。

## Linux 直接啟動

```bash
FLOW_UI_TOKEN=replace-with-random-token \
FLOW_UI_HOST=127.0.0.1 \
FLOW_UI_PORT=8787 \
./scripts/run_flow_editor.sh
```

## Selector 建議

自訂流程的物件定位仍使用 Playwright selector。常用範例：

```text
button:has-text('搜尋')
[aria-label*='搜尋']
[data-testid='search-button']
input[type='search']
```

後續若要降低使用者理解 selector 的門檻，可再新增「頁面物件掃描器」，由系統列出頁面上的按鈕、連結、輸入框供使用者點選。

## 副作用說明

「有副作用」代表流程執行後可能真的改變系統狀態，不只是查看畫面。

常見有副作用的流程：

- 送出表單或申請。
- 寄出 Email。
- 下載或匯出檔案。
- 新增收藏、加入清單、修改設定。
- 建立、修改、刪除資料。
- 產生查詢紀錄、交易紀錄或外部通知。

通常沒有副作用的流程：

- 開啟頁面。
- 點搜尋並輸入關鍵字。
- 驗證畫面文字。
- 檢查連結或 SSL。
- 截圖。

建議管理方式：

- 有副作用的流程預設先不要啟用正式排程。
- 優先使用測試帳號、測試收件人與測試資料。
- 若流程會寄信、匯出、修改資料或送出申請，應先人工試跑確認。
- 必要時補上清理步驟或人工復原流程。
