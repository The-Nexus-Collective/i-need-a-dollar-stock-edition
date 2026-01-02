"""
Real-Time Trading Dashboard

Features:
- Live equity curve with WebSocket updates
- Real-time position PnL
- 10-coin sentiment heatmap
- Trade execution log with fees/slippage
- Cost breakdown (fees, slippage)
"""

import os
import time
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
from sqlalchemy import create_engine, text

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Crypto Trading Bot",
    page_icon="💹",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM CSS
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

:root {
    --bg-dark: #0a0a0f;
    --bg-card: rgba(18, 18, 26, 0.85);
    --border: rgba(255, 255, 255, 0.08);
    --text: #e8e8ed;
    --text-dim: #8b8b99;
    --accent: #00d4ff;
    --green: #00ff88;
    --red: #ff4757;
    --yellow: #ffd93d;
}

.stApp {
    background: linear-gradient(145deg, #0a0a0f 0%, #12121a 50%, #0d0d14 100%);
    font-family: 'Space Grotesk', sans-serif;
}

#MainMenu, footer, header {visibility: hidden;}

.metric-card {
    background: var(--bg-card);
    backdrop-filter: blur(20px);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    text-align: center;
}

.metric-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 2.2rem;
    font-weight: 700;
    color: var(--text);
}

.metric-value.positive { color: var(--green); }
.metric-value.negative { color: var(--red); }

.metric-label {
    color: var(--text-dim);
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 8px;
}

.live-indicator {
    display: inline-block;
    width: 8px;
    height: 8px;
    background: var(--green);
    border-radius: 50%;
    margin-right: 8px;
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.4); }
    50% { opacity: 0.8; box-shadow: 0 0 0 8px rgba(0, 255, 136, 0); }
}

.position-card {
    background: linear-gradient(135deg, rgba(0, 212, 255, 0.1), rgba(0, 255, 136, 0.05));
    border: 1px solid rgba(0, 212, 255, 0.3);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 16px;
}

.position-card.short {
    background: linear-gradient(135deg, rgba(255, 71, 87, 0.1), rgba(155, 89, 182, 0.05));
    border-color: rgba(255, 71, 87, 0.3);
}

.heatmap-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 10px;
}

.heatmap-cell {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px;
    text-align: center;
    transition: all 0.2s;
}

.heatmap-cell:hover {
    transform: translateY(-2px);
    border-color: var(--accent);
}

.cost-breakdown {
    background: var(--bg-card);
    border-radius: 12px;
    padding: 16px;
}

.cost-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid var(--border);
}

.cost-row:last-child { border-bottom: none; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════════════════════

DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://trading_user:trading_secret_2024@localhost:5432/trading_platform'
)
WS_URL = os.getenv('WS_URL', 'ws://localhost:8000/ws/live')

@st.cache_resource
def get_engine():
    return create_engine(DATABASE_URL)

def query(sql: str, params: dict = None) -> pd.DataFrame:
    try:
        return pd.read_sql(text(sql), get_engine(), params=params or {})
    except Exception as e:
        st.error(f"DB Error: {e}")
        return pd.DataFrame()

# ═══════════════════════════════════════════════════════════════════════════════
# DATA QUERIES
# ═══════════════════════════════════════════════════════════════════════════════

def get_account_state() -> dict:
    df = query("""
        SELECT * FROM account_state WHERE account_id = 'paper_main'
    """)
    if len(df) > 0:
        return df.iloc[0].to_dict()
    return {
        'balance_usdt': 108000, 'initial_balance': 108000,
        'total_fees_paid': 0, 'total_slippage_cost': 0,
        'total_trades': 0, 'winning_trades': 0, 'realized_pnl': 0
    }

def get_equity_history(minutes: int = 60) -> pd.DataFrame:
    return query(f"""
        SELECT timestamp, equity, cash, positions_value, unrealized_pnl, btc_price
        FROM account_equity_history
        WHERE account_id = 'paper_main'
        AND timestamp >= NOW() - INTERVAL '{minutes} minutes'
        ORDER BY timestamp ASC
    """)

def get_open_positions() -> pd.DataFrame:
    return query("""
        SELECT coin, side, quantity, entry_price, current_price,
               stop_loss, take_profit, unrealized_pnl, opened_at
        FROM positions WHERE status = 'open'
    """)

def get_latest_signals() -> pd.DataFrame:
    return query("""
        WITH latest AS (
            SELECT DISTINCT ON (coin) *
            FROM signals ORDER BY coin, timestamp DESC
        )
        SELECT coin, sentiment_score, narrative_strength, combined_score,
               filter_score_pass, filter_volume_pass, price_at_signal
        FROM latest ORDER BY ABS(combined_score) DESC
    """)

def get_recent_trades(limit: int = 20) -> pd.DataFrame:
    return query(f"""
        SELECT t.coin, t.side, t.quantity, t.price, t.fee, 
               t.slippage_cost, t.total_cost, t.executed_at,
               p.realized_pnl
        FROM trades t
        LEFT JOIN positions p ON t.position_id = p.id
        WHERE t.status = 'filled'
        ORDER BY t.executed_at DESC
        LIMIT {limit}
    """)

def get_filter_stats() -> dict:
    df = query("""
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE filter_score_pass AND filter_volume_pass) as passed,
            COUNT(*) FILTER (WHERE NOT filter_score_pass) as score_fail,
            COUNT(*) FILTER (WHERE filter_score_pass AND NOT filter_volume_pass) as vol_fail
        FROM signals WHERE timestamp >= CURRENT_DATE
    """)
    if len(df) > 0:
        return df.iloc[0].to_dict()
    return {'total': 0, 'passed': 0, 'score_fail': 0, 'vol_fail': 0}

# ═══════════════════════════════════════════════════════════════════════════════
# LIVE CHART COMPONENT
# ═══════════════════════════════════════════════════════════════════════════════

def render_live_equity_chart():
    """Render JavaScript-based live updating equity chart"""
    
    # Get initial data
    history = get_equity_history(60)
    initial_data = []
    if len(history) > 0:
        initial_data = [
            {"x": row['timestamp'].isoformat(), "y": float(row['equity'])}
            for _, row in history.iterrows()
        ]
    
    components.html(f"""
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <div id="live-equity-chart" style="width:100%; height:350px;"></div>
    
    <script>
    const initialData = {initial_data};
    const wsUrl = "{WS_URL}";
    
    // Initialize chart
    const trace = {{
        x: initialData.map(d => d.x),
        y: initialData.map(d => d.y),
        type: 'scatter',
        mode: 'lines',
        fill: 'tozeroy',
        line: {{ color: '#00d4ff', width: 2 }},
        fillcolor: 'rgba(0, 212, 255, 0.1)'
    }};
    
    const layout = {{
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        margin: {{ l: 60, r: 20, t: 20, b: 40 }},
        xaxis: {{
            showgrid: false,
            color: '#8b8b99',
            tickformat: '%H:%M'
        }},
        yaxis: {{
            showgrid: true,
            gridcolor: 'rgba(255,255,255,0.05)',
            color: '#8b8b99',
            tickprefix: '$',
            tickformat: ',.0f'
        }},
        hovermode: 'x unified'
    }};
    
    Plotly.newPlot('live-equity-chart', [trace], layout, {{
        displayModeBar: false,
        responsive: true
    }});
    
    // WebSocket connection
    let ws;
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 10;
    
    function connect() {{
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {{
            console.log('WebSocket connected');
            reconnectAttempts = 0;
        }};
        
        ws.onmessage = (event) => {{
            const data = JSON.parse(event.data);
            
            if (data.type === 'equity' || data.type === 'init') {{
                const equity = data.type === 'init' ? data.equity?.equity : data.equity;
                const timestamp = new Date(data.timestamp * 1000).toISOString();
                
                if (equity) {{
                    Plotly.extendTraces('live-equity-chart', {{
                        x: [[timestamp]],
                        y: [[equity]]
                    }}, [0]);
                    
                    // Keep last 500 points
                    const traceLen = document.getElementById('live-equity-chart').data[0].x.length;
                    if (traceLen > 500) {{
                        Plotly.relayout('live-equity-chart', {{
                            'xaxis.range': [
                                document.getElementById('live-equity-chart').data[0].x[traceLen - 500],
                                document.getElementById('live-equity-chart').data[0].x[traceLen - 1]
                            ]
                        }});
                    }}
                }}
            }}
        }};
        
        ws.onclose = () => {{
            console.log('WebSocket closed');
            if (reconnectAttempts < maxReconnectAttempts) {{
                reconnectAttempts++;
                setTimeout(connect, 2000 * reconnectAttempts);
            }}
        }};
        
        ws.onerror = (err) => {{
            console.error('WebSocket error:', err);
        }};
    }}
    
    connect();
    </script>
    """, height=370)

# ═══════════════════════════════════════════════════════════════════════════════
# UI COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

def render_sidebar():
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="color: #00d4ff; font-size: 1.4rem; margin: 0;">💹 TRADING BOT</h1>
            <p style="color: #8b8b99; font-size: 0.8rem;">Real-Time Paper Trading</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Status
        mode = os.getenv('MODE', 'paper').upper()
        st.markdown(f"""
        <div style="text-align: center; margin-bottom: 20px;">
            <span class="live-indicator"></span>
            <span style="color: #00ff88; font-weight: 600;">{mode} MODE</span>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # Account summary
        account = get_account_state()
        st.metric("Initial Balance", f"${account['initial_balance']:,.2f}")
        st.metric("Total Fees", f"${account['total_fees_paid']:,.2f}")
        st.metric("Slippage Cost", f"${account['total_slippage_cost']:,.2f}")
        
        st.divider()
        
        # Filter stats
        filters = get_filter_stats()
        st.markdown("### 📊 Filter Stats Today")
        cols = st.columns(2)
        cols[0].metric("Passed", filters.get('passed', 0))
        cols[1].metric("Filtered", filters.get('score_fail', 0) + filters.get('vol_fail', 0))
        
        st.divider()
        
        st.caption(f"Last refresh: {datetime.now().strftime('%H:%M:%S')}")
        
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.rerun()

def render_hero_metrics():
    account = get_account_state()
    
    equity = float(account.get('balance_usdt', 108000))
    initial = float(account.get('initial_balance', 108000))
    pnl = equity - initial
    pnl_pct = (pnl / initial * 100) if initial > 0 else 0
    fees = float(account.get('total_fees_paid', 0))
    slippage = float(account.get('total_slippage_cost', 0))
    trades = int(account.get('total_trades', 0))
    wins = int(account.get('winning_trades', 0))
    win_rate = (wins / trades * 100) if trades > 0 else 0
    
    cols = st.columns(5)
    
    with cols[0]:
        pnl_class = "positive" if pnl >= 0 else "negative"
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">${equity:,.2f}</div>
            <div class="metric-label">Equity</div>
            <div style="color: {'#00ff88' if pnl >= 0 else '#ff4757'}; margin-top: 4px;">
                {'+' if pnl >= 0 else ''}{pnl_pct:.2f}%
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[1]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value {'positive' if pnl >= 0 else 'negative'}">${pnl:+,.2f}</div>
            <div class="metric-label">Net P&L</div>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[2]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{win_rate:.1f}%</div>
            <div class="metric-label">Win Rate</div>
            <div style="color: #8b8b99; margin-top: 4px;">{wins}/{trades}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[3]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: #ffd93d;">${fees:,.2f}</div>
            <div class="metric-label">Total Fees</div>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[4]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color: #ff9f43;">${slippage:,.2f}</div>
            <div class="metric-label">Slippage</div>
        </div>
        """, unsafe_allow_html=True)

def render_positions():
    st.markdown("### 📊 Open Positions")
    
    positions = get_open_positions()
    
    if len(positions) == 0:
        st.info("No open positions")
        return
    
    for _, pos in positions.iterrows():
        is_long = pos['side'] == 'long'
        pnl = float(pos['unrealized_pnl'] or 0)
        entry = float(pos['entry_price'])
        current = float(pos['current_price'] or entry)
        pnl_pct = ((current - entry) / entry * 100) if is_long else ((entry - current) / entry * 100)
        
        card_class = "position-card" if is_long else "position-card short"
        
        st.markdown(f"""
        <div class="{card_class}">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="color: {'#00ff88' if is_long else '#ff4757'}; font-weight: 600;">
                        {'🟢 LONG' if is_long else '🔴 SHORT'}
                    </span>
                    <span style="font-size: 1.5rem; font-weight: 700; margin-left: 10px;">{pos['coin']}</span>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 1.3rem; font-weight: 600; color: {'#00ff88' if pnl >= 0 else '#ff4757'};">
                        ${pnl:+,.2f}
                    </div>
                    <div style="color: #8b8b99;">{pnl_pct:+.2f}%</div>
                </div>
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 15px; color: #8b8b99; font-size: 0.85rem;">
                <span>Entry: ${entry:,.2f}</span>
                <span>Current: ${current:,.2f}</span>
                <span>Qty: {float(pos['quantity']):.4f}</span>
                <span>SL: ${float(pos['stop_loss'] or 0):,.2f}</span>
                <span>TP: ${float(pos['take_profit'] or 0):,.2f}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

def render_heatmap():
    st.markdown("### 🔥 Sentiment Heatmap")
    
    signals = get_latest_signals()
    
    if len(signals) == 0:
        st.info("No signal data")
        return
    
    cells_html = ""
    for _, row in signals.iterrows():
        score = float(row.get('combined_score', 0))
        coin = row['coin']
        
        if score > 40:
            bg = "linear-gradient(135deg, rgba(0, 255, 136, 0.2), rgba(0, 212, 255, 0.1))"
            color = "#00ff88"
        elif score < -40:
            bg = "linear-gradient(135deg, rgba(255, 71, 87, 0.2), rgba(155, 89, 182, 0.1))"
            color = "#ff4757"
        else:
            bg = "var(--bg-card)"
            color = "#8b8b99"
        
        filters = ""
        if not row.get('filter_score_pass', True):
            filters += "⚠️"
        if not row.get('filter_volume_pass', True):
            filters += "📉"
        
        cells_html += f"""
        <div class="heatmap-cell" style="background: {bg};">
            <div style="font-weight: 600; color: var(--text);">{coin} {filters}</div>
            <div style="font-size: 1.4rem; font-weight: 700; color: {color}; margin: 5px 0;">
                {score:+.1f}
            </div>
            <div style="font-size: 0.75rem; color: var(--text-dim);">
                S:{float(row.get('sentiment_score', 0)):.0f} N:{float(row.get('narrative_strength', 0)):.0f}
            </div>
        </div>
        """
    
    st.markdown(f'<div class="heatmap-grid">{cells_html}</div>', unsafe_allow_html=True)

def render_trades():
    st.markdown("### 📜 Recent Trades")
    
    trades = get_recent_trades(15)
    
    if len(trades) == 0:
        st.info("No trades yet")
        return
    
    # Format as dataframe
    display_df = trades.copy()
    display_df['time'] = pd.to_datetime(display_df['executed_at']).dt.strftime('%m/%d %H:%M')
    display_df['fee'] = display_df['fee'].apply(lambda x: f"${float(x or 0):.2f}")
    display_df['slippage'] = display_df['slippage_cost'].apply(lambda x: f"${float(x or 0):.2f}")
    display_df['pnl'] = display_df['realized_pnl'].apply(
        lambda x: f"${float(x or 0):+,.2f}" if x else "-"
    )
    
    st.dataframe(
        display_df[['time', 'coin', 'side', 'quantity', 'price', 'fee', 'slippage', 'pnl']],
        use_container_width=True,
        hide_index=True
    )

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    render_sidebar()
    
    # Hero metrics
    render_hero_metrics()
    
    st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)
    
    # Live equity chart
    st.markdown("### 📈 Live Equity")
    render_live_equity_chart()
    
    st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)
    
    # Two column layout
    col1, col2 = st.columns([3, 2])
    
    with col1:
        render_heatmap()
        st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)
        render_trades()
    
    with col2:
        render_positions()

if __name__ == "__main__":
    main()