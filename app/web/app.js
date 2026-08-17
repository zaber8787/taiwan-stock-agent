// Web GUI JavaScript App Logic - Pure Monitoring Command Center
document.addEventListener('DOMContentLoaded', () => {
  const statEquity = document.getElementById('stat-equity');
  const statInitial = document.getElementById('stat-initial');
  const statCash = document.getElementById('stat-cash');
  const statMaxAlloc = document.getElementById('stat-max-alloc');
  const statHoldingsVal = document.getElementById('stat-holdings-val');
  const statPositionsLimit = document.getElementById('stat-positions-limit');
  const statRoi = document.getElementById('stat-roi');
  const statUnrealized = document.getElementById('stat-unrealized');
  const statRealized = document.getElementById('stat-realized');
  const statDbCount = document.getElementById('stat-db-count');

  const mktStatusText = document.getElementById('mkt-status-text');
  const dbMongoBadge = document.getElementById('db-mongo-badge');
  const dbQdrantBadge = document.getElementById('db-qdrant-badge');

  const btnReset = document.getElementById('btn-reset');
  const feedContainer = document.getElementById('feed-container');
  const watchlistContainer = document.getElementById('watchlist-container');
  const universeTbody = document.getElementById('universe-tbody');
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

  // Load Market Status (Trading hours vs Off-market)
  async function loadMarketStatus() {
    try {
      const res = await fetch('/api/market-status');
      if (!res.ok) return;
      const data = await res.json();
      if (mktStatusText) mktStatusText.textContent = data.status_text || '🟢 盤中交易中';
    } catch (err) {
      console.error("Failed to load market status:", err);
    }
  }

  // Load Active Watchlist Timers (WATCH mode)
  async function loadWatchlistTimers() {
    try {
      const res = await fetch('/api/watchlist');
      if (!res.ok) return;
      const data = await res.json();
      renderWatchlistTimers(data.watchlist || []);
    } catch (err) {
      console.error("Failed to load watchlist timers:", err);
    }
  }

  function renderWatchlistTimers(list) {
    if (!list || list.length === 0) {
      watchlistContainer.innerHTML = `<div class="empty-feed">尚無 Agent 預約的排程觀察標的。當 Agent 偵測到連動族群補漲機會時，將在此處展示倒數與觀察原因。</div>`;
      return;
    }

    watchlistContainer.innerHTML = list.map(w => {
      const remMins = Math.floor(w.remaining_seconds / 60);
      const remSecs = w.remaining_seconds % 60;
      const timeStr = `${remMins}分 ${remSecs}秒`;
      return `
        <div class="watch-item">
          <div class="watch-info">
            <span class="watch-ticker">[${w.ticker}]</span>
            <span>觀察原因: ${w.reason}</span>
            ${w.deferred_off_market ? '<span class="badge" style="background:rgba(255,171,0,0.2); color:#ffab00;">隔日開盤再評估</span>' : ''}
          </div>
          <div class="watch-timer">⏱️ 倒數 ${timeStr}</div>
        </div>
      `;
    }).join('');
  }

  // Load Full Universe Watchlist Grid
  async function loadUniverseWatchlist() {
    try {
      const res = await fetch('/api/autotrader/universe');
      if (!res.ok) return;
      const data = await res.json();
      renderUniverseTable(data.universe || []);
    } catch (err) {
      console.error("Failed to load universe watchlist:", err);
    }
  }

  function renderUniverseTable(items) {
    if (!items || items.length === 0) {
      universeTbody.innerHTML = `<tr><td colspan="6" class="empty-msg">全自動交易引擎巡檢中...</td></tr>`;
      return;
    }

    universeTbody.innerHTML = items.map(u => {
      const sideBadge = `<span class="${u.ai_signal === 'BUY' ? 'badge-buy' : u.ai_signal === 'SELL' ? 'badge-sell' : 'badge-hold'}">${u.ai_signal}</span>`;
      return `
        <tr>
          <td><strong>${u.ticker}</strong></td>
          <td>$${u.price.toFixed(2)}</td>
          <td>${sideBadge}</td>
          <td>${(u.confidence * 100).toFixed(0)}%</td>
          <td><span style="color:${u.holding_status.includes('持有') ? 'var(--profit-color)' : 'var(--text-muted)'}">${u.holding_status}</span></td>
          <td style="font-size:0.8rem; color:var(--text-muted);">${u.updated_at}</td>
        </tr>
      `;
    }).join('');
  }

  // Load Listener & DB Status
  async function loadListenerStatus() {
    try {
      const res = await fetch('/api/listener/status');
      if (!res.ok) return;
      const data = await res.json();
      if (statDbCount) statDbCount.textContent = data.companies_in_db || 0;

      if (data.db) {
        updateDbBadge(dbMongoBadge, 'Mongo', data.db.mongo);
        updateDbBadge(dbQdrantBadge, 'Qdrant', data.db.qdrant);
      }
    } catch (err) {
      console.error("Failed to load listener status:", err);
    }
  }

  const discordBadge = document.getElementById('discord-badge');
  const btnNotifyTest = document.getElementById('btn-notify-test');

  const regimeBadge = document.getElementById('regime-badge');

  async function loadMarketRegime() {
    try {
      const res = await fetch('/api/market/regime');
      if (!res.ok) return;
      const data = await res.json();
      if (regimeBadge) {
        let tagClass = 'online';
        if (data.regime === 'BEAR') tagClass = 'offline';
        else if (data.regime === 'RANGING') tagClass = 'fallback';
        
        const allocStr = `${(data.allocation_multiplier * 100).toFixed(0)}%撥款`;
        regimeBadge.innerHTML = `大盤: <span class="badge-tag ${tagClass}" title="${data.rationale}">${data.regime_name_zh} (${allocStr})</span>`;
      }
    } catch (err) {
      console.error("Failed to load market regime:", err);
    }
  }

  async function loadNotificationStatus() {
    try {
      const res = await fetch('/api/notify/status');
      if (!res.ok) return;
      const data = await res.json();
      if (discordBadge) {
        if (data.configured && data.enabled) {
          discordBadge.innerHTML = `Discord: <span class="badge-tag online">✅ 已啟用</span>`;
        } else if (!data.configured) {
          discordBadge.innerHTML = `Discord: <span class="badge-tag fallback" title="請在 .env 設定 DISCORD_WEBHOOK_URL">⚠️ 未設定</span>`;
        } else {
          discordBadge.innerHTML = `Discord: <span class="badge-tag fallback">⏸️ 已暫停</span>`;
        }
      }
    } catch (err) {
      console.error("Failed to load notify status:", err);
    }
  }

  if (btnNotifyTest) {
    btnNotifyTest.addEventListener('click', async () => {
      try {
        btnNotifyTest.disabled = true;
        btnNotifyTest.textContent = '⏳ 發送中...';
        const res = await fetch('/api/notify/test', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          alert("🎉 Discord Webhook 測試推播已成功送出！請至 Discord 頻道確認。");
        } else {
          alert("⚠️ " + (data.message || "發送失敗，請確認 Webhook URL 配置"));
        }
        await loadNotificationStatus();
      } catch (err) {
        alert("測試發送時發生異常: " + err);
      } finally {
        btnNotifyTest.disabled = false;
        btnNotifyTest.textContent = '🔔 測試推播';
      }
    });
  }

  function updateDbBadge(el, name, dbInfo) {
    if (!el || !dbInfo) return;
    if (dbInfo.connected) {
      el.innerHTML = `${name}: <span class="badge-tag online">✅ 連線成功</span>`;
    } else {
      el.innerHTML = `${name}: <span class="badge-tag fallback" title="${dbInfo.reason}">⚠️ 本地備份檔</span>`;
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
      feedContainer.innerHTML = `<div class="empty-feed">📡 背景新聞監聽與全自動交易運作中...（每 3 分鐘自動偵測並廣播事件）</div>`;
      return;
    }

    feedContainer.innerHTML = events.map(ev => {
      const isBuy = ev.side === 'BUY';
      const sideBadge = `<span class="${isBuy ? 'badge-buy' : 'badge-sell'}">${ev.side} (${(ev.confidence * 100).toFixed(0)}%)</span>`;
      const timeStr = ev.timestamp ? ev.timestamp.replace('T', ' ').substring(11, 19) : '--';
      const catName = ev.event_category_name || '📰 一般產經';
      const catBadge = `<span class="badge-cat">${catName}</span>`;
      return `
        <div class="feed-item">
          <div class="feed-title">
            <span style="color:var(--primary-accent); margin-right:0.5rem;">[${ev.ticker}]</span>
            ${catBadge}
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
      statPositionsLimit.textContent = `${data.holdings.length} / ${data.max_positions_limit || 5} 檔`;
      
      const roi = data.total_roi_pct || 0;
      statRoi.textContent = (roi >= 0 ? '+' : '') + roi.toFixed(2) + '%';
      statRoi.className = 'stat-value ' + (roi > 0 ? 'profit' : roi < 0 ? 'loss' : 'neutral');

      statUnrealized.textContent = formatMoney(data.unrealized_pnl);
      statRealized.textContent = formatMoney(data.realized_pnl);

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
      holdingsTbody.innerHTML = `<tr><td colspan="9" class="empty-msg">目前尚無股票持倉。</td></tr>`;
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
          <td>$${(h.highest_price || h.cost_price).toFixed(2)}</td>
          <td style="font-size:0.8rem; color:var(--text-muted);">${h.buy_date || '--'}</td>
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
      const taxLabel = t.tax_rate_label ? `<br><span style="font-size:0.7rem; color:var(--profit-color);">${t.tax_rate_label}</span>` : '';

      return `
        <tr>
          <td style="font-size:0.8rem; color:var(--text-muted);">${timeStr}</td>
          <td><code>${t.trade_id}</code></td>
          <td><strong>${t.ticker}</strong></td>
          <td>${sideBadge}</td>
          <td>$${t.price.toFixed(2)} <span style="font-size:0.7rem; color:var(--text-muted);">(含0.5%滑價)</span></td>
          <td>${t.shares.toLocaleString()} 股</td>
          <td>${formatMoney(costOrRev)}</td>
          <td>$${taxFee.toFixed(2)} ${taxLabel}</td>
          <td style="max-width:240px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${t.reason}">${t.reason}</td>
          <td><button class="btn btn-secondary btn-action-small" onclick="viewTradeReport(${idx})">檢視報告</button></td>
        </tr>
      `;
    }).join('');
  }

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
        alert("帳戶與持倉已被成功重置！");
      }
    } catch (err) {
      alert("重置帳戶失敗");
    }
  });

  window.viewTradeReport = function(idx) {
    const trade = currentTradeLogs[idx];
    if (trade) {
      const mdContent = `# 📜 交易單報告 (${trade.ticker} - ${trade.side})\n\n- **交易時間**: ${trade.time}\n- **成交價 (含0.5%滑價)**: $${trade.price}\n- **股數**: ${trade.shares} 股\n- **券商手續費 (2折)**: $${trade.commission.toFixed(2)}\n- **證交稅**: $${(trade.stamp_tax || 0).toFixed(2)} ${trade.tax_rate_label || ''}\n\n### 🤖 AI 決策與離場觸發理由\n> ${trade.reason}`;
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

  // Initial Load & Polling Loops
  loadAccountData();
  loadTradeLogs();
  loadMarketStatus();
  loadMarketRegime();
  loadWatchlistTimers();
  loadUniverseWatchlist();
  loadListenerStatus();
  loadNotificationStatus();
  loadNewsFeed();

  setInterval(loadWatchlistTimers, 3000);
  setInterval(loadAccountData, 8000);
  setInterval(loadUniverseWatchlist, 10000);
  setInterval(loadNewsFeed, 12000);
  setInterval(loadMarketStatus, 30000);
  setInterval(loadMarketRegime, 30000);
  setInterval(loadListenerStatus, 30000);
  setInterval(loadNotificationStatus, 30000);
});
