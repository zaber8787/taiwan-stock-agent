# File: tests/test_notifier.py

import os
import unittest
from unittest.mock import patch, MagicMock
from app.notifier import (
    DiscordNotifier,
    get_discord_notifier,
    COLOR_BUY,
    COLOR_SELL_PROFIT,
    COLOR_SELL_LOSS,
    COLOR_NEWS,
    COLOR_RISK_ALERT
)


class TestDiscordNotifier(unittest.TestCase):

    def setUp(self):
        # Reset singleton and test environment
        DiscordNotifier._instance = None
        os.environ['DISCORD_WEBHOOK_URL'] = 'https://discord.com/api/webhooks/123456/abcdef'
        os.environ['DISCORD_NOTIFICATIONS_ENABLED'] = 'true'
        os.environ['DISCORD_NOTIFY_ON_TRADE'] = 'true'
        os.environ['DISCORD_NOTIFY_ON_NEWS'] = 'true'
        os.environ['DISCORD_NOTIFY_ON_RISK'] = 'true'

    def test_singleton_and_config(self):
        n1 = get_discord_notifier()
        n2 = get_discord_notifier()
        self.assertIs(n1, n2)
        self.assertTrue(n1.is_configured())
        self.assertTrue(n1.enabled)

        status = n1.get_status()
        self.assertTrue(status['configured'])
        self.assertTrue(status['enabled'])
        self.assertTrue(status['notify_on_trade'])

    @patch.object(DiscordNotifier, '_send_payload_sync', return_value=True)
    def test_send_buy_trade_notification(self, mock_send):
        notifier = get_discord_notifier()
        trade_record = {
            'trade_id': 't001',
            'ticker': '2330',
            'side': 'BUY',
            'shares': 1000,
            'price': 1050.0,
            'total_cost': 1050299.25,
            'commission': 299.25,
            'confidence': 0.85,
            'reason': 'AI 突破買進訊號'
        }
        res = notifier.send_trade_notification(trade_record, current_cash=500000.0, async_mode=False)
        self.assertTrue(res)
        mock_send.assert_called_once()
        payload = mock_send.call_args[0][0]
        self.assertEqual(len(payload['embeds']), 1)
        embed = payload['embeds'][0]
        self.assertIn("買進 2330", embed['title'])
        self.assertEqual(embed['color'], COLOR_BUY)

    @patch.object(DiscordNotifier, '_send_payload_sync', return_value=True)
    def test_send_sell_trade_notification(self, mock_send):
        notifier = get_discord_notifier()
        trade_record = {
            'trade_id': 't002',
            'ticker': '2454',
            'side': 'SELL',
            'shares': 1000,
            'price': 1400.0,
            'net_revenue': 1395000.0,
            'commission': 399.0,
            'stamp_tax': 4200.0,
            'pnl': 50000.0,
            'roi_pct': 3.72,
            'reason': '移動停利觸發 (+10% 回檔2%)',
            'confidence': 0.90
        }
        res = notifier.send_trade_notification(trade_record, current_cash=1500000.0, async_mode=False)
        self.assertTrue(res)
        mock_send.assert_called_once()
        payload = mock_send.call_args[0][0]
        embed = payload['embeds'][0]
        self.assertIn("賣出 2454", embed['title'])
        self.assertEqual(embed['color'], COLOR_SELL_PROFIT)

    @patch.object(DiscordNotifier, '_send_payload_sync', return_value=True)
    def test_send_news_notification(self, mock_send):
        notifier = get_discord_notifier()
        news_event = {
            'ticker': '2330',
            'news_title': '台積電2奈米量產進度超前',
            'news_summary': '供應鏈消息指稱2奈米製程良率大幅提升...',
            'side': 'BUY',
            'confidence': 0.88,
            'industry': '半導體',
            'reason': '先進製程利多',
            'trade_status': 'EXECUTED'
        }
        res = notifier.send_news_notification(news_event, async_mode=False)
        self.assertTrue(res)
        mock_send.assert_called_once()
        embed = mock_send.call_args[0][0]['embeds'][0]
        self.assertIn("重大新聞事件監聽", embed['title'])
        self.assertIn("台積電2奈米量產進度超前", embed['title'])

    @patch.object(DiscordNotifier, '_send_payload_sync', return_value=True)
    def test_send_risk_alert(self, mock_send):
        notifier = get_discord_notifier()
        res = notifier.send_risk_alert('2330', '單檔持倉上限攔截', '已達單檔本金20%上限', async_mode=False)
        self.assertTrue(res)
        mock_send.assert_called_once()
        embed = mock_send.call_args[0][0]['embeds'][0]
        self.assertIn("風控引擎攔截/告警", embed['title'])
        self.assertEqual(embed['color'], COLOR_RISK_ALERT)

    def test_unconfigured_graceful_fallback(self):
        os.environ['DISCORD_WEBHOOK_URL'] = ''
        DiscordNotifier._instance = None
        notifier = get_discord_notifier()
        self.assertFalse(notifier.is_configured())
        # Should return False gracefully without raising exceptions
        res = notifier.send_system_notification('測試', '內文', async_mode=False)
        self.assertFalse(res)


if __name__ == '__main__':
    unittest.main()
