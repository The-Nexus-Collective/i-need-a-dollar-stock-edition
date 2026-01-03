'use client'

import { useEffect, useState, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  TrendingUp, 
  TrendingDown,
  Zap,
  RefreshCw,
  Clock,
  DollarSign,
  Activity,
  Target,
  BarChart3,
  LineChart,
  Wallet,
} from 'lucide-react'
import { clsx } from 'clsx'

import { Sidebar } from '@/components/Sidebar'
import { api } from '@/lib/api'

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface Prediction {
  id: string
  cycle_id: string
  cycle_number: number
  coin: string
  direction: string
  conviction: number
  leverage: number
  reason: string
  created_at: string
}

interface Cycle {
  id: string
  cycle_number: number
  started_at: string
  completed_at: string | null
  capital_before: number
  capital_after: number
  total_pnl: number
  coins_traded: string[]
  status: string
  prediction_count: number
  avg_conviction: number
}

interface TraderStatus {
  running: boolean
  cycle_count: number
  executor: {
    capital: number
    starting_capital: number
    total_pnl: number
    total_pnl_pct: number
    open_positions: number
    total_cycles: number
    total_trades: number
    positions: any[]
    total_fees_paid: number
    total_spread_cost: number
    total_slippage_cost: number
    total_trading_costs: number
  }
  top_coins_count: number
  cycle_interval_seconds: number
  mode: string
}

interface EquityPoint {
  timestamp: string
  total_equity: number
  unrealized_pnl: number
  cash: number
}

// ═══════════════════════════════════════════════════════════════════════════════
// PREDICTION CARD COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

function PredictionCard({ prediction }: { prediction: Prediction }) {
  const isLong = prediction.direction === 'LONG'
  
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={clsx(
        'glass-card p-3 border-l-4 transition-all hover:scale-[1.02]',
        isLong ? 'border-l-accent-emerald' : 'border-l-accent-red'
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-text-primary">{prediction.coin}</span>
          <span className={clsx(
            'px-2 py-0.5 text-xs font-bold rounded',
            isLong 
              ? 'bg-accent-emerald/20 text-accent-emerald' 
              : 'bg-accent-red/20 text-accent-red'
          )}>
            {prediction.direction}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {isLong ? (
            <TrendingUp className="w-5 h-5 text-accent-emerald" />
          ) : (
            <TrendingDown className="w-5 h-5 text-accent-red" />
          )}
        </div>
      </div>
      
      <div className="grid grid-cols-2 gap-2 mb-2">
        <div>
          <span className="text-xs text-text-muted">Conviction</span>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 bg-surface-2 rounded-full overflow-hidden">
              <div 
                className={clsx(
                  'h-full rounded-full transition-all',
                  prediction.conviction >= 70 ? 'bg-accent-emerald' :
                  prediction.conviction >= 50 ? 'bg-accent-amber' : 'bg-accent-red'
                )}
                style={{ width: `${prediction.conviction}%` }}
              />
            </div>
            <span className="text-sm font-mono font-bold text-text-primary">
              {prediction.conviction}%
            </span>
          </div>
        </div>
        <div>
          <span className="text-xs text-text-muted">Leverage</span>
          <div className="text-sm font-mono font-bold text-accent-cyan">
            {prediction.leverage.toFixed(1)}x
          </div>
        </div>
      </div>
      
      <p className="text-xs text-text-secondary italic truncate">
        "{prediction.reason}"
      </p>
    </motion.div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// EQUITY CHART COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

function EquityChart({ data, startingCapital }: { data: EquityPoint[], startingCapital: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  
  useEffect(() => {
    if (!canvasRef.current || data.length < 2) return
    
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    
    // High DPI canvas
    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    ctx.scale(dpr, dpr)
    
    // Clear
    ctx.clearRect(0, 0, rect.width, rect.height)
    
    // Calculate bounds
    const values = data.map(d => d.total_equity)
    const minVal = Math.min(...values, startingCapital * 0.95)
    const maxVal = Math.max(...values, startingCapital * 1.05)
    const range = maxVal - minVal || 1
    
    const padding = { top: 20, right: 10, bottom: 30, left: 50 }
    const chartWidth = rect.width - padding.left - padding.right
    const chartHeight = rect.height - padding.top - padding.bottom
    
    // Draw grid lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)'
    ctx.lineWidth = 1
    for (let i = 0; i <= 4; i++) {
      const y = padding.top + (chartHeight * i / 4)
      ctx.beginPath()
      ctx.moveTo(padding.left, y)
      ctx.lineTo(rect.width - padding.right, y)
      ctx.stroke()
      
      // Y-axis labels
      const val = maxVal - (range * i / 4)
      ctx.fillStyle = 'rgba(255, 255, 255, 0.4)'
      ctx.font = '10px monospace'
      ctx.textAlign = 'right'
      ctx.fillText(`$${(val / 1000).toFixed(1)}k`, padding.left - 5, y + 3)
    }
    
    // Draw baseline (starting capital)
    const baselineY = padding.top + ((maxVal - startingCapital) / range) * chartHeight
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)'
    ctx.setLineDash([4, 4])
    ctx.beginPath()
    ctx.moveTo(padding.left, baselineY)
    ctx.lineTo(rect.width - padding.right, baselineY)
    ctx.stroke()
    ctx.setLineDash([])
    
    // Draw equity line with gradient
    const latestEquity = values[values.length - 1]
    const isProfit = latestEquity >= startingCapital
    const color = isProfit ? '#10b981' : '#ef4444'
    
    ctx.beginPath()
    ctx.strokeStyle = color
    ctx.lineWidth = 2
    ctx.lineJoin = 'round'
    
    data.forEach((point, i) => {
      const x = padding.left + (i / (data.length - 1)) * chartWidth
      const y = padding.top + ((maxVal - point.total_equity) / range) * chartHeight
      
      if (i === 0) {
        ctx.moveTo(x, y)
      } else {
        ctx.lineTo(x, y)
      }
    })
    ctx.stroke()
    
    // Fill gradient under line
    const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartHeight)
    gradient.addColorStop(0, isProfit ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)')
    gradient.addColorStop(1, 'rgba(0, 0, 0, 0)')
    
    ctx.lineTo(padding.left + chartWidth, padding.top + chartHeight)
    ctx.lineTo(padding.left, padding.top + chartHeight)
    ctx.closePath()
    ctx.fillStyle = gradient
    ctx.fill()
    
    // Draw latest value dot
    const lastX = padding.left + chartWidth
    const lastY = padding.top + ((maxVal - latestEquity) / range) * chartHeight
    ctx.beginPath()
    ctx.arc(lastX, lastY, 4, 0, Math.PI * 2)
    ctx.fillStyle = color
    ctx.fill()
    ctx.beginPath()
    ctx.arc(lastX, lastY, 6, 0, Math.PI * 2)
    ctx.strokeStyle = color
    ctx.lineWidth = 2
    ctx.stroke()
    
  }, [data, startingCapital])
  
  const latestEquity = data[data.length - 1]?.total_equity || startingCapital
  const pnl = latestEquity - startingCapital
  const pnlPct = (pnl / startingCapital) * 100
  
  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
          <LineChart className="w-4 h-4 text-accent-cyan" />
          Real-Time Equity
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">{data.length}s</span>
          <span className={clsx(
            'text-sm font-mono font-bold',
            pnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'
          )}>
            {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)} ({pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(3)}%)
          </span>
        </div>
      </div>
      <div className="relative h-64">
        {data.length < 2 ? (
          <div className="absolute inset-0 flex items-center justify-center text-text-muted text-sm">
            <div className="text-center">
              <LineChart className="w-8 h-8 mx-auto mb-2 opacity-20 animate-pulse" />
              <p>Waiting for equity data...</p>
            </div>
          </div>
        ) : (
          <canvas 
            ref={canvasRef} 
            className="w-full h-full"
            style={{ width: '100%', height: '100%' }}
          />
        )}
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// CYCLE CARD COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

function CycleCard({ cycle }: { cycle: Cycle }) {
  const pnl = cycle.total_pnl || 0
  const isProfit = pnl >= 0
  
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      className="glass-card p-3"
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-accent-cyan">Cycle #{cycle.cycle_number}</span>
          <span className={clsx(
            'px-2 py-0.5 text-xs rounded',
            cycle.status === 'completed' ? 'bg-accent-emerald/20 text-accent-emerald' : 'bg-accent-amber/20 text-accent-amber'
          )}>
            {cycle.status}
          </span>
        </div>
        <span className="text-xs text-text-muted">
          {new Date(cycle.started_at).toLocaleTimeString()}
        </span>
      </div>
      
      <div className="grid grid-cols-3 gap-3 mb-3">
        <div>
          <span className="text-xs text-text-muted block">Capital</span>
          <span className="text-sm font-mono text-text-primary">
            ${cycle.capital_after?.toLocaleString() || cycle.capital_before?.toLocaleString()}
          </span>
        </div>
        <div>
          <span className="text-xs text-text-muted block">PnL</span>
          <span className={clsx(
            'text-sm font-mono font-bold',
            isProfit ? 'text-accent-emerald' : 'text-accent-red'
          )}>
            {isProfit ? '+' : ''}{pnl.toFixed(2)}
          </span>
        </div>
        <div>
          <span className="text-xs text-text-muted block">Avg Conviction</span>
          <span className="text-sm font-mono text-text-primary">
            {cycle.avg_conviction?.toFixed(0) || 0}%
          </span>
        </div>
      </div>
      
      <div className="flex flex-wrap gap-1">
        {cycle.coins_traded?.slice(0, 5).map(coin => (
          <span key={coin} className="px-2 py-0.5 text-xs bg-surface-2 rounded text-text-secondary">
            {coin}
          </span>
        ))}
        {(cycle.coins_traded?.length || 0) > 5 && (
          <span className="px-2 py-0.5 text-xs bg-surface-2 rounded text-text-muted">
            +{cycle.coins_traded.length - 5} more
          </span>
        )}
      </div>
    </motion.div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════════

export default function Dashboard() {
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState<TraderStatus | null>(null)
  const [predictions, setPredictions] = useState<Prediction[]>([])
  const [cycles, setCycles] = useState<Cycle[]>([])
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())
  const [error, setError] = useState<string | null>(null)
  const [equityData, setEquityData] = useState<EquityPoint[]>([])
  const [wsConnected, setWsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  // WebSocket connection for real-time equity updates
  useEffect(() => {
    const connectWebSocket = () => {
      try {
        const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws/equity'
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws
        
        ws.onopen = () => {
          console.log('Equity WebSocket connected')
          setWsConnected(true)
        }
        
        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data)
            
            if (message.type === 'equity_update' && message.data) {
              setEquityData(prev => {
                const newData = [...prev, message.data]
                // Keep last 120 seconds (2 minutes)
                return newData.slice(-120)
              })
            }
            
            // Handle paper trades reset - clear equity data
            if (message.type === 'paper_trades_reset') {
              console.log('Paper trades reset received - clearing equity data')
              setEquityData([])
            }
          } catch (e) {
            console.error('Failed to parse WebSocket message:', e)
          }
        }
        
        ws.onclose = () => {
          console.log('Equity WebSocket disconnected')
          setWsConnected(false)
          // Reconnect after 3 seconds
          setTimeout(connectWebSocket, 3000)
        }
        
        ws.onerror = (error) => {
          console.error('Equity WebSocket error:', error)
          setWsConnected(false)
        }
      } catch (e) {
        console.error('Failed to connect WebSocket:', e)
        setTimeout(connectWebSocket, 5000)
      }
    }
    
    connectWebSocket()
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  // Fetch data
  useEffect(() => {
    async function fetchData() {
      try {
        const [statusData, predictionsData, cyclesData] = await Promise.all([
          api.getTraderStatus().catch(e => { console.error('Status error:', e); return null }),
          api.getPredictions(200).catch(e => { console.error('Predictions error:', e); return [] }),  // Increased to show all 25 coins
          api.getPredictionCycles(10).catch(e => { console.error('Cycles error:', e); return [] }),
        ])

        if (statusData) setStatus(statusData)
        if (predictionsData) setPredictions(predictionsData)
        // Sort cycles by cycle_number descending (highest first)
        if (cyclesData) {
          const sorted = [...cyclesData].sort((a, b) => b.cycle_number - a.cycle_number)
          setCycles(sorted)
        }
        
        setLastRefresh(new Date())
        setError(null)
      } catch (e) {
        console.error('Failed to fetch data:', e)
        setError('Failed to connect to backend')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 10000) // Refresh every 10s
    return () => clearInterval(interval)
  }, [])

  // Calculate metrics - use total equity (includes unrealized PnL), not just cash
  const totalEquity = status?.equity?.total_equity || status?.executor?.capital || 100000
  const startingCapital = status?.executor?.starting_capital || 100000
  const pnl = totalEquity - startingCapital
  const pnlPercent = ((pnl / startingCapital) * 100)

  // Get latest cycle's predictions
  const latestCycle = cycles[0]
  const latestPredictions = predictions.filter(p => p.cycle_id === latestCycle?.id)

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-void">
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="text-center"
        >
          <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-gradient-to-br from-accent-cyan to-accent-emerald flex items-center justify-center shadow-glow-cyan-intense">
            <Zap className="w-10 h-10 text-void animate-pulse" />
          </div>
          <h1 className="text-xl font-semibold gradient-text mb-2">Simple Prediction Trader</h1>
          <p className="text-text-muted text-sm">Loading predictions...</p>
        </motion.div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-void">
      <Sidebar isConnected={status?.running || false} />

      <main className="flex-1 ml-[280px] p-6 lg:p-8">
        {/* Header */}
        <header className="flex items-center justify-between mb-8">
          <div>
            <motion.h1 
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="text-2xl font-semibold text-text-primary tracking-tight flex items-center gap-3"
            >
              🎯 Prediction Trader
              <span className={clsx(
                'px-2 py-0.5 text-xs font-bold rounded border',
                status?.running 
                  ? 'bg-accent-emerald/20 text-accent-emerald border-accent-emerald/40'
                  : 'bg-accent-amber/20 text-accent-amber border-accent-amber/40'
              )}>
                {status?.running ? 'RUNNING' : 'IDLE'}
              </span>
              <span className="px-2 py-0.5 text-xs font-bold bg-purple-500/20 text-purple-400 rounded border border-purple-500/40">
                {status?.mode?.toUpperCase() || 'PAPER'}
              </span>
            </motion.h1>
            <p className="text-xs text-text-muted mt-1 flex items-center gap-2">
              <Clock className="w-3 h-3" />
              Last updated: {lastRefresh.toLocaleTimeString()} • 
              {status?.cycle_interval_seconds ? ` ${Math.round(status.cycle_interval_seconds / 60)}min cycles` : ' 15min cycles'}
              <span className={clsx(
                'inline-flex items-center gap-1 ml-2',
                wsConnected ? 'text-accent-emerald' : 'text-accent-amber'
              )}>
                <span className={clsx(
                  'w-1.5 h-1.5 rounded-full',
                  wsConnected ? 'bg-accent-emerald animate-pulse' : 'bg-accent-amber'
                )} />
                {wsConnected ? 'Live' : 'Connecting...'}
              </span>
            </p>
          </div>

          <button
            onClick={() => window.location.reload()}
            className="btn-ghost p-2"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </header>

        {error && (
          <div className="mb-6 p-4 bg-accent-red/10 border border-accent-red/30 rounded-lg text-accent-red">
            {error}
          </div>
        )}

        {/* Hero Metrics */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className={clsx(
              'glass-card p-3',
              pnl >= 0 ? 'border-glow-emerald' : 'border-glow-red'
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-label">Portfolio</span>
              <DollarSign className="w-5 h-5 text-accent-cyan" />
            </div>
            <div className="text-2xl font-mono font-semibold text-text-primary">
              ${totalEquity.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </div>
            <div className={clsx(
              'text-xs font-mono',
              pnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'
            )}>
              {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)} ({pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%)
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="glass-card p-3"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-label">Open Positions</span>
              <Activity className="w-5 h-5 text-accent-amber" />
            </div>
            <div className="text-2xl font-mono font-semibold text-text-primary">
              {status?.executor?.open_positions || 0}
            </div>
            <div className="text-xs text-text-muted">
              {status?.top_coins_count || 10} coins per cycle
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card p-3"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-label">Total Cycles</span>
              <BarChart3 className="w-5 h-5 text-purple-400" />
            </div>
            <div className="text-2xl font-mono font-semibold text-text-primary">
              {cycles.length || status?.executor?.total_cycles || 0}
            </div>
            <div className="text-xs text-text-muted">
              {status?.executor?.total_trades || 0} total trades
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="glass-card p-3"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-label">Trading Costs</span>
              <Wallet className="w-5 h-5 text-accent-red" />
            </div>
            <div className="text-2xl font-mono font-semibold text-accent-red">
              ${(status?.executor?.total_trading_costs || 0).toFixed(2)}
            </div>
            <div className="text-xs text-text-muted">
              Fees: ${(status?.executor?.total_fees_paid || 0).toFixed(2)}
            </div>
          </motion.div>
        </div>

        {/* Real-Time Equity Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="mb-6"
        >
          <EquityChart 
            data={equityData} 
            startingCapital={status?.executor?.starting_capital || 100000} 
          />
        </motion.div>

        {/* Main Grid */}
        <div className="grid grid-cols-12 gap-4">
          {/* Left Column - Latest Predictions */}
          <div className="col-span-12 xl:col-span-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-card p-4"
            >
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-lg font-semibold text-text-primary flex items-center gap-2">
                  <Zap className="w-5 h-5 text-accent-cyan" />
                  Latest Predictions
                  {latestCycle && (
                    <span className="text-sm text-text-muted font-normal">
                      (Cycle #{latestCycle.cycle_number})
                    </span>
                  )}
                </h2>
                <span className="text-xs text-text-muted">
                  {latestPredictions.length || predictions.length} predictions
                </span>
              </div>

              {(latestPredictions.length > 0 || predictions.length > 0) ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {(latestPredictions.length > 0 ? latestPredictions : predictions).map((pred, idx) => (
                    <motion.div
                      key={pred.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.05 }}
                    >
                      <PredictionCard prediction={pred} />
                    </motion.div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 text-text-muted">
                  <Zap className="w-12 h-12 mx-auto mb-4 opacity-20" />
                  <p>No predictions yet. Waiting for first cycle...</p>
                </div>
              )}
            </motion.div>
          </div>

          {/* Right Column - Cycles */}
          <div className="col-span-12 xl:col-span-4 space-y-4">
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              className="glass-card p-4"
            >
              <h2 className="text-lg font-semibold text-text-primary mb-3 flex items-center gap-2">
                <Clock className="w-5 h-5 text-accent-amber" />
                Recent Cycles
              </h2>

              {cycles.length > 0 ? (
                <div className="space-y-3">
                  {cycles.slice(0, 5).map((cycle, idx) => (
                    <motion.div
                      key={cycle.id}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.1 }}
                    >
                      <CycleCard cycle={cycle} />
                    </motion.div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-text-muted">
                  <Clock className="w-8 h-8 mx-auto mb-2 opacity-20" />
                  <p className="text-sm">No cycles yet</p>
                </div>
              )}
            </motion.div>

            {/* Open Positions */}
            {(status?.executor?.positions?.length || 0) > 0 && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2 }}
                className="glass-card p-4"
              >
                <h2 className="text-lg font-semibold text-text-primary mb-3 flex items-center gap-2">
                  <Activity className="w-5 h-5 text-accent-emerald" />
                  Open Positions
                </h2>

                <div className="space-y-2">
                  {status?.executor?.positions?.map((pos: any) => (
                    <div key={pos.position_id} className="flex items-center justify-between p-3 bg-surface-2 rounded-lg">
                      <div className="flex items-center gap-2">
                        <span className={clsx(
                          'w-2 h-2 rounded-full',
                          pos.direction === 'LONG' ? 'bg-accent-emerald' : 'bg-accent-red'
                        )} />
                        <span className="font-mono text-sm">{pos.symbol}</span>
                      </div>
                      <div className="text-right">
                        <div className="text-xs text-text-muted">{pos.leverage?.toFixed(1)}x</div>
                        <div className="text-xs font-mono">${pos.size_usdt?.toFixed(0)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

            {/* System Info */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.3 }}
              className="glass-card p-4"
            >
              <h2 className="text-lg font-semibold text-text-primary mb-3">System Info</h2>
              
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">Mode</span>
                  <span className="badge badge-paper">{status?.mode?.toUpperCase() || 'PAPER'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">Status</span>
                  <span className={clsx(
                    'text-xs font-medium',
                    status?.running ? 'text-accent-emerald' : 'text-accent-amber'
                  )}>
                    {status?.running ? '● Running' : '○ Idle'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">Cycle Interval</span>
                  <span className="text-xs font-mono text-text-muted">
                    {status?.cycle_interval_seconds 
                      ? `${Math.round(status.cycle_interval_seconds / 60)}m`
                      : '15m'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">Coins per Cycle</span>
                  <span className="text-xs font-mono text-text-muted">
                    {status?.top_coins_count || 10}
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
