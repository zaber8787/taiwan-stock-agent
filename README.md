# 台股 AI 多 Agent 當沖與短線分析系統 (taiwan-stock-agent-private)

基於 **CrewAI** 框架打造的台股自動化多 Agent 股票分析與決策系統。整合多家數據源爬蟲（證交所 TWSE、奇摩股市 Yahoo Finance、鉅亨網 Anue、公開資訊觀測站 MOPS、PTT 股票板等），搭配 **MongoDB** 行情儲存與 **Qdrant** 向量資料庫，並由大語言模型（如 `qwen2.5:7b`）進行深度研究、新聞分析、技術面計算與綜合交易決策。

---

## 🌟 核心功能與特色

- **多 Agent 協作鏈 (CrewAI Pipeline)**：
  1. 🕵️‍♂️ **Researcher (台股研究員)**：自動爬取目標個股近期 OHLCV、三大法人買賣超、產業新聞與 PTT 社群情緒。
  2. 📰 **NewsAnalyst (新聞分析師)**：評估新聞利多/利空因素，並利用 Qdrant 進行向量相似度新聞檢索與企業檔分析。
  3. 📈 **PriceAnalyst (技術分析師)**：計算 RSI (14)、MACD (12, 26, 9)、Bollinger Bands (20, 2σ)、EMA-20/60 等指標並分析量價結構。
  4. 🎯 **DecisionMaker (決策主管)**：綜合前三方分析與持倉狀態，給出最終交易訊號（`BUY` / `SELL` / `HOLD`）、信心度與目標價。
- **豐富數據源爬蟲**：
  - **證交所 TWSE**：個股與加權指數行情、三大法人每日買賣超數據 (`T86`)。
  - **Yahoo Finance TW (奇摩股市)**：歷史 K 線數據、即時報價、個股財經新聞。
  - **鉅亨網 (Anue)**：個股即時新聞、產業類股專題與內文解析。
  - **PTT Stock 板**：板塊文章爬取與多空社群情緒（Sentiment Score）計算。
  - **公開資訊觀測站 MOPS**：個股季度財報 (EPS) 與重大訊息。
  - **工商時報 & 東森財經**：總體經濟與產業新聞。
- **雙資料庫支援**：
  - **MongoDB**：儲存標的個股歷史價格 (`prices`)、企業檔案 (`companies`)、持倉紀錄 (`portfolio`) 與交易明細 (`trades`)。
  - **Qdrant**：768 維新聞密集向量（Embeddings）檢索。

---

## 📁 專案目錄結構

```text
taiwan-stock-agent-private/
├── app/
│   └── main.py                  # 專案主控制流程與 CLI 進入點 (crawl / run 模式)
├── agents/
│   ├── team.py                  # CrewAI 任務編排 (Research, News, Price, Decision)
│   ├── decision_maker.py        # 決策主管 Agent 邏輯與提示詞
│   ├── researcher_agent.py      # 資料研究員 Agent
│   ├── news_analyst_agent.py    # 新聞分析師 Agent
│   ├── price_analyst_agent.py   # 技術分析師 Agent
│   ├── models.py                # TradeSignal, PortfolioSnapshot 等資料模型
│   ├── config.py                # Agent 與 LLM 配置 (Ollama / Qwen)
│   └── tools/                   # Agent 自訂工具集
│       ├── research_tools.py    # 爬蟲與數據獲取 Tool
│       ├── analyst_tools.py     # 技術指標、向量搜尋 Tool
│       ├── decision_tools.py    # 風控下單試算與報告生成 Tool
│       └── base.py              # BaseTool 基礎類別
├── crawlers/
│   ├── twse_crawler.py          # TWSE 證交所 API 爬蟲
│   ├── twse_fund_crawler.py     # 三大法人買賣超爬蟲
│   ├── yfinance_crawler.py      # Yahoo Finance 歷史/即時 K 線爬蟲
│   ├── anue_crawler.py          # 鉅亨網新聞爬蟲
│   ├── ptt_stock_crawler.py     # PTT 股票板爬蟲與情緒計算
│   ├── mops_crawler.py          # 公開資訊觀測站爬蟲
│   ├── yahoo_twt_crawler.py     # 奇摩股市爬蟲
│   ├── ecb_newspaper_crawler.py # 東森財經新聞爬蟲
│   ├── changshang_crawler.py    # 工商時報新聞爬蟲
│   └── config.py                # 爬蟲 User-Agent 與延遲設定
├── db/
│   ├── mongo_client.py          # MongoDB 客戶端與 CRUD 封裝
│   ├── qdrant_manager.py        # Qdrant 向量檢索管理器
│   ├── base_client.py           # 資料庫抽象基礎類別
│   └── schemas/                 # Pydantic 結構定義
│       ├── price_schema.py      # K 線行情 Schema
│       ├── news_schema.py       # 新聞與向量 Schema
│       ├── trade_schema.py      # 交易明細 Schema
│       ├── company_schema.py    # 企業基本面 Schema
│       └── portfolio_schema.py  # 投資組合 Schema
├── data/                        # 原始資料暫存
├── reports/                     # 產出的交易報告與摘要
├── requirements.txt             # 專案依賴套件清單
└── README.md                    # 專案說明文件
```

---

## 🚀 快速開始 (Quick Start)

### 1. 環境需求
- **Python**: `>= 3.11`
- **MongoDB** *(選填)*: 預設運行於 `localhost:27017`
- **Qdrant** *(選填)*: 預設運行於 `localhost:6333`
- **Ollama** *(若需本機 LLM)*: 安裝並拉取 `qwen2.5:7b` 模型

### 2. 安裝依賴套件
```bash
pip install -r requirements.txt
```

### 3. 使用 CLI 運行

#### 🔹 模式一：僅收集數據 (Crawl Mode)
只觸發各家爬蟲採集台積電 (2330.TW) 的即時行情、新聞與證交所數據，不消耗 LLM：
```bash
python -m app.main crawl 2330.TW
```

#### 🔹 模式二：完整 Agent 分析與決策 (Run Mode)
啟動完整的 CrewAI 4 Agent 鏈，產出綜合交易建議與 Markdown 報告：
```bash
python -m app.main run 2330.TW -v
```

#### 🔹 模式三：直接啟動團隊任務
```bash
python -m agents.team 2330
```

---

## ⚙️ 配置說明 (Configuration)

- **LLM 設定**：預設連接 Ollama `qwen2.5:7b`，亦可在 `agents/config.py` 中切換模型或 API 端點。
- **爬蟲間隔**：可在 `crawlers/config.py` 調整 `scraping_delay_min` 與 `scraping_delay_max` 避免請求過度頻繁。
- **資料庫連線**：
  - MongoDB 預設資料庫名稱：`stock_agent`
  - Qdrant 預設集合名稱：`news_vectors` (768 維，Cos 距離)

---

## 📝 授權說明
本專案僅供學術研究與個股分析實驗使用，不構成任何投資建議。
