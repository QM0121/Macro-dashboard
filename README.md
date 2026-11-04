# Macro Dashboard · v7.1

以美股趨勢為主、總經資料為背景的 GitHub Pages 儀表板。

## 本版功能

- 圖下兩句動態解讀：顯示期間的首末變化，以及與指標定義相符的解釋。
- 「如何判讀與數據明細」預設收合，整合指標用途、觀察重點、常見誤讀、官方說明與原有數據；避免重複訊號堆疊。

- 30 組真實 FRED 歷史序列，各保留截至最新觀察日的一年資料。
- 每個類別可切換指標與近三個月、半年、一年；可放大、觸控及以方向鍵查看數值。
- 非農就業以柱狀圖顯示；七項股票指數可疊加 200 日均線。
- 保留最新數字與前值，詳細數據可展開；明確顯示資料所屬日期、來源、頻率與單位。
- 更新失敗沿用舊值並明確標示，不以抓取日期代替觀察日期；移除停止更新的 USSLIND。
- 不依賴外部圖表 CDN。既有市場評分權重與門檻保留，新增評分方法說明。

## 檔案

- `index.html`、`styles.css`：介面與手機排版。
- `charts.js`：SVG 互動圖表。
- `interpretation.js`：30 項指標教學與依可見資料產生的規則式解讀。
- `test_interpretation.cjs`：解讀單位、缺資料、過期資料與期間切換檢查。
- `data.json`：最新摘要、歷史觀察值與抓取狀態。
- `update_data.py`、`history_data.py`：FRED API 抓取、歷史轉換與資料品質紀錄。
- `test_history.py`：成長率、單位、均線與更新失敗處理測試。
- `.github/workflows/update-data.yml`：既有自動更新排程。

## 自動更新

沿用 GitHub Secrets 中的 `FRED_API_KEY`，排程每次執行 `python update_data.py` 即更新摘要與一年歷史資料。相同 FRED 序列在一次執行中共用觀察值快取，避免重複請求；輸出以暫存檔原子替換，避免留下半份 JSON。

```bash
pip install requests
python -m unittest test_history.py
node --test test_interpretation.cjs
python update_data.py
```

## 資料口徑

圖表為 FRED 最新修訂後的歷史序列，不是當時發布版本，也不是策略回測。月資料日期表示所屬月份；一年月資料通常含 12–13 個觀察值。年增率需同月份前一年觀察值；缺值不補零、不插值。非交易日不列點；長時間斷檔會分段呈現。

市場總分為自訂趨勢評分，並非上漲機率。未以修訂後資料回填過往每日總分。有效聯邦基金利率（DFF）並非政策目標區間。Fed 資產變動為最新值減四週前，並非曆月變動。
