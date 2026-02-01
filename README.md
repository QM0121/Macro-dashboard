# Macro Dashboard（GitHub Pages）

這是一個可直接分享網址的靜態網站：
- 首頁＋章節導覽
- PDF 線上預覽（嵌入）
- PDF 下載按鈕

## 檔案結構
- `index.html`
- `styles.css`
- `handbook.pdf`

## 部署到 GitHub Pages（最短流程）

1. 到 GitHub 建立一個新的 repository，例如：`macro-dashboard`
2. 把這三個檔案上傳到 repo 根目錄（root）
3. 進入 repo：Settings → Pages
4. Build and deployment → Source：選 `Deploy from a branch`
5. Branch：選 `main`，資料夾選 `/ (root)`，Save
6. 等 1~3 分鐘後，Pages 會產生網址：
   `https://<你的帳號>.github.io/macro-dashboard/`

## 更新 PDF
直接用新的 PDF 覆蓋 `handbook.pdf`，再 push 一次就會自動更新。
