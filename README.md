# 台股 AI 多 Agent 全自動事件驅動當沖與模擬交易系統

基於 **CrewAI** 多智慧體框架、**FastAPI** 高效 Web 伺服器、**Qdrant** 向量資料庫與 **Discord Webhook** 即時推播打造的台股全自動化、事件驅動 (Event-Driven) 股票分析與微觀籌碼模擬交易系統。

系統具備 **科技股與 ETF 自動掃描建檔**、**背景即時新聞事件監聽與分類**、**4 大 AI Agent 協作鏈**、**多空辯論系統 (Multi-Agent Debate)**、**盤勢狀態偵測 (Market Regime)**、**動態本金風控撥款引擎**、**盤中即時洗價與停損停利守護**、**特徵工程與回測期望值引擎**、**即時 Discord Webhook 推播** 以及 **暗黑擬物風格 Web GUI 指揮中心**。

---

## 🏗️ 完整系統架構 (System Architecture)

```mermaid
flowchart TD
    subgraph 1_Data_Layer ["1. 數據與爬蟲層 (Data Layer)"]
        TWSE["🏛️ 證交所 API (加權指數 / T86三大法人)"]
        YF["📈 Yahoo Finance (即時報價 / K線)"]
        ANUE["📰 鉅亨網 (Anue 財經即時新聞)"]
        MOPS["📊 公開資訊觀測站 (EPS / 財報)"]
        PTT["💬 PTT 股票板 (散戶情緒分數)"]
        CT["🗞️ 工商時報 / 經濟日報 (產業新聞)"]
    end

    subgraph 2_Auto_Core ["2. 全自動掃描與事件監聽核心"]
        REGIME["🌐 盤勢狀態偵測器 (market_regime.py)\nBULL / BEAR / RANGING 決定撥款與停損參數"]
        SCANNER["🔍 科技股/ETF 掃描器 (stock_scanner.py)\n自動清查 28 檔標的並補齊缺檔資料"]
        LISTENER["📡 背景新聞監聽器 (news_listener.py)\n每 3 分鐘輪詢新聞與關鍵字比對"]
        CLASSIFIER["🏷️ 事件分類器 (event_classifier.py)\n財報/併購/供應鏈/總經等 7 類事件歸類"]
        SCHEDULER["⏰ 排程觀察器 (watch_scheduler.py)\n管理 WATCH 標的與開收盤狀態判定"]
    end

    subgraph 3_Agent_Chain ["3. CrewAI Agent 協作研判鏈 + 多空辯論"]
        RESEARCHER["🕵️‍♂️ Researcher (台股研究員)\n搜集個股 K線/法人/新聞/PTT情緒"]
        NEWS_ANALYST["📰 NewsAnalyst (新聞分析師)\n分析新聞利多利空 + Qdrant 語意檢索"]
        PRICE_ANALYST["📈 PriceAnalyst (技術分析師)\n計算 RSI / MACD / 布林通道 / 均線"]
        DEBATE["⚖️ 多空辯論系統 (debate_system.py)\nBull vs Bear → Moderator → Judge 覆核決策"]
        DECISION_MAKER["🎯 DecisionMaker (決策主管)\n綜合研判產出 TradeSignal (BUY/SELL/HOLD)"]
    end

    subgraph 4_Paper_Trading ["4. 動態風控與模擬盤交易引擎 (Paper Trader Engine)"]
        CASH_CHECK["💰 剩餘現金檢查 (Available Cash Check)"]
        BUDGET_CALC["🛡️ 動態撥款算額:\n預算 = 現金 × 上限% × AI信心度 × 盤勢係數"]
        AFFORD_CHECK["⛔ 現金充裕性驗證 (不足 1 張自動退單)"]
        WASHER["🌊 盤中洗價守護 (realtime_washer.py)\nTick 級 -6% 停損 / +10% 移動停利 / 漲停鎖死標記"]
        RISK_RULES["⚡ 出場規則:\n-6% 剛性停損 / +10% 移動停利 / T+4 時間出場"]
        EXECUTION["⚡ 扣除手續費 (0.0285%) 與證交稅 (0.15%~0.30%)\n更新持倉、現金與未/已實現損益"]
    end

    subgraph 5_Notification ["5. 即時通知與展示層 (Presentation & Push)"]
        DISCORD["🔔 Discord Webhook 推播器 (notifier.py)\n發送買賣成交 / 新聞 / 風控告警 Rich Embeds"]
        SERVER["🌐 FastAPI 伺服器 (app/server.py)"]
        GUI["🖥️ 暗黑擬物風格 Web GUI (http://127.0.0.1:8000)\n包含: 資產卡片, 新聞牆, 撥款預覽, 持倉表, 報告Drawer"]
    end

    TWSE & YF & ANUE & MOPS & PTT & CT --> SCANNER & LISTENER
    TWSE --> REGIME
    SCANNER -->|自動建檔| MONGO[🗄️ MongoDB (companies/prices/portfolio)]
    LISTENER --> CLASSIFIER
    LISTENER -->|向量寫入| QDRANT[⚡ Qdrant (news_vectors 768維)]
    CLASSIFIER -->|重大事件| RESEARCHER
    REGIME --> BUDGET_CALC
    RESEARCHER --> NEWS_ANALYST --> PRICE_ANALYST --> DEBATE --> DECISION_MAKER
    DECISION_MAKER --> CASH_CHECK --> BUDGET_CALC --> AFFORD_CHECK --> EXECUTION
    EXECUTION --> WASHER --> RISK_RULES
    RISK_RULES --> DISCORD
    EXECUTION --> SERVER --> GUI
    LISTENER -->|新聞廣播| DISCORD
```

---

## 🌟 核心模組與功能亮點

### 1. 🔔 即時 Discord Webhook 推播模組 (`app/notifier.py`)
系統全面整合 Discord Webhook，使用 **Discord Rich Embeds** 彩色卡片格式發送各類即時事件通知：
- 🟢 **買進成交通知 (BUY)**：標的代碼、成交單價、張數與股數、總投入金額、券商手續費、AI 信心度、可用現金餘額及研判理由。
- 🔴 **賣出平倉成交通知 (SELL)**：賣出單價、淨回收金額、實現損益（PnL）、報酬率（ROI %）、證交稅率（含當沖降稅標記）、出場觸發理由。
- 📰 **重大新聞事件推播 (News Event)**：新聞標題、摘要、關聯個股與產業、事件分類、AI 漲跌預判（看多/看空/觀望）及信心指數。
- 🛡️ **風控攔截與停損告警 (Risk Alert)**：剛性停損觸發、移動停利鎖定、單一產業或標的持倉超額攔截。
- 🧪 **系統開機與連線測試 (System Test)**：開機自檢、API 測試推播連線。
- **安全降級與非同步機制**：採用 ThreadPool/非同步發送，不阻塞交易撮合；若未設定 Webhook URL 則自動略過，不影響系統運作。

### 2. 🔍 科技股與 ETF 自動掃描與深度建檔 (`crawlers/stock_scanner.py`)
- **全市場標的清查**：預設覆蓋半導體與 AI 伺服器供應鏈（2330, 2454, 2303, 3034, 2382, 3231, 2317 等）與高息/市值 ETF（0050, 0056, 00878, 00919, 00929, 00940）共 28 檔標的，各附產業標籤圖譜。
- **自動缺檔補齊**：啟動時自動檢查資料庫；若發現未建檔標的，立刻爬取 MOPS 季報財報與 yfinance K 線數據，完成持久化存儲（支援 MongoDB 與本地 JSON 備份檔）。

### 3. 📡 即時新聞事件監聽、分類與驅動 (`app/news_listener.py` & `crawlers/event_classifier.py`)
- **背景輪詢**：預設每 180 秒自動抓取鉅亨網 (Anue)、PTT 股票板與產業報紙最新文章。
- **事件智能分類**：自動將新聞歸類為財報營收、併購擴產、監管法規、供應鏈訂單、董監庫藏股、總經政策、市場傳聞等 7 大事件類型並判定急迫度。
- **個股關聯比對與向量化**：精確識別新聞中的台股代碼與產業鏈，並將新聞語意寫入 Qdrant 向量資料庫（768 維）。
- **事件驅動自動交易**：當 AI 信心度 $\ge 70\%$ 且給出強烈買賣訊號時，自動連動模擬交易引擎下單。

### 4. ⚖️ 多空辯論系統 (Multi-Agent Debate) (`agents/debate_system.py`)
在 CrewAI 四代理鏈產出初步決策後，自動進入對抗式辯論覆核：
- 🐂 **Bull Agent（看多研究員）** 與 🐻 **Bear Agent（看空研究員）** 輪流攻防，各最多 `DEBATE_MAX_ROUNDS`（預設 3）輪。
- 🎯 **Moderator** 控場並偵測辯論崩潰（鬼打牆/離題），🏆 **Judge** 依據論點強度評估產出最終裁決。
- 辯論結論**覆蓋**原 Crew 決策，辯論摘要一併寫入交易報告（`DEBATE_ENABLED=false` 可停用）。

### 5. 🌐 盤勢狀態自適應引擎 (`crawlers/market_regime.py`)
以加權指數均線結構（20MA/60MA）自動切換交易參數：
- 🐂 **BULL（多頭）**：指數 > 20MA > 60MA，順勢做多，撥款上限 100%、停損 -6%。
- 🐻 **BEAR（空頭）**：指數 < 20MA < 60MA，防禦避險，撥款壓至 0~30%、停損收緊 -3%，拒絕弱勢追高。
- 🦀 **RANGING（盤整）**：指數於月線附近糾結，區間短打，撥款 50~60%、停損 -4%、T+2 快速出場。

### 6. 🛡️ 微觀籌碼與短線波段風控交易引擎 (`db/paper_trader.py` & `agents/risk_manager.py`)
- **動態加權撥款公式**：
  $$\text{下單預算 (Budget)} = \text{當前可用現金} \times \text{撥款上限} \times \text{AI 信心度 (0~1)} \times \text{盤勢係數}$$
- **台股真實摩擦成本計算**：
  - 券商手續費：`0.1425% × 0.20 = 0.0285%`（大戶 2 折合約，低消 20 元）。
  - 證交稅率：當日當沖避險出場享 `0.15%` 減半優惠，隔夜出場為 `0.30%`。
  - 滑價機制：買進市價 $+0.5\%$、賣出市價 $-0.5\%$。
- **微觀短線出場風控規則**：
  1. 🛑 **剛性避險停損 (-6%)**：盤中浮虧達 $-6\%$ 無條件市價平倉（當日發起享當沖降稅）。
  2. 🎯 **動態移動停利 (+10% 激活 / 2% 回檔)**：浮盈達 $+10\%$ 啟動追蹤，自波段最高價回檔 $2\%$ 時立即市價平倉鎖定獲利。
  3. ⌛ **高週轉時間離場 (T+4)**：持倉滿 3 個交易日未發動，於第 4 天強制平倉釋放資金。
  4. 📊 **產業集中度上限 (50%)**：單一產業（如半導體、電腦設備、ETF）總市值不得超過初始本金的 $50\%$，超額自動縮減張數。
  5. ⛔ **現金充裕性攔截**：預算不足購買 1 張（1,000 股）自動退單，避免超額透支。

### 7. 🌊 盤中即時洗價與停損停利守護器 (`app/realtime_washer.py` & `crawlers/tick_stream.py`)
- **毫秒級 Tick 串流**：接收或模擬持倉標的逐筆成交流，盤中即時重估浮損益。
- **盤中觸發即出**：-6% 剛性停損一經觸發立即以當沖方式平倉出場；+10% 後自高點回檔 2% 自動停利。
- **漲停鎖死偵測**：09:30 前鎖死漲停自動標記次日溢價跟單並 Discord 通報。

### 8. 🤖 特徵工程、ML Alpha 與回測期望值引擎 (`crawlers/feature_engine.py` / `ml/` / `backtest/`)
- **微觀籌碼特徵工程**：從真實歷史行情與法人數據提取 15+ 維特徵向量，杜絕寫死假預設值。
- **ML Alpha 預測器**：以 NumPy 手刻 GBDT（或 LightGBM 產出的 `ml/models/lgb_alpha_model.joblib`）對進場訊號做離線加權。
- **剛性進場篩選濾網** (`crawlers/rigid_screener.py`)：20 日均量 > 3,000 張且實收股本 < 50 億等交集條件，不合格標的不進 AI 撮合流水線。
- **歷史回測引擎** (`backtest/backtester.py`)：嚴格扣除手續費、證交稅與滑價，輸出勝率 (WR)、盈虧比 (PLR)、最大回撤 (MDD)、年化夏普比率 (Sharpe)。

### 9. 🖥️ 暗黑擬物風格 Web GUI 指揮中心 (`app/web/` & `app/server.py`)
- **資產概覽卡片 (Banner)**：實時顯示總資產 (Total Equity)、可用現金 (Cash)、持倉市值與累積報酬率 (ROI %)。
- **全自動即時新聞動態牆 (Live Event Feed)**：即時滑入背景監聽到的最新新聞、事件分類、關聯股票、AI 漲跌預判與下單結果。
- **全市場即時巡檢表 (Universe Watchlist)**：顯示 28 檔科技股與 ETF 的即時報價、AI 訊號、持倉狀態與更新時間。
- **排程觀察倒數看板 (Watchlist Timers)**：展示 AI 預約觀察標的倒數計時與補漲觀察原因。
- **模擬/實盤模式切換**：一鍵切換 Paper Trading 與 Real Trading（實盤預設關閉）。
- **Discord 推播狀態 Badge 與一鍵測試**：即時顯示 Webhook 狀態並提供「🔔 測試推播」按鈕。
- **報告檢視視窗 (Modal Drawer)**：點擊可展開檢視 AI 生成的 Markdown 完整交易決策報告（含辯論紀錄）。

---

## ⚙️ 全局環境變數對照表 (.env)

專案啟動時會自動載入根目錄下的 `.env` 檔案（範本見 `.env.example`）：

```ini
# ==========================================
# LLM 模型與 API 配置
# ==========================================
LLM_MODEL=qwen2.5:7b
LLM_BASE_URL=http://localhost:11434/v1
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=2000
OPENAI_API_KEY=                      # 或 LLM_API_KEY（相容 OpenAI 兼容端點）

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
MAX_POSITIONS_LIMIT=5              # 同時最大持倉檔數 (5 檔)
MAX_SINGLE_STOCK_PCT=0.20          # 單檔股票佔總資金上限 (20%)
MAX_SINGLE_STOCK_LOTS=10           # 單檔最大持有張數 (10 張)
MAX_INDUSTRY_PCT=0.50              # 單一產業集中度上限 (50%)

# ==========================================
# 交易模式切換 (Paper / Real)
# ==========================================
PAPER_TRADING_ENABLED=true         # 模擬盤（預設開啟）
REAL_TRADING_ENABLED=false         # 實盤（預設關閉，Web GUI 可一鍵切換）
TRADING_API_URL=                   # 實盤券商 API（預設留空）
TRADING_API_KEY=

# ==========================================
# 多空辯論系統 (Debate System)
# ==========================================
DEBATE_ENABLED=true                # 是否啟用多空辯論覆核 (true/false)
DEBATE_MAX_ROUNDS=3                # 辯論最大輪數 (建議 2-3 輪)

# ==========================================
# 全自動掃描與新聞監聽配置
# ==========================================
AUTO_SCAN_ON_STARTUP=true          # 啟動時是否自動掃描建檔
NEWS_POLL_INTERVAL_SECONDS=180     # 新聞輪詢監聽間隔 (秒)
DATA_REFRESH_INTERVAL_HOURS=24     # 行情與資料庫排程更新間隔 (小時)
AUTO_TRADER_INTERVAL_SECONDS=60    # 全市場巡檢引擎間隔 (秒)
MAX_PARALLEL_ANALYSIS=10           # 最大平行分析線程數
ANALYSIS_QUEUE_TIMEOUT=300         # 新聞分析佇列逾時 (秒)

# ==========================================
# 即時推播配置 (Discord Webhook Notifications)
# ==========================================
DISCORD_WEBHOOK_URL=               # 請貼上您的 Discord 頻道 Webhook URL
DISCORD_NOTIFICATIONS_ENABLED=true # 是否啟用推播 (true/false)
DISCORD_NOTIFY_ON_TRADE=true       # 是否推播模擬/實盤交易成交通知 (買進/賣出/平倉)
DISCORD_NOTIFY_ON_NEWS=true        # 是否推播重大財經新聞與 AI 研判事件
DISCORD_NOTIFY_ON_RISK=true        # 是否推播風控告警與攔截 (停損/停利/部位上限)

# ==========================================
# 爬蟲配置
# ==========================================
SCRAPING_DELAY_MIN=1.0
SCRAPING_DELAY_MAX=3.0
MAX_RETRIES=3
USER_AGENT=Mozilla/5.0 (compatible; StockAgent/1.0)
DEFAULT_TICKER=2330
```

---

## 📁 專案目錄結構

```text
stock-agent/
├── app/
│   ├── main.py                  # 專案 CLI 進入點 (gui / run / crawl 模式與開機檢測)
│   ├── server.py                # FastAPI Web 伺服器與 REST API 端點
│   ├── notifier.py              # Discord Webhook 即時推播器 (Rich Embeds)
│   ├── news_listener.py         # 背景即時新聞事件監聽器 (Event-Driven Trader)
│   ├── auto_trader.py           # 全市場 28 檔標的背景巡檢與自適應交易引擎
│   ├── realtime_washer.py       # 盤中即時洗價與停損停利守護器 (Tick 級出場)
│   ├── watch_scheduler.py       # 排程觀察管理器 (Watchlist Timers)
│   ├── market_hours.py          # 台股開收盤判定與國定假日行事曆
│   ├── scheduler.py             # 定時資料排程更新器
│   └── web/                     # Web GUI 前端介面
│       ├── index.html           # 儀表板 HTML (資產卡, 策略規則, 新聞牆, 巡檢表, 持倉表)
│       ├── style.css            # Glassmorphism 毛玻璃與暗黑擬物風格樣式
│       └── app.js               # 前端 AJAX 輪詢, 撥款預覽, 測試推播與動態渲染
├── agents/
│   ├── team.py                  # CrewAI 任務編排 (Research, News, Price, Decision + Debate)
│   ├── debate_system.py         # 多空辯論系統 (Bull/Bear/Moderator/Judge)
│   ├── decision_maker.py        # 決策主管 Agent 邏輯與提示詞
│   ├── researcher_agent.py      # 資料研究員 Agent
│   ├── news_analyst_agent.py    # 新聞分析師 Agent
│   ├── price_analyst_agent.py   # 技術分析師 Agent
│   ├── risk_manager.py          # 風控規則引擎 (部位/產業/現金流攔截)
│   ├── ml_predictor.py          # ML Alpha 預測器 (joblib 模型載入)
│   ├── models.py                # TradeSignal, PortfolioSnapshot, MarketRegime 資料模型
│   ├── config.py                # Agent 與 LLM 動態配置中心
│   └── tools/                   # Agent 自訂工具集 (技術指標/新聞檢索/持倉檢查)
├── crawlers/
│   ├── stock_scanner.py         # 台股科技股與 ETF 自動掃描與深度建檔器
│   ├── twse_crawler.py          # 證交所 API 爬蟲 (大盤/三大法人)
│   ├── twse_fund_crawler.py     # 證交所外資/投信/自營商細部統計
│   ├── yfinance_crawler.py      # Yahoo Finance 歷史/即時 K 線爬蟲
│   ├── yahoo_twt_crawler.py     # Yahoo 即時分時資料爬蟲
│   ├── anue_crawler.py          # 鉅亨網即時新聞爬蟲
│   ├── changshang_crawler.py    # 工商時報產業新聞爬蟲
│   ├── ecb_newspaper_crawler.py # 經濟日報財經新聞爬蟲
│   ├── ptt_stock_crawler.py     # PTT 股票板爬蟲與情緒計算
│   ├── mops_crawler.py          # 公開資訊觀測站季報 EPS 爬蟲
│   ├── tick_stream.py           # 盤中逐筆 Tick 串流處理器
│   ├── market_regime.py         # 盤勢狀態偵測器 (BULL/BEAR/RANGING)
│   ├── event_classifier.py      # 新聞事件分類器 (7 大事件類型)
│   ├── rigid_screener.py        # 剛性進場篩選濾網 (流動性/股本門檻)
│   ├── feature_engine.py        # 微觀籌碼與量價特徵工程引擎 (15+ 維)
│   ├── industry_graph.py        # 產業鏈關聯圖譜與標的標籤庫
│   └── chip_analyzer.py         # 籌碼集中度與法人動向計算器
├── db/
│   ├── paper_trader.py          # 模擬盤撮合、動態撥款與微觀出場風控引擎
│   ├── mongo_client.py          # MongoDB 客戶端與 CRUD 封裝 (含 Fallback)
│   ├── qdrant_manager.py        # Qdrant 向量檢索管理器 (768維新聞語意)
│   ├── base_client.py           # 資料庫抽象基礎類別
│   └── schemas/                 # Pydantic 結構定義 (Price, News, Trade, Portfolio)
├── ml/
│   ├── dataset_builder.py       # 特徵數據集構建器 (X, y 生成)
│   ├── train_ml_model.py        # GBDT/LightGBM Alpha 模型離線訓練
│   └── models/                  # 訓練產出模型 (lgb_alpha_model.joblib)
├── backtest/
│   └── backtester.py            # 歷史回測與數學期望值引擎 (WR/PLR/MDD/Sharpe)
├── reports/                     # AI 生成的 Markdown 決策報告輸出目錄
├── tests/
│   ├── test_notifier.py         # Discord 推播器單元測試
│   └── test_server_endpoints.py # FastAPI 端點整合測試
├── test_*.py                    # 根目錄一鍵整合測試腳本 (見下方「執行測試」)
├── DEBATE_SYSTEM.md             # 多空辯論系統實作說明
├── .env                         # 環境變數設定檔 (已加入 .gitignore)
├── .env.example                 # 環境變數範本檔
├── requirements.txt             # 專案依賴套件清單
└── README.md                    # 專案完整架構與說明文件
```

---

## 📡 REST API 端點一覽

| 路由端點 | 方法 | 說明 |
| :--- | :---: | :--- |
| `/` | `GET` | 載入 Web GUI 前端儀表板 (`index.html`) |
| `/api/account` | `GET` | 取得當前帳戶資金、持倉、未實現/已實現損益、ROI |
| `/api/trades` | `GET` | 取得歷史模擬交易紀錄列表（反序排列） |
| `/api/news-feed` | `GET` | 取得背景監聽到的即時新聞事件廣播牆 |
| `/api/news/queue` | `GET` | 取得新聞分析佇列排隊狀態 |
| `/api/watchlist` | `GET` | 取得目前排程觀察中的標的、原因與倒數秒數 |
| `/api/autotrader/universe` | `GET` | 取得全市場 28 檔標的最新即時行情與 AI 研判訊號 |
| `/api/autotrader/status` | `GET` | 取得全自動交易引擎運行狀態 |
| `/api/listener/status` | `GET` | 取得新聞監聽器與掃描器背景運行狀態 |
| `/api/market-status` | `GET` | 取得當前台股開收盤狀態判定 |
| `/api/market/regime` | `GET` | 取得盤勢狀態偵測結果 (Bull/Bear/Ranging) |
| `/api/trading-config` | `GET` | 取得模擬/實盤交易模式與風控參數設定 |
| `/api/trade/toggle` | `POST` | 切換 Paper / Real 交易模式（實盤預設關閉） |
| `/api/notify/status` | `GET` | 取得 Discord Webhook 推播配置與啟用狀態 |
| `/api/notify/test` | `POST` | 發送 Discord Webhook 測試卡片至指定頻道 |
| `/api/tags` | `GET` | 取得產業標籤圖譜與標的對照表 |
| `/api/reset` | `POST` | 100% 完全重置帳戶本金、持倉、交易紀錄與新聞牆 |
| `/api/db-status` | `GET` | 查詢 MongoDB 與 Qdrant 連線健康度 |
| `/api/stocks/analyze` | `GET` | 批量觸發指定多檔股票之 CrewAI 協同分析 |

---

## 🚀 快速開始 (Quick Start)

### 1. 安裝環境與依賴套件
```bash
# 建議使用 Python 3.10+
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. 設定環境變數
```bash
cp .env.example .env
```
編輯 `.env` 檔案：
- 若使用本地 Ollama：確保 `LLM_BASE_URL=http://localhost:11434/v1` 並已下載 `ollama pull qwen2.5:7b`。
- 若啟用 Discord 推播：將 `DISCORD_WEBHOOK_URL` 填入您的頻道 Webhook 網址。
- 資料庫（MongoDB / Qdrant）未啟動時系統會自動降級為本地 JSON 備份模式，可先跳過安裝。

### 3. 運行系統

#### 🔹 模式一：啟動全自動 Web GUI 指揮中心 (推薦)
```bash
python -m app.main gui            # 預設 port 8000，可加 --port 自訂
```
系統會自動在終端印出連線檢查表，啟動 FastAPI 服務，並開啟瀏覽器訪問 `http://127.0.0.1:8000`。在背景自動啟動新聞監聽、全市場巡檢、盤中洗價守護與 Discord 推播！

#### 🔹 模式二：單次 Agent 深度分析與下單
```bash
python -m app.main run 2330.TW
```

#### 🔹 模式三：僅單次爬取市場數據 (Crawl Mode)
```bash
python -m app.main crawl 2330.TW
```

### 4. 執行測試
```bash
# 單元與端點整合測試 (tests/ 目錄)
python -m unittest discover tests

# 根目錄整合測試腳本（直接執行，各自獨立）
python test_all_data_sources.py     # 全部資料源連通性驗證
python test_debate_system.py        # 多空辯論系統端到端驗證
python test_backtest_engine.py      # 回測引擎數值驗證
python test_risk_manager.py         # 風控規則驗證
python test_market_regime.py        # 盤勢偵測器驗證
```

---

## 📝 免責聲明 (Disclaimer)
本專案僅供學術研究、AI 多智慧體協作論文實驗與量化交易模擬測試使用。系統產出之所有分析結果、訊號與預測均不構成任何真實金融投資建議。真實投資具有風險，請投資人審慎評估。
