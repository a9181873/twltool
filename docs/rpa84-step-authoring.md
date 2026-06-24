# RPA84 步驟新增方式

未來新增 RPA84 點擊、輸入、驗證規則時，只改 `config/taiwanlife.json` 的 `rpa84.scenarios`。

`steps` 是程式實際照做的動作；截圖是結果證據，不是操作規則本身。

## 基本格式

```json
{
  "id": "3-2-product-filter",
  "group": "商品資訊",
  "name": "商品篩選",
  "enabled": true,
  "input": {
    "keyword": "台灣人壽"
  },
  "acceptance": [
    "篩選結果有資料"
  ],
  "steps": [
    {
      "action": "goto",
      "path": "/product-personal-life-TermLife",
      "name": "開啟商品頁"
    },
    {
      "action": "click_first",
      "name": "開啟篩選條件",
      "selectors": [
        "button:has-text('篩選')",
        "text=篩選條件"
      ]
    },
    {
      "action": "fill_first",
      "name": "輸入關鍵字",
      "value": "台灣人壽",
      "selectors": [
        "input[placeholder*='搜尋']",
        "input[type='search']"
      ]
    },
    {
      "action": "press_first",
      "name": "送出查詢",
      "key": "Enter",
      "selectors": [
        "input[placeholder*='搜尋']",
        "input[type='search']"
      ]
    },
    {
      "action": "assert_any_text",
      "name": "確認查詢結果",
      "texts": [
        "搜尋結果",
        "台灣人壽"
      ]
    },
    {
      "action": "screenshot",
      "name": "結果截圖"
    }
  ]
}
```

## 可用動作

| action | 用途 | 常用欄位 |
|---|---|---|
| `goto` | 開啟頁面 | `path` 或 `url` |
| `click_first` | 點第一個找得到的按鈕/連結 | `selectors` |
| `fill_first` | 在第一個找得到的輸入框填值 | `selectors`, `value` |
| `press_first` | 對輸入框按鍵，例如 Enter | `selectors`, `key` |
| `wait_for_load_state` | 等頁面載入狀態 | `state`, `timeout_ms` |
| `wait` | 固定等待短時間 | `milliseconds` |
| `assert_any_text` | 任一文字出現就算成功 | `texts` |
| `assert_all_text` | 所有文字都出現才算成功 | `texts` |
| `screenshot` | 留截圖證據 | `filename`, `full_page` |
| `manual_note` | 暫時留下人工備註 | `note` |

`selectors` 是設定檔欄位名稱，意思是「頁面元素辨識規則」。建議同一個動作放 2 到 4 個備援規則，例如按鈕文字、輸入框 placeholder、aria-label；程式會由上而下找第一個看得到的元素。

## 建議流程

1. 先把 `enabled` 設成 `false`，補好 `steps`。
2. 本機用 `--enable-rpa84` 跑一次，確認報表與截圖。
3. 有下載、寄信、收藏、匯出等副作用的場景，先設定測試帳號、測試收件人或清理步驟。
4. 成功後再把該場景 `enabled` 改成 `true`。

## 網頁巡查是否寫死網址

不是只寫死網址：

- `pages` 是必看頁清單，確保重要頁面一定被檢查。
- `link_crawl` 會從種子頁抓站內連結並抽查，官網新增連結也有機會被巡到。
- `rpa84.scenarios` 是業務流程，負責模擬人操作，例如點擊、輸入、送出與驗證結果。
