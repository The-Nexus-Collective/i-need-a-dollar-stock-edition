'use client'

import { useEffect, useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Activity, 
  Zap,
  RefreshCw,
  Clock,
} from 'lucide-react'
import { clsx } from 'clsx'

import { Sidebar } from '@/components/Sidebar'
import { EquityChart } from '@/components/EquityChart'
import { SentimentBarometer, SentimentGauge } from '@/components/SentimentBarometer'
import { CoinGrid } from '@/components/CoinTile'
import { PositionsList } from '@/components/PositionCard'
import { TradeHistory } from '@/components/TradeHistory'
import { DecisionLog } from '@/components/DecisionLog'

import { api } from '@/lib/api'
import { useWebSocket, useTradingStore } from '@/lib/websocket'

// ═══════════════════════════════════════════════════════════════════════════════
// HERO METRICS COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

interface MetricCardProps {
  label: string
  value: string
  subValue?: string
  trend?: 'up' | 'down' | 'neutral'
  icon?: React.ReactNode
  glow?: boolean
}

function MetricCard({ label, value, subValue, trend, icon, glow }: MetricCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={clsx(
        'glass-card p-5 transition-all duration-300',
        glow && trend === 'up' && 'border-glow-emerald',
        glow && trend === 'down' && 'border-glow-red'
      )}
    >
      <div className="flex items-start justify-between mb-3">
        <span className="text-label">{label}</span>
        {icon}
      </div>
      <div className="text-2xl font-mono font-semibold text-text-primary mb-1">
        {value}
      </div>
      {subValue && (
        <div className={clsx(
          'text-xs font-mono',
          trend === 'up' && 'text-accent-emerald',
          trend === 'down' && 'text-accent-red',
          trend === 'neutral' && 'text-text-muted'
        )}>
          {subValue}
        </div>
      )}
    </motion.div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════════

export default function Dashboard() {
  // State
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())
  const [equityHistory, setEquityHistory] = useState<{ time: number; value: number }[]>([])
  const [positions, setPositions] = useState<any[]>([])
  const [trades, setTrades] = useState<any[]>([])
  const [signals, setSignals] = useState<Record<string, any>>({})
  const [accountData, setAccountData] = useState({
    balance: 108000,
    initialBalance: 108000,
    totalFees: 0,
    slippageCost: 0,
    totalTrades: 0,
    winningTrades: 0,
    mode: 'paper' as const,
  })
  const [decisions, setDecisions] = useState<any[]>([])
  const [decisionStats, setDecisionStats] = useState({
    total_decisions: 0,
    long_decisions: 0,
    short_decisions: 0,
    flat_decisions: 0,
    filtered_decisions: 0,
    score_filtered: 0,
    volume_filtered: 0,
    executed_count: 0,
  })
  const [regimeInfo, setRegimeInfo] = useState({
    regime: 'normal',
    regime_display: 'Normal',
    threshold: 67,
    btc_atr_percent: 0,
  })
  
  // AGGRESSIVE MODE: Velocity and deployment metrics
  const [velocityMetrics, setVelocityMetrics] = useState({
    trades_last_hour: 0,
    trades_today: 0,
    trades_24h: 0,
    rebalances_today: 0,
    avg_trades_per_hour: 0,
    velocity_status: 'BELOW_TARGET',
    deployment_percent: 0,
    positions_count: 0,
    target_deployment: 0.80,
    deployment_status: 'LOW',
    force_trade_enabled: false,
  })

  // WebSocket
  const { isConnected, lastMessage } = useWebSocket({
    channel: 'all',
    onMessage: (message) => {
      if (message.type === 'equity' || message.event_type?.includes('portfolio')) {
        const equity = message.data?.total_equity || message.data?.equity
        if (equity) {
          setEquityHistory(prev => {
            const newPoint = {
              time: Math.floor(Date.now() / 1000),
              value: equity,
            }
            return [...prev.slice(-500), newPoint]
          })
          setAccountData(prev => ({ ...prev, balance: equity }))
        }
      }
      if (message.event_type?.includes('signal') && message.data?.coin) {
        setSignals(prev => ({ ...prev, [message.data.coin]: message.data }))
      }
    },
  })

  // Initial data fetch
  useEffect(() => {
    async function fetchData() {
      try {
        const [portfolioData, historyData, positionsData, signalsData, tradesData, decisionsData, statsData, regimeData, velocityData] = await Promise.all([
          api.getPortfolio().catch(() => null),
          api.getPortfolioHistory(500).catch(() => []),
          api.getPositions('open').catch(() => []),
          api.getLatestSignals().catch(() => ({})),
          api.getTrades(20).catch(() => []),
          api.getDecisions(24).catch(() => []),
          api.getDecisionStats().catch(() => null),
          api.getVolatilityRegime().catch(() => null),
          api.getVelocityMetrics().catch(() => null),
        ])

        if (portfolioData) {
          setAccountData(prev => ({
            ...prev,
            balance: portfolioData.total_equity,
          }))
        }

        if (historyData && historyData.length > 0) {
          setEquityHistory(
            historyData.map((p: any) => ({
              time: Math.floor(new Date(p.timestamp).getTime() / 1000),
              value: p.total_equity,
            }))
          )
        }

        if (positionsData) {
          setPositions(
            positionsData.map((p: any) => ({
              id: p.id,
              coin: p.coin,
              side: p.side,
              quantity: p.quantity,
              entryPrice: p.entry_price,
              currentPrice: p.current_price,
              stopLoss: p.stop_loss,
              takeProfit: p.take_profit,
              unrealizedPnl: p.unrealized_pnl,
              openedAt: p.opened_at,
            }))
          )
        }

        if (signalsData) {
          setSignals(signalsData)
        }

        if (tradesData) {
          setTrades(
            tradesData.map((t: any) => ({
              id: t.id,
              coin: t.coin,
              side: t.side,
              price: t.price,
              quantity: t.quantity,
              fee: t.fee || 0,
              slippage: 0,
              total: t.price * t.quantity,
              executedAt: t.executed_at || t.created_at,
              status: t.status,
            }))
          )
        }

        if (decisionsData) {
          setDecisions(decisionsData)
        }

        if (statsData) {
          setDecisionStats(statsData)
        }

        if (regimeData) {
          setRegimeInfo(regimeData)
        }

        if (velocityData) {
          setVelocityMetrics(velocityData)
        }

        setLastRefresh(new Date())
      } catch (error) {
        console.error('Failed to fetch data:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

  // Calculate derived values
  const pnl = accountData.balance - accountData.initialBalance
  const pnlPercent = (pnl / accountData.initialBalance) * 100
  const previousEquity = equityHistory.length > 1 
    ? equityHistory[equityHistory.length - 2]?.value || accountData.initialBalance
    : accountData.initialBalance

  // Format signals for CoinGrid
  const coinSignals = useMemo(() => {
    const coins = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'BNB', 'ADA', 'AVAX', 'TRX', 'LINK']
    return coins.map(coin => {
      const signal = signals[coin] || {}
      return {
        coin,
        sentimentScore: signal.sentiment_score || 0,
        narrativeStrength: signal.narrative_strength || 0,
        combinedScore: signal.combined_score || 0,
        filterScorePass: signal.filter_score_pass ?? true,
        filterVolumePass: signal.filter_volume_pass ?? true,
        recommendedAction: signal.recommended_action as 'long' | 'short' | 'none' | undefined,
      }
    })
  }, [signals])

  // Calculate aggregate sentiment
  const aggregateSentiment = useMemo(() => {
    const scores = coinSignals.map(s => s.combinedScore)
    if (scores.length === 0) return 0
    return scores.reduce((a, b) => a + b, 0) / scores.length
  }, [coinSignals])

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center"
        >
          <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-accent-cyan to-accent-emerald flex items-center justify-center shadow-glow-cyan-intense">
            <Zap className="w-10 h-10 text-void animate-pulse" />
          </div>
          <h1 className="text-xl font-semibold gradient-text mb-2">I Need A Dollar</h1>
          <p className="text-text-muted text-sm">Initializing trading terminal...</p>
          <div className="mt-6 flex justify-center gap-1">
            {[0, 1, 2].map(i => (
              <motion.div
                key={i}
                className="w-2 h-2 rounded-full bg-accent-cyan"
                animate={{ opacity: [0.3, 1, 0.3] }}
                transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
              />
            ))}
          </div>
        </motion.div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <Sidebar accountData={accountData} isConnected={isConnected} />

      {/* Main Content */}
      <main className="flex-1 ml-[280px] p-6 lg:p-8">
        {/* Header */}
        <header className="flex items-center justify-between mb-8">
          <div>
            <motion.h1 
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="text-2xl font-semibold text-text-primary tracking-tight flex items-center gap-3"
            >
              Trading Dashboard
              <span className="px-2 py-0.5 text-xs font-bold bg-accent-amber/20 text-accent-amber rounded border border-accent-amber/40">
                AGGRESSIVE
              </span>
              {velocityMetrics.force_trade_enabled && (
                <span className="px-2 py-0.5 text-xs font-bold bg-purple-500/20 text-purple-400 rounded border border-purple-500/40 animate-pulse">
                  FORCE_TRADE
                </span>
              )}
            </motion.h1>
            <p className="text-xs text-text-muted mt-1 flex items-center gap-2">
              <Clock className="w-3 h-3" />
              Last updated: {lastRefresh.toLocaleTimeString()} • 15min cycles
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Connection status */}
            <div className={clsx(
              'flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium',
              isConnected 
                ? 'bg-accent-emerald/10 text-accent-emerald border border-accent-emerald/30'
                : 'bg-accent-red/10 text-accent-red border border-accent-red/30'
            )}>
              <div className={clsx('status-dot', isConnected ? 'live' : 'offline')} />
              {isConnected ? 'LIVE' : 'DISCONNECTED'}
            </div>

            {/* Refresh button */}
            <button
              onClick={() => window.location.reload()}
              className="btn-ghost p-2"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </header>

        {/* Hero Metrics */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <MetricCard
            label="Portfolio Value"
            value={`$${accountData.balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}`}
            subValue={`${pnl >= 0 ? '+' : ''}${pnl.toLocaleString('en-US', { minimumFractionDigits: 2 })} (${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%)`}
            trend={pnl >= 0 ? 'up' : 'down'}
            glow
            icon={<Activity className="w-5 h-5 text-accent-cyan" />}
          />
          <MetricCard
            label="Open Positions"
            value={positions.length.toString()}
            subValue={positions.length > 0 ? `${positions.filter(p => p.unrealizedPnl >= 0).length} profitable` : 'No active trades'}
            trend="neutral"
          />
          <MetricCard
            label="Today's Trades"
            value={trades.length.toString()}
            subValue={`$${accountData.totalFees.toFixed(2)} in fees`}
            trend="neutral"
          />
          <MetricCard
            label="Win Rate"
            value={accountData.totalTrades > 0 
              ? `${((accountData.winningTrades / accountData.totalTrades) * 100).toFixed(1)}%`
              : '—'}
            subValue={accountData.totalTrades > 0 
              ? `${accountData.winningTrades}/${accountData.totalTrades} trades`
              : 'No trades yet'}
            trend={accountData.winningTrades > accountData.totalTrades / 2 ? 'up' : 'down'}
          />
        </div>

        {/* AGGRESSIVE MODE: Velocity & Deployment Metrics */}
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-label">Trades/Hour</span>
              <Zap className="w-4 h-4 text-accent-amber" />
            </div>
            <div className="text-xl font-mono font-semibold text-text-primary">
              {velocityMetrics.trades_last_hour}
            </div>
            <div className="text-xs text-text-muted">
              Avg: {velocityMetrics.avg_trades_per_hour}/hr
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="glass-card p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-label">Trades Today</span>
              <Activity className="w-4 h-4 text-accent-cyan" />
            </div>
            <div className="text-xl font-mono font-semibold text-text-primary">
              {velocityMetrics.trades_today}
            </div>
            <div className={clsx(
              'text-xs font-medium',
              velocityMetrics.velocity_status === 'ON_TARGET' && 'text-accent-emerald',
              velocityMetrics.velocity_status === 'MODERATE' && 'text-accent-amber',
              velocityMetrics.velocity_status === 'BELOW_TARGET' && 'text-accent-red'
            )}>
              {velocityMetrics.velocity_status === 'ON_TARGET' ? '✓ On target (100+)' :
               velocityMetrics.velocity_status === 'MODERATE' ? '⚡ Moderate' : '⚠ Below target'}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-label">Deployment</span>
              <Activity className="w-4 h-4 text-accent-emerald" />
            </div>
            <div className="text-xl font-mono font-semibold text-text-primary">
              {(velocityMetrics.deployment_percent * 100).toFixed(1)}%
            </div>
            <div className="mt-1 h-1.5 bg-void rounded-full overflow-hidden">
              <div 
                className={clsx(
                  'h-full rounded-full transition-all',
                  velocityMetrics.deployment_percent >= 0.80 ? 'bg-accent-emerald' :
                  velocityMetrics.deployment_percent >= 0.60 ? 'bg-accent-amber' : 'bg-accent-red'
                )}
                style={{ width: `${Math.min(velocityMetrics.deployment_percent * 100, 100)}%` }}
              />
            </div>
            <div className="text-xs text-text-muted mt-1">
              Target: {(velocityMetrics.target_deployment * 100).toFixed(0)}%
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="glass-card p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-label">Rebalances</span>
              <RefreshCw className="w-4 h-4 text-purple-400" />
            </div>
            <div className="text-xl font-mono font-semibold text-text-primary">
              {velocityMetrics.rebalances_today}
            </div>
            <div className="text-xs text-text-muted">
              15% score shift trigger
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card p-4"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-label">Score Threshold</span>
            </div>
            <div className="text-xl font-mono font-semibold text-text-primary">
              {regimeInfo.threshold}
            </div>
            <div className={clsx(
              'text-xs font-medium px-2 py-0.5 rounded-full w-fit',
              regimeInfo.regime === 'high_vol' && 'bg-accent-amber/10 text-accent-amber',
              regimeInfo.regime === 'normal' && 'bg-accent-cyan/10 text-accent-cyan',
              regimeInfo.regime === 'low_vol' && 'bg-accent-emerald/10 text-accent-emerald'
            )}>
              {regimeInfo.regime_display}
            </div>
          </motion.div>
        </div>

        {/* Main Grid */}
        <div className="grid grid-cols-12 gap-6">
          {/* Left Column - Charts & Heatmap */}
          <div className="col-span-12 xl:col-span-8 space-y-6">
            {/* Equity Chart */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
            >
              <EquityChart
                data={equityHistory}
                currentEquity={accountData.balance}
                previousEquity={previousEquity}
                isLive={isConnected}
              />
            </motion.div>

            {/* Sentiment Matrix */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <CoinGrid signals={coinSignals} />
            </motion.div>

            {/* Trade History */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              <TradeHistory trades={trades} />
            </motion.div>
          </div>

          {/* Right Column - Positions & Sentiment */}
          <div className="col-span-12 xl:col-span-4 space-y-6">
            {/* Sentiment Barometer */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 }}
            >
              <SentimentBarometer value={aggregateSentiment} />
            </motion.div>

            {/* Open Positions */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 }}
            >
              <PositionsList positions={positions} />
            </motion.div>

            {/* Decision Log */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.25 }}
            >
              <DecisionLog decisions={decisions} stats={decisionStats} />
            </motion.div>

            {/* System Status */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 }}
              className="glass-card p-5"
            >
              <span className="text-label block mb-4">System Status</span>
              
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">WebSocket</span>
                  <span className={clsx(
                    'text-xs font-medium',
                    isConnected ? 'text-accent-emerald' : 'text-accent-red'
                  )}>
                    {isConnected ? 'Connected' : 'Disconnected'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">Mode</span>
                  <span className="badge badge-paper">PAPER</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">Next Cycle</span>
                  <span className="text-xs font-mono text-text-muted">
                    {new Date().getMinutes() < 55 
                      ? `${55 - new Date().getMinutes()}m` 
                      : 'Soon'}
                  </span>
                </div>
              </div>

              {/* Volatility Regime Indicator */}
              <div className="mt-4 p-3 rounded-lg bg-surface-2 border border-white/5">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-text-muted">Volatility Regime</span>
                  <span className={clsx(
                    'text-xs font-semibold px-2 py-0.5 rounded-full',
                    regimeInfo.regime === 'high_vol' && 'bg-accent-amber/20 text-accent-amber',
                    regimeInfo.regime === 'normal' && 'bg-accent-cyan/20 text-accent-cyan',
                    regimeInfo.regime === 'low_vol' && 'bg-accent-emerald/20 text-accent-emerald'
                  )}>
                    {regimeInfo.regime_display}
                  </span>
                </div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-text-muted">Score Threshold</span>
                  <span className="text-sm font-mono text-text-primary font-semibold">
                    {regimeInfo.threshold}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-muted">BTC ATR</span>
                  <span className="text-xs font-mono text-text-secondary">
                    {regimeInfo.btc_atr_percent}%
                  </span>
                </div>
              </div>

              <div className="mt-4 p-3 rounded-lg bg-accent-emerald/10 border border-accent-emerald/20">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse" />
                  <span className="text-xs text-accent-emerald font-medium">
                    All Systems Operational
                  </span>
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </main>
    </div>
  )
}
