# 測試說明

本專案的基本回歸測試放在 `tests/`，使用 Python 標準函式庫 `unittest`，不需要真實瀏覽器、不下載 Playwright browser，也不連外。

## 執行方式

```bash
python3 -m unittest discover -s tests -v
```

若使用專案虛擬環境：

```bash
./venv/bin/python -m unittest discover -s tests -v
```

## 測試範圍

- JSON/Markdown 報表結構與序列化輸出。
- Email alert gating：停用時不寄、成功報告預設不寄、失敗報告才透過 mocked SMTP 寄送。
- `config/taiwanlife.json` 設定載入與 `TaiwanLifeMonitor` 基本初始化。
- URL normalization、狀態判斷、Email 收件人拆分等 helper 行為。
- Playwright page listener 的資源錯誤、request failed、console error、page error 收集邏輯。

## 設計原則

- 測試不得呼叫 `TaiwanLifeMonitor.run()`，避免觸發 TLS、瀏覽器或外部網路。
- 測試 SMTP 時一律 patch `smtplib.SMTP`，不得寄送真實 Email。
- 新增測試優先使用 `unittest` 與標準函式庫假物件，只有必要時才把輕量開發依賴加入 `dev-requirements.txt`。
- 測試檔只應維護在 `tests/`，測試說明維護在本檔。
