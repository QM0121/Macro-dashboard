# Macro Dashboard（GitHub Pages）

這是一個可直接分享網址的「總經 × 牛熊市判斷指標」網站。  
網站會透過 **GitHub Actions + FRED API** 每天自動抓取最新總經資料，並更新儀表板內容。

---

## 網站功能

- 自動更新總經與市場指標
- 一眼判讀目前市場偏多、偏空或中性
- 以燈號方式呈現各類風險訊號
- 提供牛熊市判斷所需的多面向資料

---

## 目前追蹤的指標

### 1. 利率環境
- 聯邦基金利率

### 2. 殖利率曲線
- 10Y − 2Y 利差

### 3. QT 與流動性
- Fed 總資產
- Fed 資產單月變動
- 銀行準備金
- 逆回購 RRP

### 4. 金融條件與風險壓力
- NFCI
- 高收益債利差
- VIX

### 5. 就業與衰退警報
- 初領失業金人數
- Sahm Rule 衰退指標

### 6. 景氣領先與股市趨勢
- 美國領先指標
- S&P 500 指數
- 200 日均線
- 距離 52 週高點跌幅

---

## 檔案結構

- `index.html`：網站主頁
- `styles.css`：網站樣式
- `data.json`：自動更新後的資料
- `update_data.py`：抓取 FRED 資料並更新 `data.json`
- `.github/workflows/update-data.yml`：GitHub Actions 自動排程

---

## 自動更新機制

網站透過 GitHub Actions 每天自動執行：

1. 呼叫 FRED API 抓取最新資料
2. 執行 `update_data.py`
3. 更新 `data.json`
4. 網站前端自動讀取最新資料

目前排程為：

```text
每天自動更新一次
