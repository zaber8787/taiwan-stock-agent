// Web GUI JavaScript App Logic
document.addEventListener('DOMContentLoaded', () => {
  const statEquity = document.getElementById('stat-equity');
  const statInitial = document.getElementById('stat-initial');
  const statCash = document.getElementById('stat-cash');
  const statMaxAlloc = document.getElementById('stat-max-alloc');
  const statHoldingsVal = document.getElementById('stat-holdings-val');
  const statHoldingsCount = document.getElementById('stat-holdings-count');
  const statRoi = document.getElementById('stat-roi');
  const statUnrealized = document.getElementById('stat-unrealized');
  const statRealized = document.getElementById('stat-realized');
  const statDbCount = document.getElementById('stat-db-count');

  const allocCash = document.getElementById('alloc-cash');
  const allocLimitPct = document.getElementById('alloc-limit-pct');
  const allocConfidence = document.getElementById('alloc-confidence');
  const allocBudget = document.getElementById('alloc-budget');
  const allocShares = document.getElementById('alloc-shares');

  const inputTicker = document.getElementById('input-ticker');
  const btnAnalyze = document.getElementById('btn-analyze');
  const btnReset = document.getElementById('btn-reset');
  const logContainer = document.getElementById('log-container');
  const logMessage = document.getElementById('log-message');

  const feedContainer = document.getElementById('feed-container');
  const holdingsTbody = document.getElementById('holdings-tbody');
  const tradesTbody = document.getElementById('trades-tbody');

  const reportModal = document.getElementById('report-modal');
  const modalTitle = document.getElementById('modal-title');
  const modalBody = document.getElementById('modal-body');
  const modalClose = document.getElementById('modal-close');

  let currentTradeLogs = [];

  function formatMoney(num) {
    return '$' + Number(num || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  // Load Listener & DB Status
  async function loadListenerStatus() {
    try {
      const res = await fetch('/api/listener/status');
      if (!res.ok) return;
      const data = await res.json();
      if (statDbCount) statDbCount.textContent = data.companies_in_db || 0;
    } catch (err) {
      console.error("Failed to load listener status:", err);
    }
  }

  // Load Live News Feed
  async function loadNewsFeed() {
    try {
      const res = await fetch('/api/news-feed');
      if (!res.ok) return;
      const data = await res.json();
      renderNewsFeed(data.events || []);
    } catch (err) {
      console.error("Failed to load news feed:", err);
    }
  }

  function renderNewsFeed(events) {
    if (!events || events.length === 0) {
      feedContainer.innerHTML = `<div class="empty-feed">📡 背景新聞監聽運行中...（監聽頻率: 每 3 分鐘，偵測到科技股/ETF 新聞時自動觸發 AI 下單）</div>`;
      return;
    }

    feedContainer.innerHTML = events.map(ev => {
      const isBuy = ev.side === 'BUY';
      const sideBadge = `<span class="${isBuy ? 'badge-buy' : 'badge-sell'}">${ev.side} (${(ev.confidence * 100).toFixed(0)}%)</span>`;
      const timeStr = ev.timestamp ? ev.timestamp.replace('T', ' ').substring(11, 19) : '--';
      return `
        <div class="feed-item">
          <div class="feed-title">
            <span style="color:var(--primary-accent); margin-right:0.5rem;">[${ev.ticker}]</span>
            ${ev.news_title}
          </div>
          <div class="feed-meta">
            <span style="font-size:0.75rem; color:var(--text-muted);">${timeStr}</span>
            ${sideBadge}
            <span style="font-size:0.75rem; color:var(--text-muted);">[${ev.trade_status}]</span>
          </div>
        </div>
      `;
    }).join('');
  }

  // Load Account Overview
  async function loadAccountData() {
    try {
      const res = await fetch('/api/account');
      if (!res.ok) return;
      const data = await res.json();
      
      statEquity.textContent = formatMoney(data.total_equity);
      statInitial.textContent = formatMoney(data.initial_capital);
      statCash.textContent = formatMoney(data.cash);
      statHoldingsVal.textContent = formatMoney(data.holdings_value);
      statHoldingsCount.textContent = data.holdings.length;
      
      const roi = data.total_roi_pct || 0;
      statRoi.textContent = (roi >= 0 ? '+' : '') + roi.toFixed(2) + '%';
      statRoi.className = 'stat-value ' + (roi > 0 ? 'profit' : roi < 0 ? 'loss' : 'neutral');

      statUnrealized.textContent = formatMoney(data.unrealized_pnl);
      statRealized.textContent = formatMoney(data.realized_pnl);

      allocCash.textContent = formatMoney(data.cash);

      renderHoldings(data.holdings);
    } catch (err) {
      console.error("Failed to load account data:", err);
    }
  }

  // Load Trade Logs
  async function loadTradeLogs() {
    try {
      const res = await fetch('/api/trades');
      if (!res.ok) return;
      const data = await res.json();
      currentTradeLogs = data.trades || [];
      renderTrades(currentTradeLogs);
    } catch (err) {
      console.error("Failed to load trade logs:", err);
    }
  }

  function renderHoldings(holdings) {
    if (!holdings || holdings.length === 0) {
      holdingsTbody.innerHTML = `<tr><td colspan="7" class="empty-msg">目前尚無股票持倉。</td></tr>`;
      return;
    }

    holdingsTbody.innerHTML = holdings.map(h => {
      const pnl = h.unrealized_pnl || 0;
      const pnlClass = pnl > 0 ? 'profit' : pnl < 0 ? 'loss' : 'neutral';
      const pnlPct = h.unrealized_pnl_pct || 0;
      return `
        <tr>
          <td><strong>${h.ticker}</strong></td>
          <td>${h.shares.toLocaleString()} 股 (${h.lots} 張)</td>
          <td>$${h.cost_price.toFixed(2)}</td>
          <td>$${h.current_price.toFixed(2)}</td>
          <td>${formatMoney(h.market_value)}</td>
          <td class="${pnlClass}">${pnl >= 0 ? '+' : ''}${formatMoney(pnl)}</td>
          <td class="${pnlClass}">${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%</td>
        </tr>
      `;
    }).join('');
  }

  function renderTrades(trades) {
    if (!trades || trades.length === 0) {
      tradesTbody.innerHTML = `<tr><td colspan="10" class="empty-msg">尚無模擬交易紀錄。</td></tr>`;
      return;
    }

    tradesTbody.innerHTML = trades.map((t, idx) => {
      const isBuy = t.side === 'BUY';
      const sideBadge = `<span class="${isBuy ? 'badge-buy' : 'badge-sell'}">${t.side}</span>`;
      const timeStr = t.time ? t.time.replace('T', ' ').substring(0, 19) : '--';
      const costOrRev = isBuy ? t.total_cost : t.net_revenue;
      const taxFee = (t.commission || 0) + (t.stamp_tax || 0);

      return `
        <tr>
          <td style="font-size:0.8rem; color:var(--text-muted);">${timeStr}</td>
          <td><code>${t.trade_id}</code></td>
          <td><strong>${t.ticker}</strong></td>
          <td>${sideBadge}</td>
          <td>$${t.price.toFixed(2)}</td>
          <td>${t.shares.toLocaleString()} 股</td>
          <td>${formatMoney(costOrRev)}</td>
          <td>$${taxFee.toFixed(2)}</td>
          <td style="max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${t.reason}">${t.reason}</td>
          <td><button class="btn btn-secondary btn-action-small" onclick="viewTradeReport(${idx})">檢視報告</button></td>
        </tr>
      `;
    }).join('');
  }

  btnAnalyze.addEventListener('click', async () => {
    const stockCode = inputTicker.value.trim();
    if (!stockCode) {
      alert("請輸入股票代碼！");
      return;
    }

    btnAnalyze.disabled = true;
    logContainer.classList.remove('hidden');
    logMessage.textContent = `🤖 4 大 AI Agent 正在深度分析 ${stockCode}...`;

    try {
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ stock_code: stockCode })
      });

      if (!res.ok) {
        throw new Error("AI 分析服務異常");
      }

      const data = await res.json();
      
      if (data.allocation_preview) {
        const ap = data.allocation_preview;
        allocConfidence.textContent = (ap.confidence * 100).toFixed(0) + '%';
        allocBudget.textContent = formatMoney(ap.budget);
        allocShares.textContent = `${ap.suggested_shares.toLocaleString()} 股 (${ap.suggested_lots} 張)`;
      }

      await loadAccountData();
      await loadTradeLogs();

      logMessage.textContent = `✅ ${stockCode} 分析與模擬交易完成！結果: ${data.trade_execution.status} (${data.trade_execution.action || data.signal.side})`;
      
      openModal(`📊 AI 交易分析報告 - ${stockCode}`, data.report_markdown);

    } catch (err) {
      logMessage.textContent = `❌ 錯誤: ${err.message}`;
    } finally {
      btnAnalyze.disabled = false;
    }
  });

  btnReset.addEventListener('click', async () => {
    if (!confirm("確定要重置模擬帳戶本金與持倉嗎？歷史紀錄將清空。")) return;
    try {
      const res = await fetch('/api/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ capital: 1000000.0 })
      });
      if (res.ok) {
        await loadAccountData();
        await loadTradeLogs();
        alert("帳戶已被成功重置！");
      }
    } catch (err) {
      alert("重置帳戶失敗");
    }
  });

  window.viewTradeReport = function(idx) {
    const trade = currentTradeLogs[idx];
    if (trade) {
      const mdContent = `# 📜 交易單報告 (${trade.ticker} - ${trade.side})\n\n- **交易時間**: ${trade.time}\n- **成交價**: $${trade.price}\n- **股數**: ${trade.shares} 股\n- **手續費+稅金**: $${(trade.commission + trade.stamp_tax).toFixed(2)}\n\n### 🤖 AI 決策理由\n> ${trade.reason}`;
      openModal(`📜 交易單報告 - ${trade.ticker} (${trade.trade_id})`, mdContent);
    }
  };

  function openModal(title, markdownContent) {
    modalTitle.textContent = title;
    modalBody.innerHTML = marked.parse(markdownContent);
    reportModal.classList.remove('hidden');
  }

  modalClose.addEventListener('click', () => {
    reportModal.classList.add('hidden');
  });

  reportModal.addEventListener('click', (e) => {
    if (e.target === reportModal) reportModal.classList.add('hidden');
  });

  // Initial Load & Polling
  loadAccountData();
  loadTradeLogs();
  loadListenerStatus();
  loadNewsFeed();

  setInterval(loadAccountData, 10000);
  setInterval(loadNewsFeed, 15000);
  setInterval(loadListenerStatus, 30000);
});
