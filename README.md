# auto-check-tpcu

`auto-check-tpcu` 是一個用 Python 撰寫的自動化工具，用於登入臺北城市科技大學校務系統，查詢最近 30 天的缺曠 / 請假紀錄，解析回傳的 HTML 表格，並透過 Discord Webhook 發送通知。

這個工具的目標很單純：把原本需要手動登入、切頁、查詢的流程改成可重複執行的腳本，方便定期檢查自己的缺曠狀態。

## 功能

- 自動登入臺北城市科技大學校務系統
- 查詢最近 30 天缺曠 / 請假紀錄
- 解析校務系統回傳的 HTML 表格
- 整理節次資料並發送到 Discord Webhook
- 將查詢結果輸出為 `absence_debug.html` 便於除錯

## 技術

- Python
- `requests`
- `BeautifulSoup`
- `python-dotenv`

## 安裝方式

1. 複製專案：

```bash
git https://github.com/alaner652/tpcu-absence-notifier
cd tpcu-absence-notifier
```

2. 建立並啟用虛擬環境：

```bash
python3 -m venv venv
source venv/bin/activate
```

3. 安裝相依套件：

```bash
pip install -r requirements.txt
```

4. 複製環境變數範例檔：

```bash
cp .env.example .env
```

5. 編輯 `.env`：

```env
TPCU_UID=你的學號
TPCU_PWD=你的密碼
DISCORD_WEBHOOK=你的 Discord Webhook URL
TPCU_YMS=114,2
```

### 環境變數說明

- `TPCU_UID`：校務系統帳號
- `TPCU_PWD`：校務系統密碼
- `DISCORD_WEBHOOK`：Discord Webhook URL
- `TPCU_YMS`：學年期參數，預設為 `114,2`

## 使用方法

直接執行：

```bash
python bot.py
```

程式會依序執行以下流程：

1. 登入校務系統
2. 查詢最近 30 天缺曠 / 請假資料
3. 解析 HTML 表格
4. 將結果送到 Discord Webhook
5. 額外輸出 `absence_debug.html` 供檢查原始回應內容

若查詢成功，終端機會顯示找到的節次筆數，並將整理後的通知送到 Discord。

## 專案背景

這個專案源自一次 Web security 研究練習，也是我第一次實際使用 Burp Suite 分析校務系統的 HTTP 流程。

在過程中，我攔截並觀察到系統主要使用以下請求處理登入與缺曠查詢：

- `POST /tsint/perchk.jsp`
- `POST /tsint/ak_pro/ak002_01.jsp`

分析 request 時，我發現缺曠查詢本質上就是一個帶參數的 POST request，因此可以用 Python 將整個登入與查詢流程自動化。

在測試過程中，我也意外發現系統的密碼欄位只在前端做了長度限制，例如 `maxlength="10"`。但透過 Burp Suite 攔截 request 並修改 payload，仍然可以提交超過 10 字元的密碼，且系統會回應密碼修改成功。

問題在於，密碼雖然已經被 server 接受並儲存，登入頁面的輸入框卻仍然只允許輸入最多 10 字元。結果就是：實際儲存在系統中的密碼長度已經超過 10 字元，但使用者在登入畫面輸入時會被前端截斷，導致即使知道正確密碼，也無法正常登入。

最初我嘗試直接透過瀏覽器修改表單，例如調整 HTML、移除 `maxlength` 後重新提交，但並沒有成功修復問題。後來我改用 Burp Suite 手動構造 HTTP request，流程大致如下：

1. 攔截登入 request
2. 在成功登入後取得 session cookie
3. 取出 `JSESSIONID`
4. 手動構造修改密碼的 request
5. 在 request 中附帶該 session cookie
6. 發送新的密碼修改請求

透過這個方式，我成功讓 server 接受新的密碼，並恢復帳號登入。

這次經驗讓我更清楚理解幾件事：

- 前端驗證並不等於安全
- HTTP request 可以被完整重構與重送
- Session cookie 是登入狀態維持的核心
- Burp Suite 不只是漏洞測試工具，也是一個很好的 HTTP protocol 學習工具

也正是因為在分析 request 的過程中，我確認缺曠查詢其實只是一個簡單的 POST request，才進一步促成這個自動查詢工具的實作。

## 未來計畫

- 支援排程執行，例如搭配 cron 定時檢查
- 只通知新增紀錄，避免重複推送相同內容
- 補上更完整的錯誤處理與重試機制
- 將查詢結果結構化輸出為 JSON 或 SQLite
- 補上測試與模組化重構，將登入、查詢、解析、通知拆分成獨立元件

## 注意事項

- 本工具依賴校務系統目前的頁面流程與欄位名稱，若校方修改系統，程式可能需要同步調整
- 請妥善保管 `.env` 中的帳號、密碼與 Webhook
- 請僅在合法且經授權的情境下進行測試與使用
