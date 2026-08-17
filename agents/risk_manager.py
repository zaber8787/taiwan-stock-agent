# File: agents/risk_manager.py
"""
🛡️ 獨立風控經理 (RiskManager)
負責在 DecisionMaker 產出交易訊號後，進行獨立的事前風控審核 (Pre-trade Risk Check)、
部位調整 (Position Sizing)、市場狀態動態連動 (Market Regime)、
停損停利點位設定與大盤/產業集中度風險攔截。
"""
from __future__ import annotations
import logging
import os
from typing import Any, Optional, Dict
from agents.config import tools_for_category, llm_for_crewai
from agents.models import TradeSignal, TradeSide, RiskStatus, RiskAssessment
from crawlers.chip_analyzer import analyze_chip_microstructure
from crawlers.industry_graph import TAG_TO_COMPANIES
from crawlers.market_regime import detect_market_regime, MarketRegime, StrategyMode
from db.paper_trader import get_paper_trader

try:
    from crewai import Agent
    HAS_CREWAI = True
except ImportError:
    HAS_CREWAI = False
    Agent = Any

logger = logging.getLogger(__name__)

_ROLE = '🛡️ 風控經理 (Risk Manager)'
_GOAL = '審查交易策略的下行風險、大盤市場狀態 (多頭/空頭/盤整)、產業集中度與部位資金合規性，擁有修正部位與一票否決權。'
_BACKSTORY = (
    '你是一位極度自律且保守的風控主管，專門守護投資組合的本金安全。'
    '你精通台股市場狀態（多頭順勢 100% 撥款、空頭防守現金為王、盤整區間短打），'
    '嚴格執行單一產業 50% 集中度上限、單檔 20% 資金上限與動態停損停利規則。'
)


def create_risk_manager_agent(ticker: str | None = None) -> Any:
    """創建獨立風控經理 Agent"""
    if not HAS_CREWAI:
        return None
    tools = tools_for_category('risk')
    llm = llm_for_crewai('risk_manager')
    return Agent(
        role=_ROLE,
        goal=_GOAL,
        backstory=_BACKSTORY,
        llm=llm,
        tools=tools,
        allow_delegation=False,
        verbose=True
    )


def evaluate_trade_risk(
    ticker: str,
    signal: TradeSignal | dict[str, Any],
    current_price: Optional[float] = None
) -> RiskAssessment:
    """
    執行全面獨立的事前風控審查 (Pre-trade Risk Evaluation)。
    
    規則矩陣：
    1. 【市場狀態連動】: 偵測大盤 (BULL/BEAR/RANGING)，動態決定撥款乘數與停損停利幅度。
    2. 【現金充裕性】: 是否足夠購買 1 張 (1,000 股)？不足則 REJECTED。
    3. 【空頭逆勢保護】: 空頭市場信心度 < 80% 一票否決 (REJECTED)。
    4. 【單檔與張數上限】: 單檔不超過 20% 本金，最大 10 張。
    5. 【產業集中度上限】: 單一產業總市值不超過總資金 50%。
    6. 【隔日沖籌碼警示】: 隔日沖券商佔比過高時，縮減部位 50%。
    7. 【動態出場點位】: 根據市場狀態精確計算停損、停利與時間出場點。
    """
    clean_ticker = ticker.replace('.TW', '')
    
    # 統一轉換為 TradeSignal 物件
    if isinstance(signal, dict):
        sig = TradeSignal.from_dict(signal)
    else:
        sig = signal

    side = sig.side.value if hasattr(sig.side, 'value') else str(sig.side)
    confidence = float(sig.confidence) if sig.confidence is not None else 0.5

    # 1. 非 BUY 訊號（HOLD 或 SELL），直接核准或維持現狀
    if side != 'BUY':
        if side == 'SELL':
            return RiskAssessment(
                status=RiskStatus.APPROVED,
                adjusted_shares=0,
                stop_loss_price=None,
                take_profit_price=None,
                max_holding_days=0,
                risk_factors=[],
                risk_rationale="【賣出平倉審核】同意賣出平倉指令，釋放資金以規避後續風險。"
            )
        else:  # HOLD
            return RiskAssessment(
                status=RiskStatus.APPROVED,
                adjusted_shares=0,
                stop_loss_price=None,
                take_profit_price=None,
                max_holding_days=4,
                risk_factors=[],
                risk_rationale="【觀望審核】維持觀望 (HOLD)，目前無新增下行風險敞口。"
            )

    # 2. 獲取帳戶與行情資料
    pt = get_paper_trader()
    acct = pt.get_account_summary()
    cash = acct.get('cash', 0.0)
    total_equity = acct.get('total_equity', 1000000.0)
    
    # 決定股票價格 (嚴禁使用假預設值，若無真實價格則一票否決)
    price = current_price or 0.0
    if price <= 0:
        price = pt._get_latest_price(clean_ticker)
    if price <= 0:
        return RiskAssessment(
            status=RiskStatus.REJECTED,
            adjusted_shares=0,
            stop_loss_price=None,
            take_profit_price=None,
            max_holding_days=0,
            risk_factors=[f"無法獲取標的 {clean_ticker} 之有效即時行情價格 (Price <= 0)"],
            risk_rationale=f"【風控拒單】標的 {clean_ticker} 行情報價異常或為 0，為防止錯誤計價與穿價風險，予以一票否決！"
        )

    # 取得大盤狀態 (Market Regime) 與微觀特徵指標
    from crawlers.feature_engine import extract_microstructure_features
    feats = extract_microstructure_features(clean_ticker)
    market_state = detect_market_regime()
    chip_info = analyze_chip_microstructure(clean_ticker)

    risk_factors: list[str] = []
    status = RiskStatus.APPROVED

    # --- 檢驗 0: 策略規劃書剛性波動度與信用底線過濾 ---
    if feats.atr_5d_pct < 2.5:
        return RiskAssessment(
            status=RiskStatus.REJECTED,
            adjusted_shares=0,
            stop_loss_price=round(price * 0.96, 2),
            take_profit_price=round(price * 1.06, 2),
            max_holding_days=2,
            risk_factors=[f"5日真實波幅過低 (ATR% {feats.atr_5d_pct:.2f}% < 2.5%)"],
            risk_rationale="【風控拒單】個股 5 日 ATR% 低於 2.5%，獲利空間受限難以覆蓋交易摩擦成本，予以排除。"
        )

    if feats.margin_maintenance_ratio < 140.0:
        return RiskAssessment(
            status=RiskStatus.REJECTED,
            adjusted_shares=0,
            stop_loss_price=round(price * 0.94, 2),
            take_profit_price=round(price * 1.10, 2),
            max_holding_days=1,
            risk_factors=[f"融資維持率瀕臨斷頭線 ({feats.margin_maintenance_ratio:.1f}% < 140%)"],
            risk_rationale=f"【風控拒單】{clean_ticker} 融資維持率僅 {feats.margin_maintenance_ratio:.1f}%，具追繳斷頭連環殺風險，嚴禁做多。"
        )

    # 計算基準撥款與建議張數 (動態乘以市場狀態撥款係數)
    max_capital_pct = float(os.getenv('MAX_CAPITAL_ALLOCATION_PCT', '0.20'))
    max_stock_pct = float(os.getenv('MAX_SINGLE_STOCK_PCT', '0.20'))
    max_lots = int(os.getenv('MAX_SINGLE_STOCK_LOTS', '10'))
    max_industry_pct = float(os.getenv('MAX_INDUSTRY_PCT', '0.50'))

    # 單筆動態預算 = 現金 * 20% * 信心度 * 市場狀態係數 (1.0 / 0.6 / 0.3)
    regime_mult = market_state.allocation_multiplier
    budget = cash * max_capital_pct * confidence * regime_mult
    lot_cost = price * 1000 * 1.005  # 含滑價

    # --- 檢驗 1: 市場狀態專屬濾網 (Market Regime Guard) ---
    if market_state.regime == MarketRegime.BEAR:
        risk_factors.append(f"大盤處於【{market_state.regime_name_zh}】格局 (MA20空頭反壓)")
        if confidence < 0.80:
            return RiskAssessment(
                status=RiskStatus.REJECTED,
                adjusted_shares=0,
                stop_loss_price=round(price * (1.0 + (market_state.suggested_stop_loss_pct / 100.0)), 2),
                take_profit_price=round(price * (1.0 + (market_state.suggested_take_profit_pct / 100.0)), 2),
                max_holding_days=market_state.suggested_max_holding_days,
                risk_factors=risk_factors,
                risk_rationale=f"【風控拒單】當前處於{market_state.regime_name_zh}，個股信心度 ({confidence:.0%}) 未達 80% 極強門檻，禁止逆勢追高。"
            )
        else:
            status = RiskStatus.ADJUSTED
            risk_factors.append("空頭市場高信心強勢股，強制縮減撥款至 30% 並緊縮停損")

    elif market_state.regime == MarketRegime.RANGING:
        risk_factors.append(f"大盤處於【{market_state.regime_name_zh}】(月線糾結狹幅震盪)")
        if confidence < 0.65:
            status = RiskStatus.ADJUSTED
            risk_factors.append("盤整市場信心度一般，撥款限縮為 60%")

    # --- 檢驗 2: 現金充裕性 ---
    if cash < lot_cost:
        return RiskAssessment(
            status=RiskStatus.REJECTED,
            adjusted_shares=0,
            stop_loss_price=round(price * (1.0 + (market_state.suggested_stop_loss_pct / 100.0)), 2),
            take_profit_price=round(price * (1.0 + (market_state.suggested_take_profit_pct / 100.0)), 2),
            max_holding_days=market_state.suggested_max_holding_days,
            risk_factors=['可用現金不足以購買 1 張整股 (1,000股)'],
            risk_rationale=f"【風控拒單】當前可用現金 ${cash:,.0f} 小於購買 1 張所需資金 ${lot_cost:,.0f}，拒絕透支下單。"
        )

    if budget < lot_cost:
        # 動態預算小於 1 張，嘗試以可用現金可買 1 張做微調，但若 confidence 過低或空頭則拒絕
        if confidence < 0.60 or market_state.regime == MarketRegime.BEAR:
            return RiskAssessment(
                status=RiskStatus.REJECTED,
                adjusted_shares=0,
                stop_loss_price=round(price * (1.0 + (market_state.suggested_stop_loss_pct / 100.0)), 2),
                take_profit_price=round(price * (1.0 + (market_state.suggested_take_profit_pct / 100.0)), 2),
                max_holding_days=market_state.suggested_max_holding_days,
                risk_factors=['信心度偏低且動態預算不足 1 張'],
                risk_rationale=f"【風控拒單】計算撥款預算不足 1 張 (市場係數 {regime_mult}x)，予以攔截保護本金。"
            )
        suggested_lots = 1
        status = RiskStatus.ADJUSTED
        risk_factors.append('撥款預算邊緣，微調以最低 1 張進場')
    else:
        suggested_lots = int(budget // lot_cost)

    # 限制最大張數
    if suggested_lots > max_lots:
        suggested_lots = max_lots
        status = RiskStatus.ADJUSTED
        risk_factors.append(f'觸發單檔最大張數上限 ({max_lots} 張)')

    # --- 檢驗 3: 單檔股票資金佔比限制 (<= 20% 總權益) ---
    existing_holding = next((h for h in acct.get('holdings', []) if h['ticker'] == clean_ticker), None)
    existing_val = existing_holding['current_val'] if existing_holding else 0.0
    new_val = suggested_lots * 1000 * price
    
    if (existing_val + new_val) > (total_equity * max_stock_pct):
        allowed_val = max(0.0, (total_equity * max_stock_pct) - existing_val)
        allowed_lots = int(allowed_val // (price * 1000))
        if allowed_lots < 1:
            return RiskAssessment(
                status=RiskStatus.REJECTED,
                adjusted_shares=0,
                stop_loss_price=round(price * (1.0 + (market_state.suggested_stop_loss_pct / 100.0)), 2),
                take_profit_price=round(price * (1.0 + (market_state.suggested_take_profit_pct / 100.0)), 2),
                max_holding_days=market_state.suggested_max_holding_days,
                risk_factors=[f'單檔標的已達持倉資金上限 ({max_stock_pct:.0%})'],
                risk_rationale=f"【風控拒單】{clean_ticker} 現有持倉與新增買入將超過單檔 {max_stock_pct:.0%} 限制，拒絕再加倉。"
            )
        if allowed_lots < suggested_lots:
            suggested_lots = allowed_lots
            status = RiskStatus.ADJUSTED
            risk_factors.append(f'單檔佔比超標，張數限縮為 {suggested_lots} 張')

    # --- 檢驗 4: 產業集中度限制 (<= 50% 總權益) ---
    target_industry = "其他"
    for tag, tickers in TAG_TO_COMPANIES.items():
        if clean_ticker in tickers:
            target_industry = tag
            break
            
    industry_exposure = 0.0
    for h in acct.get('holdings', []):
        h_ticker = h['ticker']
        for tag, tickers in TAG_TO_COMPANIES.items():
            if h_ticker in tickers and tag == target_industry:
                industry_exposure += h['current_val']
                break
                
    if (industry_exposure + (suggested_lots * 1000 * price)) > (total_equity * max_industry_pct):
        allowed_ind_val = max(0.0, (total_equity * max_industry_pct) - industry_exposure)
        allowed_ind_lots = int(allowed_ind_val // (price * 1000))
        if allowed_ind_lots < 1:
            return RiskAssessment(
                status=RiskStatus.REJECTED,
                adjusted_shares=0,
                stop_loss_price=round(price * (1.0 + (market_state.suggested_stop_loss_pct / 100.0)), 2),
                take_profit_price=round(price * (1.0 + (market_state.suggested_take_profit_pct / 100.0)), 2),
                max_holding_days=market_state.suggested_max_holding_days,
                risk_factors=[f'產業集中度超標 ({target_industry} > {max_industry_pct:.0%})'],
                risk_rationale=f"【風控拒單】所屬【{target_industry}】產業持倉已逼近 {max_industry_pct:.0%} 上限，予以攔截分散風險。"
            )
        if allowed_ind_lots < suggested_lots:
            suggested_lots = allowed_ind_lots
            status = RiskStatus.ADJUSTED
            risk_factors.append(f'【{target_industry}】產業集中度受限，張數調整為 {suggested_lots} 張')

    # --- 檢驗 5: 籌碼隔日沖警示 ---
    if chip_info and chip_info.get('has_next_day_warning'):
        risk_factors.append('分點偵測到顯著隔日沖籌碼進駐 (明日開盤賣壓高)')
        adjusted_down = max(1, suggested_lots // 2)
        if adjusted_down != suggested_lots:
            suggested_lots = adjusted_down
            status = RiskStatus.ADJUSTED
            risk_factors.append(f'隔日沖賣壓警示，部位縮減至 {suggested_lots} 張')

    # 確保最終至少 1 張 (1000 股)
    final_shares = max(1, suggested_lots) * 1000

    # 根據市場狀態動態計算出場點位
    stop_loss_pct = market_state.suggested_stop_loss_pct       # 如 -6.0% (多頭) 或 -4.0% (盤整) 或 -3.0% (空頭)
    take_profit_pct = market_state.suggested_take_profit_pct   # 如 +10.0% (多頭) 或 +6.0% (盤整) 或 +5.0% (空頭)
    max_days = market_state.suggested_max_holding_days

    stop_loss = round(price * (1.0 + (stop_loss_pct / 100.0)), 2)
    take_profit = round(price * (1.0 + (take_profit_pct / 100.0)), 2)

    # 組合風控裁決說明
    rationale_parts = []
    if status == RiskStatus.APPROVED:
        rationale_parts.append(f"【風控審批通過】當前大盤為【{market_state.regime_name_zh}】，各項指標合規，核准以 {suggested_lots} 張進場。")
    elif status == RiskStatus.ADJUSTED:
        rationale_parts.append(f"【風控調整後核准】配合大盤【{market_state.regime_name_zh}】與風險因子，已修正為 {suggested_lots} 張。")
    
    rationale_parts.append(f"依市場狀態設定動態停損價 ${stop_loss:,.2f} ({stop_loss_pct:+.1f}%)、動態停利點 ${take_profit:,.2f} ({take_profit_pct:+.1f}%)、T+{max_days} 時間出場。")
    if risk_factors:
        rationale_parts.append(f"風險告警: {'; '.join(risk_factors)}。")

    return RiskAssessment(
        status=status,
        adjusted_shares=final_shares,
        stop_loss_price=stop_loss,
        take_profit_price=take_profit,
        max_holding_days=max_days,
        risk_factors=risk_factors,
        risk_rationale=" ".join(rationale_parts)
    )
