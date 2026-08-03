# 台股 AI 多 Agent 全自動事件驅動當沖與模擬交易系統 (taiwan-stock-agent-private)

基於 **CrewAI** 框架、**FastAPI** 與 **Qdrant** 向量資料庫打造的台股全自動化事件驅動 (Event-Driven) 股票分析與模擬下單系統。

系統具備 **科技股與 ETF 自動掃描建檔**、**背景即時新聞事件監聽**、**4 大 AI Agent 協作鏈**、**動態本金風控撥款引擎** 以及 **暗黑擬物風格 Web GUI 儀表板**。

---

## 🏗️ 完整系統架構 (System Architecture)

```mermaid
flowchart TD
    subgraph 1_Data_Layer ["1. 數據與爬蟲層 (Data Layer)"]
        TWSE["🏛️ 證交所 API (加權指數 / T86三大法人)"]
        YF["📈 Yahoo Finance (即時報價 / K線)"]
        ANUE["📰 鉅亨網 (Anue 財經新聞)"]
        MOPS["📊 公開資訊觀測站 (EPS / 財報)"]
        PTT["💬 PTT 股票板 (社群情緒)"]
    end

    subgraph 2_Auto_Core ["2. 全自動掃描與事件監聽核心"]
        SCANNER["🔍 科技股/ETF 掃描器 (stock_scanner.py)\n自動清查 23+ 檔標的並補齊缺檔資料"]
        LISTENER["📡 背景新聞監聽器 (news_listener.py)\n每 3 分鐘輪詢新聞與關鍵字比對"]
        SCHEDULER["⏰ 排程更新器 (scheduler.py)\n每 24h 定期更新全庫行情與基本面"]
    end

    subgraph 3_Agent_Chain ["3. CrewAI 4 大 Agent 協作研判鏈"]
        RESEARCHER["🕵️‍♂️ Researcher (台股研究員)\n搜集個股 K線/法人/新聞/PTT情緒"]
        NEWS_ANALYST["📰 NewsAnalyst (新聞分析師)\n分析新聞利多利空 + Qdrant 語意檢索"]
        PRICE_ANALYST["📈 PriceAnalyst (技術分析師)\n計算 RSI / MACD / 布林通道 / 均線"]
        DECISION_MAKER["🎯 DecisionMaker (決策主管)\n綜合研判產出 TradeSignal (BUY/SELL/HOLD)"]
    end

    subgraph 4_Paper_Trading ["4. 動態風控與模擬盤交易引擎 (Paper Trader Engine)"]
        CASH_CHECK["💰 剩餘現金檢查 (Available Cash Check)"]
        BUDGET_CALC["🛡️ 動態撥款算額:\n預算 = 現金 × 20%上限 × AI信心度"]
        AFFORD_CHECK["⛔ 現金充裕性驗證 (不足 1 張自動退單)"]
        EXECUTION["⚡ 扣除手續費 (0.1425%) 與證交稅 (0.3%)\n更新持倉、現金與未/已實現損益"]
    end

    subgraph 5_Presentation ["5. Web GUI 展示與 REST API"]
        SERVER["🌐 FastAPI 伺服器 (app/server.py)"]
        GUI["🖥️ 暗黑擬物風格 Web GUI (http://127.0.0.1:8000)\n包含: 資產卡片, 新聞牆, 撥款預覽, 持倉表, 報告Drawer"]
    end

    TWSE & YF & ANUE & MOPS & PTT --> SCANNER & LISTENER
    SCANNER -->|自動建檔| MONGO[🗄️ MongoDB (companies/prices/portfolio)]
    LISTENER -->|向量寫入| QDRANT[⚡ Qdrant (news_vectors 768維)]
    LISTENER -->|偵測到重大新聞| RESEARCHER
    RESEARCHER --> NEWS_ANALYST --> PRICE_ANALYST --> DECISION_MAKER
    DECISION_MAKER --> CASH_CHECK --> BUDGET_CALC --> AFFORD_CHECK --> EXECUTION
    EXECUTION --> SERVER --> GUI
```

---

## 🌟 核心模組詳細說明

### 1. 🔍 科技股與 ETF 自動掃描與深度建檔 (`crawlers/stock_scanner.py`)
- **標的清查**：預設覆蓋半導體 (2330, 2454, 2303等)、AI/伺服器 (2382, 3231, 2317等) 與熱門 ETF (0050, 0056, 00878, 00919, 00929, 00940 等)。
- **自動缺檔補齊**：啟動時自動比對資料庫；若發現無資料，立刻深度爬取 MOPS 財報與 yfinance K 線，完成基本面與行情建檔（持久化於 MongoDB 及 `data/companies.json`）。

### 2. 📡 即時新聞事件監聽與驅動 (`app/news_listener.py`)
- **背景輪詢**：預設每 180 秒（可在 `.env` 調整）自動抓取最新財經新聞與 PTT 文章。
- **自動比對與向量化**：辨識新聞內文個股代碼，自動寫入 Qdrant 向量資料庫（`news_vectors`）。
- **事件驅動交易**：自動傳送新聞至 4 大 Agent 研判。若 AI 信心度 $\ge 70\%$ 且給出強烈買賣訊號，自動連動模擬下單。

### 3. 🛡️ 動態風控撥款與模擬交易引擎 (`db/paper_trader.py`)
- **本金與撥款上限**：支援設定初始本金（預設 $1,000,000$ 台幣）與單筆上限比例（`MAX_CAPITAL_ALLOCATION_PCT=0.20`）。
- **信心度加權撥款公式**：
  $$\text{下單預算 (Budget)} = \text{當前可用現金} \times 20\% \times \text{AI 信心度 (0~1)}$$
- **現金充裕性攔截**：若預算不足以購買至少 1 張股票（1,000 股），系統自動攔截退單，避免超額透支。
- **真實交易摩擦成本**：扣除台股券商手續費 (`0.1425%`) 與賣出證交稅 (`0.3%`)，並即時計算未實現與已實現損益。

### 4. 🖥️ 暗黑擬物風格 Web GUI 儀表板 (`app/web/` & `app/server.py`)
- **資產概覽卡片 (Banner)**：實時顯示總資產 (Total Equity)、可用現金 (Cash)、持倉市值與累積報酬率 (ROI %)。
- **全自動即時新聞動態牆 (Live Event Feed)**：即時滑入背景監聽到的最新新聞、關聯股票、AI 漲跌預判與下單結果。
- **風控撥款預覽卡**：即時顯示現金、信心度、建議撥款金額與換算張數。
- **報告檢視視窗 (Modal Drawer)**：點擊可展開檢視 AI 生成的 Markdown 交易報告。

---

## ⚙️ 全局環境變數對照表 (.env)

專案啟動時會自動載入根目錄下的 `.env` 檔案：

```ini
# ==========================================
# LLM 模型與 API 配置
# ==========================================
LLM_MODEL=qwen2.5:7b
LLM_BASE_URL=http://localhost:11434/v1
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=2000
OPENAI_API_KEY=

# 可選：個別 Agent 獨立模型覆蓋 (若留空則使用 LLM_MODEL)
RESEARCHER_MODEL=
NEWS_ANALYST_MODEL=
PRICE_ANALYST_MODEL=
DECISION_MAKER_MODEL=

# ==========================================
# 資料庫配置 (MongoDB & Qdrant)
# ==========================================
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=stock_agent

QDRANT_URI=http://localhost:6333
QDRANT_COLLECTION_NAME=news_vectors
QDRANT_VECTOR_SIZE=768

# ==========================================
# 模擬盤與風控撥款配置
# ==========================================
INITIAL_CAPITAL=1000000            # 初始本金 (TWD)
MAX_CAPITAL_ALLOCATION_PCT=0.20    # 單筆撥款上限 (20%)

# ==========================================
# 全自動掃描與新聞監聽配置
# ==========================================
AUTO_SCAN_ON_STARTUP=true          # 啟動時是否自動掃描建檔
NEWS_POLL_INTERVAL_SECONDS=180     # 新聞輪詢監聽間隔 (秒)
DATA_REFRESH_INTERVAL_HOURS=24     # 行情與資料庫排程更新間隔 (小時)

# ==========================================
# 爬蟲配置
# ==========================================
SCRAPING_DELAY_MIN=1.0
SCRAPING_DELAY_MAX=3.0
MAX_RETRIES=3
USER_AGENT=Mozilla/5.0 (compatible; StockAgent/1.0; +https://stock-agent.ai)
DEFAULT_TICKER=2330
```

---

## 📁 專案目錄結構

```text
taiwan-stock-agent-private/
├── app/
│   ├── main.py                  # 專案 CLI 進入點 (gui / run / crawl 模式)
│   ├── server.py                # FastAPI Web 伺服器與 REST API 端點
│   ├── news_listener.py          # 背景即時新聞事件監聽器 (Event-Driven Trader)
│   ├── scheduler.py             # 定時資料排程更新器
│   └── web/                     # Web GUI 前端介面
│       ├── index.html           # 儀表板 HTML 結構 (新聞牆, 資產卡, 持倉表)
│       ├── style.css            # Glassmorphism 毛玻璃與暗黑擬物風格樣式
│       └── app.js               # 前端 AJAX 輪詢, 撥款預覽與動態渲染邏輯
├── agents/
│   ├── team.py                  # CrewAI 任務編排 (Research, News, Price, Decision)
│   ├── decision_maker.py        # 決策主管 Agent 邏輯與提示詞
│   ├── researcher_agent.py      # 資料研究員 Agent
│   ├── news_analyst_agent.py    # 新聞分析師 Agent
│   ├── price_analyst_agent.py   # 技術分析師 Agent
│   ├── models.py                # TradeSignal, PortfolioSnapshot 資料模型
│   ├── config.py                # Agent 與 LLM 動態配置中心
│   └── tools/                   # Agent 自訂工具集
├── crawlers/
│   ├── stock_scanner.py         # 台股科技股與 ETF 自動掃描與深度建檔器
│   ├── twse_crawler.py          # 證交所 API 爬蟲
│   ├── yfinance_crawler.py      # Yahoo Finance 歷史/即時 K 線爬蟲
│   ├── anue_crawler.py          # 鉅亨網新聞爬蟲
│   ├── ptt_stock_crawler.py     # PTT 股票板爬蟲與情緒計算
│   ├── mops_crawler.py          # 公開資訊觀測站爬蟲
│   └── config.py                # 爬蟲 User-Agent 與延遲設定
├── db/
│   ├── paper_trader.py          # 模擬盤交易與動態風控撥款引擎
│   ├── mongo_client.py          # MongoDB 客戶端與 CRUD 封裝
│   ├── qdrant_manager.py        # Qdrant 向量檢索管理器
│   ├── base_client.py           # 資料庫抽象基礎類別
│   └── schemas/                 # Pydantic 結構定義 (Price, News, Trade, Portfolio)
├── data/                        # 本地資料與帳戶狀態備份 (JSON Fallback)
├── .env                         # 環境變數設定檔
├── .env.example                 # 環境變數範本檔
├── requirements.txt             # 專案依賴套件清單
└── README.md                    # 專案架構說明文件
```

---

## 🚀 快速開始 (Quick Start)

### 1. 安裝依賴套件
```bash
pip install -r requirements.txt
```

### 2. 設定環境變數
```bash
cp .env.example .env
# 編輯 .env 設定您的 LLM 模型或 API Key
```

### 3. 使用 CLI 運行

#### 🔹 模式一：啟動全自動 Web GUI 與背景新聞監聽器 (推薦)
```bash
python -m app.main gui
```
> 系統會啟動 FastAPI 服務，自動打開瀏覽器 `http://127.0.0.1:8000`，並在背景自動完成科技股建檔與新聞監聽！

#### 🔹 模式二：單次 Agent 分析與模擬下單
```bash
python -m app.main run 2330.TW
```

#### 🔹 模式三：僅單次收集數據 (Crawl Mode)
```bash
python -m app.main crawl 2330.TW
```

---

## 📝 免責聲明
本專案僅供學術研究、AI 論文實驗與模擬交易測試使用，不構成任何真實金融投資建議。
