# 台灣人壽官網巡檢工具 - 優化建議報告

> 歷史文件：此文件保留早期優化建議與處理狀態。最新排程/通知分工請以 `docs/scheduler-integration.md`、`docs/deployment.md`、`docs/go-live-checklist.md` 為準；RPA84 需求對照請看 `docs/rpa84-requirements.md`。

> **報告版本**：v1.0  
> **審查日期**：2026-06-19  
> **審查範圍**：完整代碼庫、配置、部署、測試、文件

## 2026-06-20 處理狀態

已落地：

- `allowed_hosts` 與 `link_crawl.include_hosts` 已同步，並讓程式在未設定 `include_hosts` 時 fallback 到 `allowed_hosts`。
- SSL 憑證檢查已支援 `ssl.hosts` 多網域。
- 已加入指數退避重試設定與 `retry_call()`，套用於 page load、search submit、link crawl。
- 搜尋觸發 selector 已補穩定屬性選擇器，文字 selector 保留為 fallback。
- 截圖保留期已由 30 天改為 90 天，與報表保留期一致。
- `.dockerignore` 已補 `.pytest_cache/`、coverage、build/dist、egg-info、node_modules 等模式。
- `.env.example` 不再放預設 SMTP 密碼值。
- 已新增 `.python-version`，指定 Python 3.12。
- 已新增 `--health-check` CLI。
- 測試從 9 個增加到 12 個，涵蓋 retry、health check、SSL hosts。

決策保留：

- `cap_add: SYS_ADMIN` 不採用。現有 `cap_drop: ALL` 與 `no-new-privileges:true` 已經實測可啟動 Playwright，增加 SYS_ADMIN 會降低容器安全性。
- Dockerfile 保留 `COPY config ./config`。原因是 image 可單獨執行，Compose 掛載 config 則用於正式環境覆寫。
- 未立即導入 pytest/ruff/mypy/CI 大改。這些列入後續 Phase 2，避免目前可部署工具被一次性重構打散。

驗證結果：

```bash
python3 -B -m unittest discover -s tests -v
python3 -m json.tool config/taiwanlife.json
docker run --rm -v /Users/jy/TESTTOOL:/app:ro -w /app taiwanlife-monitor:local \
  python -m taiwanlife_monitor.monitor --config config/taiwanlife.json --output-dir /tmp/twl-reports
```

最新容器實跑：`PASS=13 WARN=0 FAIL=0`。

---

## 📋 總覽

| 指標 | 現狀 | 目標 |
|------|------|------|
| **核心功能** | ✅ 可運行 | 🎯 生產就緒 |
| **部署可靠性** | ⚠️ n8n Execute Command 在 Docker 內失敗 | ✅ SSH 模式或自製 image |
| **測試覆蓋** | ~15%（僅 helper 函數） | ≥70%（含整合測試） |
| **錯誤恢復** | 無重試機制 | 指數退避重試 2-3 次 |
| **資安合規** | ⚠️ .env 範例含密碼、cap_drop 過度 | ✅ 完善 |
| **可觀測性** | 僅 stdout JSON | Health check + Metrics + 結構化日誌 |

---

## 🔴 P0 - 必須修復（阻塞生產部署）

### 1. n8n Execute Command 在 Docker 內無法執行 Python/Playwright

**檔案**：`docker-compose.yml:33-64`, `n8n/taiwanlife-monitor.workflow.json:26-38`  
**問題**：n8n container 沒有 Python venv、Playwright、Chromium。workflow 會直接失敗。  
**解決方案**（三選一）：

- **方案 A（推薦）**：改用 SSH node 呼叫專用巡檢主機（`n8n/README.md:26-45` 已有說明）。
- **方案 B**：自製 `n8n-python-playwright` image，含完整環境。
- **方案 C**：n8n 與巡檢器同機非 Docker 部署（僅限開發/測試環境）。

### 2. `allowed_hosts` 配置未被使用，導致子域名連結漏檢

**檔案**：`config/taiwanlife.json:4-11`, `taiwanlife_monitor/monitor.py:163-165`  
**問題**：`link_crawl.include_hosts` 只有 `www.taiwanlife.com`，但 `allowed_hosts` 有 5 個子域名：
- `ezbao.taiwanlife.com`
- `customer.taiwanlife.com`
- `consultancyservice.taiwanlife.com`
- `accessibility.taiwanlife.com`

這些子域名的連結在 link crawl 中不被檢查。  
**修復**：將 `allowed_hosts` 全部加入 `link_crawl.include_hosts`，或在 `monitor.py:164` 讀取 config 時 fallback 到 `allowed_hosts`。

---

## 🟠 P1 - 高優先級（穩定性、誤報率）

### 3. 無重試機制：網路抖動、WAF 攔截直接判定 fail

**檔案**：`taiwanlife_monitor/monitor.py:550-560` (page_check), `756-773` (link_crawl)  
**建議**：加入指數退避重試

```python
def retry(max_attempts=3, base_delay=2, max_delay=10, exceptions=(Exception,)):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts - 1:
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    time.sleep(delay)
        return wrapper
    return decorator
```

**應用點**：
- `page.goto()` / `page.wait_for_load_state()`（頁面巡檢）
- `context.request.get()`（link crawl）
- `page.locator().fill()` / `click()`（搜尋功能）

### 4. 搜尋觸發器選擇器脆弱（依賴文字內容）

**檔案**：`config/taiwanlife.json:134-140`  
**問題**：`text=搜尋全站`、`text=搜尋` 官網改版文案變動即失效。  
**建議**：優先使用穩定屬性選擇器

```json
"trigger_selectors": [
  "[data-testid='search-trigger']",
  "[aria-label*='搜尋']",
  "button[aria-expanded='false'][aria-haspopup='dialog']",
  "a[href*='search']",
  "text=搜尋全站"
]
```

並在開發階段以 `headful` 模式驗證選擇器穩定性。

### 5. Docker 容器權限過度限制，Playwright 可能啟動失敗

**檔案**：`docker-compose.yml:19-22`  
**問題**：`cap_drop: ALL` + `no-new-privileges` 導致 Chromium `--no-sandbox` 失效時無法啟動。  
**修復**：

```yaml
cap_drop:
  - ALL
cap_add:
  - SYS_ADMIN   # 僅在需要時
security_opt:
  - no-new-privileges:true
shm_size: 2gb  # 從 1gb 增加
```

**驗證**：在 CI/CD 中執行 `docker compose run --rm taiwanlife-monitor` 確認啟動成功。

### 6. SSL 憑證檢查僅檢查 base_url，子域名憑證漏檢

**檔案**：`taiwanlife_monitor/monitor.py:498-537`  
**建議**：遍歷 `allowed_hosts` 檢查每個域名的憑證，或新增 `ssl.hosts` 陣列配置。

---

## 🟡 P2 - 中優先級（維運性、資安、開發體驗）

### 7. Dockerfile 複製 config 但 runtime 掛載覆蓋

**檔案**：`Dockerfile:17`, `docker-compose.yml:14`  
**問題**：Dockerfile 的 `COPY config ./config` 在 runtime 被 `docker-compose.yml` 的 volume 掛載覆蓋，導致 image 層浪費且可能誤導維護者。  
**修復**：移除以 `COPY config ./config`，只保留 volume 掛載。

### 8. 缺乏中文字體，截圖中文顯示 □□□

**檔案**：`Dockerfile:12`  
**修復**：

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*
```

或改用官方 image：`FROM mcr.microsoft.com/playwright/python:v1.53-noble`。

### 9. 截圖保留期(30天) < 報告保留期(90天)

**檔案**：`config/taiwanlife.json:179-183`, `monitor.py:962-1000`  
**問題**：截圖消失後，90 天內的 markdown 報告仍有截圖參考，會出現無效路徑。  
**建議**：將 `screenshot_days` 統一為 90 天，或在 markdown 報告中加入 `*截圖可能已過期刪除*` 標記。

### 10. .dockerignore 遺漏關鍵模式

**檔案**：`.dockerignore`  
**補充**：

```dockerignore
venv/
.venv/
*.pyc
__pycache__/
.pytest_cache/
.coverage
htmlcov/
*.egg-info/
dist/
build/
node_modules/
```

### 11. Python 版本不一致

**檔案**：`Dockerfile:1` vs 本機環境  
**問題**：Docker image 使用 `python:3.12-slim`，但本機環境為 Python 3.13/3.14（從 `.cache` 路徑 `cpython-313/314` 可證）。  
**建議**：統一採用 Python 3.12（Playwright 官方支援最佳），並在專案根目錄宣告 `.python-version` 或 `pyproject.toml`。

---

## 🟢 P3 - 低優先級（技術債、擴展性）

### 12. 單元測試覆蓋率極低（~15%）

**檔案**：`tests/test_monitor_core.py`  
**缺口**：
- `run_page_check`、`run_search_check`、`run_link_crawl`、`run_ssl_check` 無整合測試
- `categorize_error` 無測試
- `build_report` / `write_markdown` 僅基本序列化測試

**建議**：
- 使用 `pytest` + `pytest-mock` 替代 `unittest`
- Mock `playwright.sync_api` 建立整合測試
- 加入 `dev-requirements.txt`：`pytest>=8.0`, `pytest-mock>=3.14`, `pytest-cov>=5.0`
- CI 加入 `pytest --cov=taiwanlife_monitor --cov-fail-under=70`

### 13. 無 Health Check / 心跳端點

**建議**：新增 CLI 模式 `--health-check`，輸出 `{"status": "ok", "version": "..."}`，讓 n8n workflow 先呼叫 health check 再跑完整巡檢。

### 14. 報表無壓縮輪轉

**檔案**：`monitor.py:962-1000`  
**問題**：90 天的 JSON/MD 累積未壓縮，可能佔用大量磁碟空間。  
**建議**：
- `cleanup_old_outputs()` 壓縮舊檔：`gzip *.json *.md`
- 或整合 `logrotate` 配置

### 15. n8n workflow JSON 可能不完整

**檔案**：`n8n/taiwanlife-monitor.workflow.json:42`  
**驗證**：匯入 n8n 前以 `jq .nodes[].parameters` 確認 JSON 結構完整性。

### 16. 缺乏程式碼品質工具

**建議加入**：
- `ruff`（lint + format，替代 black/isort/flake8）
- `mypy`（型別檢查）
- `pre-commit` hooks

### 17. 缺乏 CI/CD Pipeline

**建議**：GitHub Actions 自動化測試、lint、Docker build 驗證。

---

## 📦 依賴升級建議

| 套件 | 當前 | 目標 | 風險 |
|------|------|------|------|
| `playwright` | `>=1.53.0` | 1.53.x | 低（含瀏覽器二進制，需同步 playwright install） |
| Python | 3.12 (Docker) / 3.13-3.14 (本機) | 3.12 LTS | 中（統一版本） |

---

## 📁 專案結構優化建議

```
TESTTOOL/
├── .github/workflows/          # CI/CD（新增）
├── .pre-commit-config.yaml     # Pre-commit hooks（新增）
├── pyproject.toml              # 專案元資料、依賴、工具配置（新增）
├── config/
│   └── taiwanlife.json         # 唯一配置來源
├── docs/                       # 保持
├── n8n/                        # 保持
├── reports/                    # .gitignore 忽略
├── taiwanlife_monitor/
│   ├── __init__.py
│   ├── monitor.py              # 核心邏輯
│   ├── cli.py                  # CLI 入口（從 monitor.py main 拆出）
│   ├── health.py               # Health check（新增）
│   ├── reporter.py             # 報表生成（從 monitor.py 拆出）
│   ├── checks/
│   │   ├── __init__.py
│   │   ├── ssl.py
│   │   ├── page.py
│   │   ├── search.py
│   │   └── links.py
│   └── utils/
│       ├── __init__.py
│       ├── sanitize.py
│       ├── retry.py
│       └── categorize.py
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_sanitize.py
│   │   ├── test_categorize.py
│   │   └── test_retry.py
│   ├── integration/
│   │   ├── test_page_check.py
│   │   ├── test_search_check.py
│   │   └── test_link_crawl.py
│   └── conftest.py             # pytest fixtures
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example
├── .gitignore
├── requirements.txt
├── dev-requirements.txt
├── README.md
└── README_TESTING.md
```

---

## 🎯 實施路線圖

| 階段 | 工作項目 | 預估工時 | 依賴 |
|------|----------|----------|------|
| **Phase 0** (立即) | 修復 n8n 執行模式 (SSH node) | 2h | 無 |
| | 同步 `allowed_hosts` → `link_crawl.include_hosts` | 0.5h | 無 |
| **Phase 1** (1 週) | 加入重試機制 | 4h | 無 |
| | 修復 Docker 權限/字體/版本 | 2h | 無 |
| | 完善 .dockerignore / .gitignore | 0.5h | 無 |
| **Phase 2** (2 週) | 重構模組化 + 單元/整合測試 (目標 70%+) | 16h | Phase 1 |
| | 加入 pytest/ruff/mypy/pre-commit/CI | 4h | Phase 2 |
| **Phase 3** (持續) | Health check endpoint | 2h | Phase 2 |
| | 報表壓縮輪轉 | 2h | Phase 2 |
| | 文件同步更新 | 2h | 全部 |

---

## ❓ 待確認決策項

| # | 決策點 | 選項 | 建議 |
|---|--------|------|------|
| 1 | n8n 執行模式 | SSH node / 自製 image / 同機非 Docker | **SSH node**（權限隔離、生產標準） |
| 2 | 測試框架 | 維持 unittest / 遷移 pytest | **pytest**（生態豐富、fixture 強） |
| 3 | 型別檢查 | 不加 / 加 mypy (strict/loose) | **mypy loose 先行**，核心模組逐步加嚴 |
| 4 | 專案打包 | requirements.txt / pyproject.toml + uv | **pyproject.toml + uv**（現代、標準） |
| 5 | 容器基底 image | python:3.12-slim / mcr.microsoft.com/playwright/python | **官方 Playwright image**（含所有依賴） |

---

## 📎 附錄：快速驗證清單

```bash
# 驗證 Docker 建置與運行
docker compose build taiwanlife-monitor
docker compose run --rm taiwanlife-monitor

# 執行測試
./venv/bin/python -m unittest discover -s tests -v

# 程式碼品質（未來）
ruff check taiwanlife_monitor tests
mypy taiwanlife_monitor

# 檢查配置一致性
jq '.link_crawl.include_hosts' config/taiwanlife.json
jq '.allowed_hosts' config/taiwanlife.json
```
