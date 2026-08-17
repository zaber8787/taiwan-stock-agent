# File: agents/debate_system.py
"""
多空辯論系統 - 模擬專業交易團隊的多空辯論機制

核心功能：
1. Bull/Bear 研究員對抗性分析
2. 多輪辯論機制 (2-3 輪)
3. 辯論主持人協調
4. 最終決策者綜合判斷

參考：TradingAgents 框架的多 Agent 辯論設計
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
import json
import asyncio

from agents.config import llm_for_crewai, tools_for_category

try:
    from crewai import Agent, Task, Crew, Process
    HAS_CREWAI = True
except ImportError:
    HAS_CREWAI = False
    Agent = Task = Crew = Process = Any

logger = logging.getLogger(__name__)
HERE = Path(__file__).resolve().parent


# ============================================================================
# 數據結構定義
# ============================================================================

@dataclass
class DebateArgument:
    """辯論論點"""
    side: str  # 'bull' or 'bear'
    main_points: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    counter_arguments: List[str] = field(default_factory=list)
    confidence: float = 0.5
    reasoning: str = ""


@dataclass
class DebateRound:
    """辯論回合"""
    round_number: int
    bull_argument: Optional[DebateArgument] = None
    bear_argument: Optional[DebateArgument] = None
    moderator_summary: str = ""
    key_disagreements: List[str] = field(default_factory=list)
    convergence_score: float = 0.0  # 0-1, 越高表示越接近共識


@dataclass
class DebateResult:
    """辯論結果"""
    ticker: str
    final_decision: str  # BUY/SELL/HOLD
    confidence: float
    reasoning: str
    bull_key_points: List[str] = field(default_factory=list)
    bear_key_points: List[str] = field(default_factory=list)
    debate_history: List[DebateRound] = field(default_factory=list)
    total_rounds: int = 0
    debate_quality: str = ""  # 辯論質量評估


# ============================================================================
# Agent 定義
# ============================================================================

def create_bull_agent() -> Any:
    """創建看多研究員 Agent"""
    if not HAS_CREWAI:
        return None
    
    llm = llm_for_crewai('bull_analyst')
    # 不傳遞工具，避免格式問題
    # tools = tools_for_category('research') + tools_for_category('analyst')
    
    return Agent(
        role='🐂 看多研究員 (Bull Analyst)',
        goal='找出所有支持買進的利多因素，包括基本面、技術面、消息面',
        backstory="""你是一位樂觀的台股研究員，專精於發現投資機會。

你的任務：
1. 從財報、營收成長、產業趨勢中找出利多
2. 識別技術面突破、量價配合等買進訊號
3. 分析新聞事件中的潛在利多
4. 提供具體的買進理由與目標價位

你的論點必須有數據支持，不能空談。
你需要考慮：
- 營收/獲利成長趨勢
- 產業景氣循環位置
- 技術面突破訊號
- 資金流向
- 市場情緒

當被要求反駁時，你要強化自己的論點並指出對方論點的弱點。""",
        llm=llm,
        # tools=tools,  # 暫不啟用工具，避免格式問題
        allow_delegation=False,
        verbose=True
    )


def create_bear_agent() -> Any:
    """創建看空研究員 Agent"""
    if not HAS_CREWAI:
        return None
    
    llm = llm_for_crewai('bear_analyst')
    # 不傳遞工具，避免格式問題
    # tools = tools_for_category('research') + tools_for_category('analyst')
    
    return Agent(
        role='🐻 看空研究員 (Bear Analyst)',
        goal='找出所有支持賣出的利空因素，包括風險、利空消息、技術破位',
        backstory="""你是一位謹慎的風險管理專家，專精於識別投資風險。

你的職責：
1. 從財報惡化、產業衰退、競爭加劇中找出利空
2. 識別技術面破位、量價背離等賣出訊號
3. 分析新聞事件中的潛在利空
4. 提供具體的風險警告與停損價位

你的職責是保護資金安全，不能忽視任何風險。
你需要考慮：
- 財報惡化跡象
- 產業競爭加劇
- 技術面破位風險
- 資金流出
- 市場過度樂觀

當被要求反駁時，你要強化自己的風險警告並指出對方論點的漏洞。""",
        llm=llm,
        # tools=tools,  # 暫不啟用工具，避免格式問題
        allow_delegation=False,
        verbose=True
    )


def create_moderator_agent() -> Any:
    """創建辯論主持人 Agent"""
    if not HAS_CREWAI:
        return None
    
    llm = llm_for_crewai('moderator')
    
    return Agent(
        role='🎯 辯論主持人 (Debate Moderator)',
        goal='協調多空辯論，提取關鍵論點，確保辯論聚焦於核心爭議',
        backstory="""你是一位經驗豐富的交易主管，擅長主持多空辯論。

你的職責：
1. 引導雙方針對同一議題展開辯論
2. 識別雙方論點中的事實與推測
3. 控制辯論輪數 (通常 2-3 輪)
4. 避免辯論偏離主題或陷入循環
5. 產出辯論摘要，供決策者參考

當發現辯論陷入重複或偏離時，你要及時介入並引導回核心議題。""",
        llm=llm,
        allow_delegation=False,
        verbose=True
    )


def create_judge_agent() -> Any:
    """創建最終決策者 Agent"""
    if not HAS_CREWAI:
        return None
    
    llm = llm_for_crewai('judge')
    
    return Agent(
        role='🏆 最終決策者 (Decision Judge)',
        goal='綜合辯論結果，產出最終交易決策與信心度',
        backstory="""你是一位資深交易主管，負責最終決策。

你的任務：
1. 評估雙方論點的強度與證據質量
2. 考慮市場環境與風險因素
3. 產出最終決策 (BUY/SELL/HOLD) 與信心度
4. 提供決策理由與風險提示

決策時你需要：
- 比較雙方論點的證據強度
- 考慮當前市場環境
- 評估風險報酬比
- 給出具體的進出場建議""",
        llm=llm,
        allow_delegation=False,
        verbose=True
    )


# ============================================================================
# 辯論系統核心
# ============================================================================

class DebateSystem:
    """多空辯論系統"""
    
    MAX_DEBATE_ROUNDS = 3
    CONVERGENCE_THRESHOLD = 0.15  # 當雙方信心度差異小於 15% 時視為接近共識
    REPETITION_THRESHOLD = 0.7    # 論點重複率高於 70% 視為辯論崩潰
    
    def __init__(self):
        self.bull_agent = None
        self.bear_agent = None
        self.moderator = None
        self.judge = None
        self._initialized = False
        
    def _initialize_agents(self):
        """初始化辯論 Agent"""
        if self._initialized:
            return
            
        self.bull_agent = create_bull_agent()
        self.bear_agent = create_bear_agent()
        self.moderator = create_moderator_agent()
        self.judge = create_judge_agent()
        self._initialized = True
    
    def run_debate(self, ticker: str, research_data: dict) -> DebateResult:
        """運行完整辯論流程"""
        if not HAS_CREWAI:
            logger.warning("⚠️ CrewAI 未安裝，使用 Fallback 模式")
            return self._fallback_decision(ticker, research_data)
        
        self._initialize_agents()
        
        logger.info(f"🎭 [Debate] 開始 {ticker} 多空辯論...")
        
        debate_history = []
        
        # 階段 1：獨立分析
        logger.info("📊 [Debate] 階段 1: 獨立分析")
        bull_initial = self._get_initial_argument('bull', ticker, research_data)
        bear_initial = self._get_initial_argument('bear', ticker, research_data)
        
        debate_history.append(DebateRound(
            round_number=0,
            bull_argument=bull_initial,
            bear_argument=bear_initial,
            moderator_summary="初始分析完成",
            key_disagreements=self._identify_disagreements(bull_initial, bear_initial)
        ))
        
        # 階段 2：辯論回合 (最多 3 輪)
        current_bull = bull_initial
        current_bear = bear_initial
        
        for round_num in range(1, self.MAX_DEBATE_ROUNDS + 1):
            # 檢查是否崩潰
            is_collapsed, collapse_reason = self._detect_debate_collapse(debate_history)
            if is_collapsed:
                logger.info(f"⚠️ [Debate] 辯論提前結束：{collapse_reason}")
                break
            
            # 進行辯論
            logger.info(f"🔄 [Debate] 辯論回合 {round_num}/{self.MAX_DEBATE_ROUNDS}")
            
            bull_response = self._debate_round(
                side='bull',
                current_args=current_bear,
                ticker=ticker,
                research_data=research_data,
                previous_context=current_bull
            )
            
            bear_response = self._debate_round(
                side='bear',
                current_args=bull_response,
                ticker=ticker,
                research_data=research_data,
                previous_context=current_bear
            )
            
            # 主持人總結
            summary, disagreements, convergence = self._summarize_round(
                bull_response, bear_response, round_num
            )
            
            debate_history.append(DebateRound(
                round_number=round_num,
                bull_argument=bull_response,
                bear_argument=bear_response,
                moderator_summary=summary,
                key_disagreements=disagreements,
                convergence_score=convergence
            ))
            
            # 檢查是否已達成共識
            if convergence >= (1 - self.CONVERGENCE_THRESHOLD):
                logger.info(f"✅ [Debate] 已達成共識，提前結束辯論")
                break
            
            # 更新參考
            current_bull = bull_response
            current_bear = bear_response
        
        # 階段 3：最終決策
        logger.info("🏆 [Debate] 做出最終決策")
        final_decision = self._make_final_decision(ticker, debate_history)
        
        # 評估辯論質量
        quality = self._evaluate_debate_quality(debate_history)
        
        return DebateResult(
            ticker=ticker,
            final_decision=final_decision['side'],
            confidence=final_decision['confidence'],
            reasoning=final_decision['reasoning'],
            bull_key_points=current_bull.main_points[:5],
            bear_key_points=current_bear.main_points[:5],
            debate_history=debate_history,
            total_rounds=len(debate_history),
            debate_quality=quality
        )
    
    def _get_initial_argument(self, side: str, ticker: str, 
                             data: dict) -> DebateArgument:
        """獲取初始論點"""
        try:
            # 準備任務描述
            if side == 'bull':
                task_desc = f"""
                請對 {ticker} 進行看多分析。

                可用資料：
                - 股價數據：{data.get('price_data', 'N/A')}
                - 新聞事件：{data.get('news', 'N/A')[:200]}...
                - 技術指標：{data.get('technical', 'N/A')}
                - 籌碼數據：{data.get('chip', 'N/A')}

                請列出：
                1. 主要利多因素 (至少 3 點)
                2. 支持證據
                3. 潛在目標價位
                4. 信心度評估
                """
            else:
                task_desc = f"""
                請對 {ticker} 進行看空分析。

                可用資料：
                - 股價數據：{data.get('price_data', 'N/A')}
                - 新聞事件：{data.get('news', 'N/A')[:200]}...
                - 技術指標：{data.get('technical', 'N/A')}
                - 籌碼數據：{data.get('chip', 'N/A')}

                請列出：
                1. 主要利空因素 (至少 3 點)
                2. 風險警告
                3. 建議停損價位
                4. 信心度評估
                """
            
            # 使用對應 Agent 執行
            if side == 'bull':
                agent = self.bull_agent
            else:
                agent = self.bear_agent
            
            task = Task(
                description=task_desc,
                expected_output='結構化的分析報告',
                agent=agent
            )
            
            crew = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=False
            )
            
            result = crew.kickoff()
            text = str(result)
            
            # 解析結果
            return self._parse_argument_text(side, text)
            
        except Exception as e:
            logger.error(f"[Debate] {side} 初始分析失敗：{e}")
            return DebateArgument(
                side=side,
                main_points=[f"分析失敗：{e}"],
                confidence=0.5
            )
    
    def _debate_round(self, side: str, current_args: DebateArgument,
                     ticker: str, research_data: dict,
                     previous_context: Optional[DebateArgument] = None) -> DebateArgument:
        """單輪辯論"""
        try:
            opponent_side = 'bear' if side == 'bull' else 'bull'
            
            task_desc = f"""
            請對 {ticker} 進行{side}方辯論回應。

            對方 ({opponent_side}方) 的主要論點：
            {self._format_argument(current_args)}

            你的任務：
            1. 回應對方的論點 (指出弱點或反駁)
            2. 強化自己的立場
            3. 提出新的論據或證據
            4. 評估對方的論點強度

            請保持專業、客觀，避免情緒性言詞。
            """
            
            if previous_context:
                task_desc += f"\n\n你之前的論點：\n{self._format_argument(previous_context)}"
            
            if side == 'bull':
                agent = self.bull_agent
            else:
                agent = self.bear_agent
            
            task = Task(
                description=task_desc,
                expected_output='辯論回應',
                agent=agent
            )
            
            crew = Crew(
                agents=[agent],
                tasks=[task],
                process=Process.sequential,
                verbose=False
            )
            
            result = crew.kickoff()
            text = str(result)
            
            return self._parse_argument_text(side, text)
            
        except Exception as e:
            logger.error(f"[Debate] {side} 辯論回應失敗：{e}")
            return DebateArgument(
                side=side,
                main_points=[f"回應失敗：{e}"],
                confidence=0.5
            )
    
    def _summarize_round(self, bull_arg: DebateArgument,
                        bear_arg: DebateArgument,
                        round_num: int) -> tuple:
        """主持人總結本輪辯論"""
        try:
            task_desc = f"""
            請總結第 {round_num} 輪多空辯論。

            看方論點：
            {self._format_argument(bull_arg)}

            空方論點：
            {self._format_argument(bear_arg)}

            請提供：
            1. 本輪核心爭議點
            2. 雙方論點強度評估
            3. 是否有達成共識的跡象
            4. 建議是否需要繼續辯論
            """
            
            task = Task(
                description=task_desc,
                expected_output='辯論總結',
                agent=self.moderator
            )
            
            crew = Crew(
                agents=[self.moderator],
                tasks=[task],
                process=Process.sequential,
                verbose=False
            )
            
            result = crew.kickoff()
            summary = str(result)
            
            # 提取關鍵分歧點
            disagreements = self._extract_disagreements(bull_arg, bear_arg)
            
            # 計算共識度
            convergence = self._calculate_convergence(bull_arg, bear_arg)
            
            return summary, disagreements, convergence
            
        except Exception as e:
            logger.error(f"[Debate] 主持人總結失敗：{e}")
            return f"總結失敗：{e}", [], 0.0
    
    def _make_final_decision(self, ticker: str,
                            debate_history: List[DebateRound]) -> dict:
        """做出最終決策"""
        try:
            # 提取最終論點
            final_round = debate_history[-1]
            bull_final = final_round.bull_argument
            bear_final = final_round.bear_argument
            
            task_desc = f"""
            請根據完整的辯論過程，對 {ticker} 做出最終決策。

            辯論輪數：{len(debate_history)} 輪

            看方最終論點：
            {self._format_argument(bull_final)}

            空方最終論點：
            {self._format_argument(bear_final)}

            辯論歷史摘要：
            {self._format_debate_history(debate_history)}

            請提供：
            1. 最終決策 (BUY/SELL/HOLD)
            2. 信心度 (0-1)
            3. 決策理由
            4. 風險提示
            """
            
            task = Task(
                description=task_desc,
                expected_output='最終決策報告',
                agent=self.judge
            )
            
            crew = Crew(
                agents=[self.judge],
                tasks=[task],
                process=Process.sequential,
                verbose=False
            )
            
            result = crew.kickoff()
            text = str(result)
            
            # 解析決策
            decision = self._parse_decision_text(text)
            
            return decision
            
        except Exception as e:
            logger.error(f"[Debate] 最終決策失敗：{e}")
            return {
                'side': 'HOLD',
                'confidence': 0.5,
                'reasoning': f'決策失敗：{e}'
            }
    
    def _detect_debate_collapse(self, history: List[DebateRound]) -> tuple:
        """檢測辯論是否崩潰"""
        if len(history) < 2:
            return False, None
        
        # 檢查論點重複率
        if len(history) >= 3:
            last_two_bull = [history[-2].bull_argument, history[-1].bull_argument]
            last_two_bear = [history[-2].bear_argument, history[-1].bear_argument]
            
            bull_repetition = self._calculate_similarity(
                self._format_argument(last_two_bull[0]),
                self._format_argument(last_two_bull[1])
            )
            
            bear_repetition = self._calculate_similarity(
                self._format_argument(last_two_bear[0]),
                self._format_argument(last_two_bear[1])
            )
            
            if bull_repetition > self.REPETITION_THRESHOLD and \
               bear_repetition > self.REPETITION_THRESHOLD:
                return True, "辯論陷入循環，論點高度重複"
        
        return False, None
    
    def _evaluate_debate_quality(self, history: List[DebateRound]) -> str:
        """評估辯論質量"""
        if not history:
            return "無辯論資料"
        
        total_rounds = len(history)
        
        # 評估維度
        has_initial_analysis = all(
            round.bull_argument and round.bear_argument 
            for round in history
        )
        
        has_convergence = any(
            round.convergence_score > 0.5 
            for round in history
        )
        
        has_clear_disagreements = any(
            len(round.key_disagreements) > 0 
            for round in history
        )
        
        # 綜合評分
        score = 0
        if has_initial_analysis:
            score += 2
        if has_convergence:
            score += 1
        if has_clear_disagreements:
            score += 1
        
        if score >= 3:
            return "高質量辯論"
        elif score >= 2:
            return "中等質量辯論"
        else:
            return "低質量辯論"
    
    # ========================================================================
    # 輔助函式
    # ========================================================================
    
    def _parse_argument_text(self, side: str, text: str) -> DebateArgument:
        """解析論點文字為結構化資料"""
        try:
            # 簡單的關鍵字提取
            main_points = []
            evidence = []
            
            lines = text.split('\n')
            for line in lines[:20]:  # 只處理前 20 行
                line = line.strip()
                if line and not line.startswith('#'):
                    if any(kw in line for kw in ['理由', '原因', '因素', '點']):
                        main_points.append(line[:100])
                    elif any(kw in line for kw in ['數據', '證據', '顯示', '達到']):
                        evidence.append(line[:100])
            
            # 估算信心度
            confidence = 0.6
            if any(kw in text.lower() for kw in ['強烈', '確定', '明確']):
                confidence = 0.8
            elif any(kw in text.lower() for kw in ['可能', '或許', '謹慎']):
                confidence = 0.5
            
            return DebateArgument(
                side=side,
                main_points=main_points[:5],
                evidence=evidence[:5],
                confidence=confidence,
                reasoning=text[:500]
            )
            
        except Exception:
            return DebateArgument(
                side=side,
                main_points=[text[:200]],
                confidence=0.5
            )
    
    def _parse_decision_text(self, text: str) -> dict:
        """解析決策文字"""
        try:
            text_lower = text.lower()
            
            if 'buy' in text_lower or '買進' in text:
                side = 'BUY'
            elif 'sell' in text_lower or '賣出' in text:
                side = 'SELL'
            else:
                side = 'HOLD'
            
            # 提取信心度
            confidence = 0.6
            import re
            match = re.search(r'信心度 [：:]\s*(\d+)%', text)
            if match:
                confidence = int(match.group(1)) / 100.0
            
            return {
                'side': side,
                'confidence': confidence,
                'reasoning': text[:500]
            }
            
        except Exception:
            return {
                'side': 'HOLD',
                'confidence': 0.5,
                'reasoning': text[:500]
            }
    
    def _format_argument(self, arg: DebateArgument) -> str:
        """格式化論點為文字"""
        if not arg:
            return "無論點"
        
        lines = [f"【{arg.side}方論點】"]
        if arg.main_points:
            lines.append("主要論點：")
            for i, point in enumerate(arg.main_points[:5], 1):
                lines.append(f"  {i}. {point[:80]}")
        if arg.evidence:
            lines.append("支持證據：")
            for i, ev in enumerate(arg.evidence[:3], 1):
                lines.append(f"  {i}. {ev[:60]}")
        
        return '\n'.join(lines)
    
    def _format_debate_history(self, history: List[DebateRound]) -> str:
        """格式化辯論歷史"""
        lines = []
        for round in history:
            lines.append(f"\n=== 第 {round.round_number} 輪 ===")
            lines.append(f"主持人總結：{round.moderator_summary[:200]}")
            if round.key_disagreements:
                lines.append(f"關鍵分歧：{', '.join(round.key_disagreements[:3])}")
        return '\n'.join(lines)
    
    def _identify_disagreements(self, bull: DebateArgument, 
                               bear: DebateArgument) -> List[str]:
        """識別雙方分歧點"""
        disagreements = []
        
        # 簡單比較主要論點
        for bull_point in bull.main_points[:3]:
            for bear_point in bear.main_points[:3]:
                if self._are_conflicting(bull_point, bear_point):
                    disagreements.append(f"利多 vs 利空：{bull_point[:40]} vs {bear_point[:40]}")
        
        return disagreements[:5]
    
    def _extract_disagreements(self, bull: DebateArgument,
                              bear: DebateArgument) -> List[str]:
        """提取關鍵分歧"""
        return self._identify_disagreements(bull, bear)
    
    def _calculate_convergence(self, bull: DebateArgument,
                              bear: DebateArgument) -> float:
        """計算共識度"""
        # 基於信心度差異計算
        confidence_diff = abs(bull.confidence - bear.confidence)
        return 1.0 - confidence_diff
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """計算文字相似度 (簡化版)"""
        if not text1 or not text2:
            return 0.0
        
        # 簡單的詞彙重疊率
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0
    
    def _are_conflicting(self, point1: str, point2: str) -> bool:
        """判斷兩個論點是否衝突"""
        bull_keywords = {'買進', '看多', '突破', '利多', '成長', '上漲'}
        bear_keywords = {'賣出', '看空', '跌破', '利空', '衰退', '下跌'}
        
        has_bull = any(kw in point1 for kw in bull_keywords)
        has_bear = any(kw in point2 for kw in bear_keywords)
        
        return has_bull and has_bear
    
    def _fallback_decision(self, ticker: str, data: dict) -> DebateResult:
        """Fallback 機制"""
        from agents.decision_maker import synthesize_decision
        
        signal = synthesize_decision(ticker=ticker)
        
        return DebateResult(
            ticker=ticker,
            final_decision=signal.get('side', 'HOLD'),
            confidence=signal.get('confidence', 0.5),
            reasoning=signal.get('reason', 'Fallback mode'),
            total_rounds=0,
            debate_quality='未啟用辯論系統'
        )


# ============================================================================
# 便捷函式
# ============================================================================

def run_debate(ticker: str, research_data: dict) -> DebateResult:
    """便捷函式：運行多空辯論"""
    system = DebateSystem()
    return system.run_debate(ticker, research_data)


def get_debate_result(ticker: str, news_output: str = "",
                     price_output: str = "", chip_info: dict = None) -> DebateResult:
    """整合現有資料運行辯論"""
    research_data = {
        'news': news_output,
        'technical': price_output,
        'chip': chip_info or {}
    }
    
    return run_debate(ticker, research_data)
