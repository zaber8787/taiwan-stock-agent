# File: app/notifier.py

'''
Discord Webhook Notifier for Taiwan Stock Agent.
Provides formatted Rich Embed notifications for trades, news events,
risk management triggers (stop-loss, trailing take-profit), and system health.
'''
from __future__ import annotations
import os
import json
import logging
import asyncio
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Colors for Discord Embeds (Hex integers)
COLOR_BUY = 0x2ECC71        # Emerald Green
COLOR_SELL_PROFIT = 0x3498DB # Blue / Green-Cyan
COLOR_SELL_LOSS = 0xE74C3C   # Red
COLOR_NEWS = 0xF1C40F        # Yellow / Gold
COLOR_RISK_ALERT = 0xE67E22  # Orange
COLOR_SYSTEM = 0x9B59B6      # Purple
COLOR_INFO = 0x95A5A6        # Gray


class DiscordNotifier:
    '''Thread-safe Discord Webhook Notifier with rich embed support.'''

    _instance: Optional[DiscordNotifier] = None
    _lock = threading.Lock()

    def __new__(cls) -> DiscordNotifier:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DiscordNotifier, cls).__new__(cls)
                cls._instance._init_notifier()
            return cls._instance

    def _init_notifier(self) -> None:
        self.webhook_url = os.getenv('DISCORD_WEBHOOK_URL', '').strip()
        self.enabled = os.getenv('DISCORD_NOTIFICATIONS_ENABLED', 'true').lower() == 'true'
        self.notify_on_trade = os.getenv('DISCORD_NOTIFY_ON_TRADE', 'true').lower() == 'true'
        self.notify_on_news = os.getenv('DISCORD_NOTIFY_ON_NEWS', 'true').lower() == 'true'
        self.notify_on_risk = os.getenv('DISCORD_NOTIFY_ON_RISK', 'true').lower() == 'true'

    def refresh_config(self) -> None:
        '''Reload environment variables.'''
        self.webhook_url = os.getenv('DISCORD_WEBHOOK_URL', '').strip()
        self.enabled = os.getenv('DISCORD_NOTIFICATIONS_ENABLED', 'true').lower() == 'true'
        self.notify_on_trade = os.getenv('DISCORD_NOTIFY_ON_TRADE', 'true').lower() == 'true'
        self.notify_on_news = os.getenv('DISCORD_NOTIFY_ON_NEWS', 'true').lower() == 'true'
        self.notify_on_risk = os.getenv('DISCORD_NOTIFY_ON_RISK', 'true').lower() == 'true'

    def is_configured(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith('http'))

    def get_status(self) -> Dict[str, Any]:
        return {
            'enabled': self.enabled,
            'configured': self.is_configured(),
            'webhook_url_masked': (self.webhook_url[:28] + '...' + self.webhook_url[-6:]) if len(self.webhook_url) > 35 else ('Set' if self.webhook_url else 'None'),
            'notify_on_trade': self.notify_on_trade,
            'notify_on_news': self.notify_on_news,
            'notify_on_risk': self.notify_on_risk
        }

    def _send_payload_sync(self, payload: Dict[str, Any]) -> bool:
        '''Synchronous HTTP POST to Discord Webhook.'''
        if not self.enabled or not self.is_configured():
            logger.debug("Discord Webhook 未配置或已停用，略過發送。")
            return False

        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.webhook_url,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'TaiwanStockAgent/1.0'
                }
            )
            with urllib.request.urlopen(req, timeout=5.0) as response:
                if response.status in (200, 204):
                    logger.info("📡 [Discord] Webhook 推播發送成功。")
                    return True
                else:
                    logger.warning(f"⚠️ [Discord] Webhook 回應狀態碼: {response.status}")
                    return False
        except urllib.error.HTTPError as e:
            logger.warning(f"⚠️ [Discord] Webhook HTTP 錯誤 ({e.code}): {e.read().decode('utf-8', errors='ignore')}")
            return False
        except Exception as e:
            logger.warning(f"⚠️ [Discord] Webhook 發送異常: {e}")
            return False

    def send_raw(self, payload: Dict[str, Any], async_mode: bool = True) -> bool:
        '''Send arbitrary Discord payload.'''
        if async_mode:
            try:
                loop = asyncio.get_running_loop()
                loop.run_in_executor(None, self._send_payload_sync, payload)
                return True
            except RuntimeError:
                # No running event loop in current thread
                threading.Thread(target=self._send_payload_sync, args=(payload,), daemon=True).start()
                return True
        else:
            return self._send_payload_sync(payload)

    def send_embed(self, embed: Dict[str, Any], content: str = "", async_mode: bool = True) -> bool:
        '''Send single rich embed to Discord.'''
        payload = {
            "username": "台股 AI 交易助手",
            "avatar_url": "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f4c8.png",
            "content": content,
            "embeds": [embed]
        }
        return self.send_raw(payload, async_mode=async_mode)

    # -------------------------------------------------------------
    # 專屬事件推播產生器
    # -------------------------------------------------------------

    def send_trade_notification(self, trade_info: Dict[str, Any], current_cash: float, async_mode: bool = True) -> bool:
        '''
        Send real-time trade execution notification.
        Handles BUY / SELL / STOP_LOSS / TRAILING_STOP executions.
        '''
        if not self.notify_on_trade:
            return False

        ticker = trade_info.get('ticker', '')
        action = trade_info.get('action', trade_info.get('side', 'TRADE')).upper()
        shares = trade_info.get('shares', 0)
        lots = shares // 1000
        odd_shares = shares % 1000
        share_str = f"{lots} 張" if odd_shares == 0 else f"{lots} 張 {odd_shares} 股"
        price = trade_info.get('price', 0.0)
        total_cost = trade_info.get('total_cost', 0.0)
        net_revenue = trade_info.get('net_revenue', 0.0)
        pnl = trade_info.get('pnl', 0.0)
        roi_pct = trade_info.get('roi_pct', 0.0)
        reason = trade_info.get('reason', 'AI 訊號研判觸發')
        confidence = trade_info.get('confidence', 0.0)
        tax = trade_info.get('stamp_tax', 0.0)
        commission = trade_info.get('commission', 0.0)

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if action == 'BUY':
            color = COLOR_BUY
            title = f"🟢 【模擬下單成交通知】買進 {ticker}"
            description = f"**標的代碼**：`{ticker}.TW`\n**動作**：買進 (BUY)\n**成交張數**：`{share_str}` ({shares:,} 股)"
            fields = [
                {"name": "成交單價", "value": f"**${price:,.2f}** NTD", "inline": True},
                {"name": "總投入金額", "value": f"${total_cost:,.2f} NTD", "inline": True},
                {"name": "手續費", "value": f"${commission:,.2f} NTD", "inline": True},
                {"name": "AI 信心度", "value": f"{confidence * 100:.1f}%", "inline": True},
                {"name": "剩餘可用現金", "value": f"${current_cash:,.2f} NTD", "inline": True},
                {"name": "觸發理由", "value": f"```{reason}```", "inline": False}
            ]
        else: # SELL
            color = COLOR_SELL_PROFIT if pnl >= 0 else COLOR_SELL_LOSS
            pnl_symbol = "📈 獲利" if pnl >= 0 else "📉 虧損"
            title = f"🔴 【模擬平倉成交通知】賣出 {ticker} ({pnl_symbol} ${pnl:,.2f})"
            description = f"**標的代碼**：`{ticker}.TW`\n**動作**：賣出平倉 (SELL)\n**成交張數**：`{share_str}` ({shares:,} 股)"
            fields = [
                {"name": "賣出單價", "value": f"**${price:,.2f}** NTD", "inline": True},
                {"name": "淨回收金額", "value": f"${net_revenue:,.2f} NTD", "inline": True},
                {"name": "實現損益 (PnL)", "value": f"**${pnl:+,.2f} NTD** ({roi_pct:+.2f}%)", "inline": True},
                {"name": "證交稅與手續費", "value": f"稅: ${tax:,.1f} / 手續: ${commission:,.1f}", "inline": True},
                {"name": "剩餘可用現金", "value": f"${current_cash:,.2f} NTD", "inline": True},
                {"name": "出場理由", "value": f"```{reason}```", "inline": False}
            ]

        embed = {
            "title": title,
            "description": description,
            "color": color,
            "fields": fields,
            "footer": {
                "text": f"Taiwan Stock Agent • 撮合時間: {now_str}"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        return self.send_embed(embed, async_mode=async_mode)

    def send_news_notification(self, news_event: Dict[str, Any], async_mode: bool = True) -> bool:
        '''Send real-time news & AI event analysis notification.'''
        if not self.notify_on_news:
            return False

        ticker = news_event.get('ticker', '')
        title = news_event.get('news_title', '財經即時新聞')
        summary = news_event.get('news_summary', '')
        side = news_event.get('side', 'HOLD')
        confidence = news_event.get('confidence', 0.0)
        industry = news_event.get('industry', '未知產業')
        reason = news_event.get('reason', '')
        trade_status = news_event.get('trade_status', 'SKIPPED')

        category_name = news_event.get('event_category_name', '📰 一般產經')
        horizon = news_event.get('impact_horizon', 'SHORT_TERM')
        urgency = news_event.get('urgency', 'MEDIUM')
        
        horizon_map = {'INTRADAY': '⚡ 當日當沖', 'SHORT_TERM': '📅 短線 1-3 日', 'LONG_TERM': '📊 中長線結構'}
        horizon_text = horizon_map.get(horizon, horizon)

        side_text = "🟢 看多 (BUY)" if side == 'BUY' else ("🔴 看空 (SELL)" if side == 'SELL' else "⚪ 觀望 (HOLD)")
        color = COLOR_BUY if side == 'BUY' else (COLOR_SELL_LOSS if side == 'SELL' else COLOR_NEWS)

        fields = [
            {"name": "關聯台股標的", "value": f"`{ticker}.TW` ({industry})", "inline": True},
            {"name": "事件分類", "value": f"**{category_name}**", "inline": True},
            {"name": "預期影響維度", "value": f"`{horizon_text}`", "inline": True},
            {"name": "AI 研判方向", "value": f"**{side_text}**", "inline": True},
            {"name": "AI 信心指數", "value": f"**{confidence * 100:.1f}%**", "inline": True},
            {"name": "自動交易狀態", "value": f"`{trade_status}`", "inline": True}
        ]

        if summary:
            fields.append({"name": "新聞內容摘要", "value": summary[:300] + ("..." if len(summary) > 300 else ""), "inline": False})
        if reason:
            fields.append({"name": "AI 研判依據", "value": f"```{reason[:300]}```", "inline": False})

        embed = {
            "title": f"📰 【{category_name}】{title[:60]}",
            "description": f"系統背景即時偵測到與 `{ticker}` 高度相關之重大財經事件（緊急度: `{urgency}`）：",
            "color": color,
            "fields": fields,
            "footer": {
                "text": f"Taiwan Stock Agent • 事件驅動引擎 • {category_name}"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        return self.send_embed(embed, async_mode=async_mode)

    def send_risk_alert(self, ticker: str, alert_type: str, details: str, async_mode: bool = True) -> bool:
        '''Send risk management rejection / stop-loss / warning alert.'''
        if not self.notify_on_risk:
            return False

        embed = {
            "title": f"🛡️ 【風控引擎攔截/告警】{ticker} - {alert_type}",
            "description": f"系統風控機制介入，已執行保護動作：\n\n```{details}```",
            "color": COLOR_RISK_ALERT,
            "fields": [
                {"name": "標的代碼", "value": f"`{ticker}`", "inline": True},
                {"name": "告警類別", "value": alert_type, "inline": True}
            ],
            "footer": {
                "text": "Taiwan Stock Agent • 動態風控模組"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        return self.send_embed(embed, async_mode=async_mode)

    def send_system_notification(self, title: str, message: str, color: int = COLOR_SYSTEM, async_mode: bool = True) -> bool:
        '''Send system-level notification (e.g. startup, test, summary).'''
        embed = {
            "title": title,
            "description": message,
            "color": color,
            "footer": {
                "text": "Taiwan Stock Agent • 系統狀態通知"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        return self.send_embed(embed, async_mode=async_mode)


def get_discord_notifier() -> DiscordNotifier:
    '''Get the global DiscordNotifier singleton instance.'''
    return DiscordNotifier()
