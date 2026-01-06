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
  Download,
  Brain,
  Loader2,
  Play,
  AlertTriangle,
  Shield,
  ArrowUpRight,
  ArrowDownRight,
  BookOpen,
  Plus,
  X,
  Check,
  ChevronRight,
  Radio,
  WifiOff,
} from 'lucide-react'
import { clsx } from 'clsx'

import { Sidebar } from '@/components/Sidebar'
import { MobileHeader } from '@/components/MobileHeader'
import { MarketStatusBanner, type MarketStatus } from '@/components/MarketStatusBanner'
import { api } from '@/lib/api'

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface PortfolioPosition {
  id: string
  symbol: string
  direction: string
  entry_price: number
  current_price: number
  quantity: number
  size_usd: number
  conviction: number
  unrealized_pnl: number
  pnl_percent: number  // Backend sends pnl_percent, not unrealized_pnl_pct
  entry_time: string   // Backend sends entry_time, not opened_at
  reason?: string      // Optional - backend may send reasoning instead
  reasoning?: string | null  // Backend may send reasoning instead of reason
  sector?: string | null
  exchange?: string | null
}

interface PortfolioStatistics {
  starting_capital: number
  current_capital: number
  total_equity: number
  unrealized_pnl: number
  realized_pnl: number
  total_pnl: number
  open_positions: number
  max_positions: number
  available_slots: number
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  total_fees: number
  transactions: {
    total: number
    open: number
    close: number
    extend: number
    reduce: number
  }
  deployment: {
    total_deployed: number
    deployment_ratio: number
    deployment_percent: number
    below_minimum: boolean
    capital_to_deploy: number
  }
}

interface PortfolioManagerStatus {
  running: boolean
  phase: string
  cycle_count: number
  cycle_interval_seconds: number
  mode: string
  portfolio: {
    positions: PortfolioPosition[]
    statistics: PortfolioStatistics
  }
  logbook: {
    total_entries: number
    total_cycles: number
    total_tokens_used: number
    total_positions_closed: number
    total_positions_opened: number
  }
  db_restored: boolean
}

interface LogEntry {
  id: string
  timestamp: string
  cycle_number: number
  analysis_text: string
  market_summary: string
  positions_closed: Array<{ symbol: string; reason: string; pnl: number }>
  positions_opened: Array<{ symbol: string; direction: string; conviction: number; reason: string }>
  positions_extended?: Array<{ symbol: string; scale_percent: number; reason: string }>
  positions_reduced?: Array<{ symbol: string; scale_percent: number; reason: string }>
  positions_kept: string[]
  stocks_analyzed: number
  tokens_used: number
  total_equity: number
  unrealized_pnl: number
}

interface EquityPoint {
  timestamp: string
  total_equity: number
  unrealized_pnl: number
  cash: number
}

interface LivePositionData {
  symbol: string
  direction: string
  size_usd: number
  unrealized_pnl: number
  pnl_percent: number  // Backend sends pnl_percent
  entry_price: number
  current_price: number
}

interface LiveEquityData {
  timestamp: string
  total_equity: number
  cash: number
  positions_value: number
  unrealized_pnl: number
  position_details: LivePositionData[]
}

// ═══════════════════════════════════════════════════════════════════════════════
// UTILITY FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════════

function formatCurrency(value: number, showSign = false): string {
  // Handle NaN, undefined, or null values
  if (value == null || isNaN(value)) {
    return '$0.00'
  }
  
  const formatted = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Math.abs(value))
  
  if (showSign && value !== 0) {
    return value >= 0 ? `+${formatted}` : `-${formatted}`
  }
  return value < 0 ? `-${formatted}` : formatted
}

function formatPercent(value: number, showSign = false): string {
  // Handle NaN, undefined, or null values
  if (value == null || isNaN(value)) {
    return '0.00%'
  }
  
  const formatted = `${Math.abs(value).toFixed(2)}%`
  if (showSign && value !== 0) {
    return value >= 0 ? `+${formatted}` : `-${formatted}`
  }
  return value < 0 ? `-${formatted}` : formatted
}

function formatTimeAgo(timestamp: string | null | undefined): string {
  if (!timestamp) return 'Unknown'
  
  const date = new Date(timestamp)
  
  // Check for invalid date
  if (isNaN(date.getTime())) return 'Unknown'
  
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  
  return date.toLocaleDateString()
}


// ═══════════════════════════════════════════════════════════════════════════════
// ANIMATED VALUE COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

function AnimatedValue({ 
  value, 
  format, 
  className,
  showSign = false 
}: { 
  value: number
  format: 'currency' | 'percent' | 'number'
  className?: string
  showSign?: boolean
}) {
  const [displayValue, setDisplayValue] = useState(value)
  const [isChanging, setIsChanging] = useState(false)
  const prevValue = useRef(value)
  
  useEffect(() => {
    if (Math.abs(value - prevValue.current) > 0.001) {
      setIsChanging(true)
      setDisplayValue(value)
      prevValue.current = value
      
      const timeout = setTimeout(() => setIsChanging(false), 500)
      return () => clearTimeout(timeout)
    }
  }, [value])
  
  let formatted: string
  if (format === 'currency') {
    formatted = formatCurrency(displayValue, showSign)
  } else if (format === 'percent') {
    formatted = formatPercent(displayValue, showSign)
  } else {
    formatted = showSign && displayValue > 0 
      ? `+${displayValue.toLocaleString()}` 
      : displayValue.toLocaleString()
  }
  
  return (
    <span className={clsx(
      className,
      'transition-all duration-300',
      isChanging && 'animate-pulse scale-105'
    )}>
      {formatted}
    </span>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// LIVE INDICATOR COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

function LiveIndicator({ 
  connected, 
  lastUpdate 
}: { 
  connected: boolean
  lastUpdate: Date | null 
}) {
  const [secondsAgo, setSecondsAgo] = useState(0)
  
  useEffect(() => {
    const interval = setInterval(() => {
      if (lastUpdate) {
        const diff = Math.floor((Date.now() - lastUpdate.getTime()) / 1000)
        setSecondsAgo(diff)
      }
    }, 1000)
    return () => clearInterval(interval)
  }, [lastUpdate])
  
  return (
    <div className={clsx(
      'flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-medium',
      connected 
        ? 'bg-accent-emerald/10 border-accent-emerald/30 text-accent-emerald'
        : 'bg-accent-red/10 border-accent-red/30 text-accent-red'
    )}>
      {connected ? (
        <>
          <Radio className="w-3 h-3 animate-pulse" />
          <span>LIVE</span>
          {lastUpdate && secondsAgo < 60 && (
            <span className="text-text-muted">
              {secondsAgo === 0 ? 'now' : `${secondsAgo}s ago`}
            </span>
          )}
        </>
      ) : (
        <>
          <WifiOff className="w-3 h-3" />
          <span>DISCONNECTED</span>
        </>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// POSITION CARD COMPONENT (with live updates)
// ═══════════════════════════════════════════════════════════════════════════════

function PositionCard({ 
  position,
  liveData
}: { 
  position: PortfolioPosition
  liveData?: LivePositionData
}) {
  const isLong = position.direction === 'LONG'
  const stockSymbol = position.symbol || 'UNKNOWN'
  
  // Use live data if available, otherwise fall back to position data
  const currentPrice = liveData?.current_price ?? position.current_price ?? 0
  const unrealizedPnl = liveData?.unrealized_pnl ?? position.unrealized_pnl ?? 0
  const unrealizedPnlPct = liveData?.pnl_percent ?? position.pnl_percent ?? 0
  const isProfitable = unrealizedPnl >= 0
  
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={clsx(
        'glass-card p-4 border-l-4 transition-all hover:scale-[1.01]',
        isProfitable ? 'border-l-accent-emerald' : 'border-l-accent-red'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={clsx(
            'w-10 h-10 rounded-lg flex items-center justify-center',
            isLong ? 'bg-accent-emerald/20' : 'bg-accent-red/20'
          )}>
            {isLong ? (
              <TrendingUp className="w-5 h-5 text-accent-emerald" />
            ) : (
              <TrendingDown className="w-5 h-5 text-accent-red" />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold text-text-primary">{stockSymbol}</span>
              <span className={clsx(
                'px-2 py-0.5 text-xs font-bold rounded',
                isLong 
                  ? 'bg-accent-emerald/20 text-accent-emerald' 
                  : 'bg-accent-red/20 text-accent-red'
              )}>
                {position.direction}
              </span>
              {position.sector && (
                <span className="text-xs text-accent-cyan font-mono">{position.sector}</span>
              )}
            </div>
            <span className="text-xs text-text-muted flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatTimeAgo(position.entry_time)}
              {position.exchange && <span className="ml-1">• {position.exchange}</span>}
            </span>
          </div>
        </div>
        
        {/* PnL - Animated */}
        <div className="text-right">
          <AnimatedValue
            value={unrealizedPnl}
            format="currency"
            showSign
            className={clsx(
              'text-xl font-mono font-bold block',
              isProfitable ? 'text-accent-emerald' : 'text-accent-red'
            )}
          />
          <AnimatedValue
            value={unrealizedPnlPct}
            format="percent"
            showSign
            className={clsx(
              'text-sm font-mono',
              isProfitable ? 'text-accent-emerald' : 'text-accent-red'
            )}
          />
        </div>
      </div>
      
      {/* Price Info */}
      <div className="grid grid-cols-3 gap-3 mb-3">
        <div>
          <span className="text-xs text-text-muted block">Entry</span>
          <span className="text-sm font-mono text-text-primary">
            ${position.entry_price.toLocaleString()}
          </span>
        </div>
        <div>
          <span className="text-xs text-text-muted block">Current</span>
          <AnimatedValue
            value={currentPrice}
            format="number"
            className={clsx(
              'text-sm font-mono',
              isProfitable ? 'text-accent-emerald' : 'text-accent-red'
            )}
          />
        </div>
        <div>
          <span className="text-xs text-text-muted block">Size</span>
          <span className="text-sm font-mono text-text-primary">
            ${position.size_usd.toFixed(0)}
          </span>
        </div>
      </div>
      
      {/* Conviction & Reason */}
      <div className="pt-3 border-t border-glass-border">
        <div className="flex items-center gap-2 mb-2">
          <Target className="w-3 h-3 text-accent-cyan" />
          <span className="text-xs text-text-muted">Conviction: </span>
          <span className="text-xs font-bold text-accent-cyan">{position.conviction}%</span>
        </div>
        <p className="text-xs text-text-secondary italic line-clamp-2">
          "{position.reasoning || position.reason || ''}"
        </p>
      </div>
    </motion.div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// ACTIVITY FEED COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

function ActivityItem({ 
  action, 
  symbol, 
  details, 
  timestamp 
}: { 
  action: 'opened' | 'closed' | 'extended' | 'reduced' | 'kept'
  symbol: string
  details: string
  timestamp: string
}) {
  const actionConfig = {
    opened: { icon: Plus, color: 'text-accent-emerald', bg: 'bg-accent-emerald/20', label: 'Opened' },
    closed: { icon: X, color: 'text-accent-red', bg: 'bg-accent-red/20', label: 'Closed' },
    extended: { icon: ArrowUpRight, color: 'text-accent-cyan', bg: 'bg-accent-cyan/20', label: 'Extended' },
    reduced: { icon: ArrowDownRight, color: 'text-accent-amber', bg: 'bg-accent-amber/20', label: 'Reduced' },
    kept: { icon: Check, color: 'text-text-muted', bg: 'bg-surface-2', label: 'Kept' },
  }
  
  const config = actionConfig[action]
  const Icon = config.icon
  
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className="flex items-start gap-3 py-3 border-b border-glass-border/50 last:border-0"
    >
      <div className={clsx('w-8 h-8 rounded-lg flex items-center justify-center', config.bg)}>
        <Icon className={clsx('w-4 h-4', config.color)} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-text-primary">{symbol?.replace('USDT', '') || 'UNKNOWN'}</span>
          <span className={clsx('text-xs px-1.5 py-0.5 rounded', config.bg, config.color)}>
            {config.label}
          </span>
        </div>
        <p className="text-xs text-text-secondary truncate">{details}</p>
      </div>
      <span className="text-xs text-text-muted whitespace-nowrap">{formatTimeAgo(timestamp)}</span>
    </motion.div>
  )
}

function ActivityFeed({ entries }: { entries: LogEntry[] }) {
  const activities: Array<{
    action: 'opened' | 'closed' | 'extended' | 'reduced' | 'kept'
    symbol: string
    details: string
    timestamp: string
  }> = []
  
  entries.slice(0, 5).forEach(entry => {
    entry.positions_opened?.forEach(pos => {
      if (!pos.symbol) return
      activities.push({
        action: 'opened',
        symbol: pos.symbol,
        details: `${pos.direction} at ${pos.conviction}% conviction`,
        timestamp: entry.timestamp,
      })
    })
    entry.positions_closed?.forEach(pos => {
      if (!pos.symbol) return
      activities.push({
        action: 'closed',
        symbol: pos.symbol,
        details: `${formatCurrency(pos.pnl, true)} - ${pos.reason}`,
        timestamp: entry.timestamp,
      })
    })
    entry.positions_extended?.forEach(pos => {
      if (!pos.symbol) return
      activities.push({
        action: 'extended',
        symbol: pos.symbol,
        details: `+${pos.scale_percent}% - ${pos.reason}`,
        timestamp: entry.timestamp,
      })
    })
    entry.positions_reduced?.forEach(pos => {
      if (!pos.symbol) return
      activities.push({
        action: 'reduced',
        symbol: pos.symbol,
        details: `-${pos.scale_percent}% - ${pos.reason}`,
        timestamp: entry.timestamp,
      })
    })
  })
  
  activities.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
  const recentActivities = activities.slice(0, 10)
  
  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
          <Activity className="w-4 h-4 text-accent-cyan" />
          Recent Activity
        </h3>
        <a href="/logbook" className="text-xs text-accent-cyan hover:underline flex items-center gap-1">
          View All <ChevronRight className="w-3 h-3" />
        </a>
      </div>
      
      {recentActivities.length > 0 ? (
        <div className="space-y-0">
          {recentActivities.map((activity, idx) => (
            <ActivityItem key={idx} {...activity} />
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-text-muted">
          <Activity className="w-8 h-8 mx-auto mb-2 opacity-20" />
          <p className="text-sm">No recent activity</p>
        </div>
      )}
    </div>
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
    
    const dpr = window.devicePixelRatio || 1
    const rect = canvas.getBoundingClientRect()
    canvas.width = rect.width * dpr
    canvas.height = rect.height * dpr
    ctx.scale(dpr, dpr)
    
    ctx.clearRect(0, 0, rect.width, rect.height)
    
    const values = data.map(d => d.total_equity)
    const minVal = Math.min(...values, startingCapital * 0.95)
    const maxVal = Math.max(...values, startingCapital * 1.05)
    const range = maxVal - minVal || 1
    
    const padding = { top: 20, right: 10, bottom: 30, left: 50 }
    const chartWidth = rect.width - padding.left - padding.right
    const chartHeight = rect.height - padding.top - padding.bottom
    
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)'
    ctx.lineWidth = 1
    for (let i = 0; i <= 4; i++) {
      const y = padding.top + (chartHeight * i / 4)
      ctx.beginPath()
      ctx.moveTo(padding.left, y)
      ctx.lineTo(rect.width - padding.right, y)
      ctx.stroke()
      
      const val = maxVal - (range * i / 4)
      ctx.fillStyle = 'rgba(255, 255, 255, 0.4)'
      ctx.font = '10px monospace'
      ctx.textAlign = 'right'
      ctx.fillText(`$${(val / 1000).toFixed(1)}k`, padding.left - 5, y + 3)
    }
    
    const baselineY = padding.top + ((maxVal - startingCapital) / range) * chartHeight
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)'
    ctx.setLineDash([4, 4])
    ctx.beginPath()
    ctx.moveTo(padding.left, baselineY)
    ctx.lineTo(rect.width - padding.right, baselineY)
    ctx.stroke()
    ctx.setLineDash([])
    
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
    
    const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartHeight)
    gradient.addColorStop(0, isProfit ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)')
    gradient.addColorStop(1, 'rgba(0, 0, 0, 0)')
    
    ctx.lineTo(padding.left + chartWidth, padding.top + chartHeight)
    ctx.lineTo(padding.left, padding.top + chartHeight)
    ctx.closePath()
    ctx.fillStyle = gradient
    ctx.fill()
    
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
          Equity History
          <span className="text-xs text-text-muted font-normal">({data.length} points)</span>
        </h3>
        <AnimatedValue
          value={pnl}
          format="currency"
          showSign
          className={clsx(
            'text-sm font-mono font-bold',
            pnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'
          )}
        />
      </div>
      <div className="relative h-48">
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
// MAIN DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════════

export default function Dashboard() {
  const [loading, setLoading] = useState(true)
  const [pmStatus, setPmStatus] = useState<PortfolioManagerStatus | null>(null)
  const [logEntries, setLogEntries] = useState<LogEntry[]>([])
  const [error, setError] = useState<string | null>(null)
  const [equityData, setEquityData] = useState<EquityPoint[]>([])
  const [wsConnected, setWsConnected] = useState(false)
  const [lastWsUpdate, setLastWsUpdate] = useState<Date | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const [triggeringCycle, setTriggeringCycle] = useState(false)
  
  // Mobile sidebar state
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  
  // Live equity data from WebSocket
  const [liveEquity, setLiveEquity] = useState<LiveEquityData | null>(null)
  
  // Phase tracking state
  const [currentPhase, setCurrentPhase] = useState<'idle' | 'fetching' | 'analyzing' | 'trading'>('idle')
  const [nextCycleAt, setNextCycleAt] = useState<number | null>(null)
  const [countdown, setCountdown] = useState<string>('')
  const [progressCurrent, setProgressCurrent] = useState<number>(0)
  const [progressTotal, setProgressTotal] = useState<number>(0)
  
  // Market status state
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(null)

  // WebSocket connection for real-time equity updates
  useEffect(() => {
    const connectWebSocket = () => {
      try {
        // Build WebSocket URL dynamically from current location or env var
        let wsUrl: string
        if (process.env.NEXT_PUBLIC_WS_URL) {
          // Use configured URL if available
          const wsBase = process.env.NEXT_PUBLIC_WS_URL
          wsUrl = wsBase.endsWith('/equity') ? wsBase : `${wsBase}/equity`
        } else if (typeof window !== 'undefined' && window.location.hostname !== 'localhost') {
          // Derive from current page URL for production
          const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
          wsUrl = `${protocol}//${window.location.host}/ws/equity`
        } else {
          // Local development fallback
          wsUrl = 'ws://localhost:8081/ws/equity'
        }
        console.log('Connecting to WebSocket:', wsUrl)
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
              const data = message.data as LiveEquityData
              setLastWsUpdate(new Date())
              
              // Update live equity state for hero metrics
              setLiveEquity(data)
              
              // Add to chart data
              setEquityData(prev => {
                const newData = [...prev, {
                  timestamp: data.timestamp,
                  total_equity: data.total_equity,
                  unrealized_pnl: data.unrealized_pnl,
                  cash: data.cash,
                }]
                return newData.slice(-120)
              })
            }
            
            if (message.type === 'phase') {
              setCurrentPhase(message.phase)
              if (message.next_cycle_at) {
                setNextCycleAt(message.next_cycle_at)
              }
              if (message.progress_current !== undefined) {
                setProgressCurrent(message.progress_current)
              }
              if (message.progress_total !== undefined) {
                setProgressTotal(message.progress_total)
              }
            }
            
            if (message.type === 'paper_trades_reset') {
              console.log('Paper trades reset received - clearing equity data')
              setEquityData([])
              setLiveEquity(null)
            }
          } catch (e) {
            console.error('Failed to parse WebSocket message:', e)
          }
        }
        
        ws.onclose = () => {
          console.log('Equity WebSocket disconnected')
          setWsConnected(false)
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

  // Countdown timer effect
  useEffect(() => {
    if (currentPhase !== 'idle' || !nextCycleAt) {
      setCountdown('')
      return
    }
    
    const updateCountdown = () => {
      const now = Date.now() / 1000
      const remaining = Math.max(0, nextCycleAt - now)
      
      if (remaining <= 0) {
        setCountdown('')
        return
      }
      
      const minutes = Math.floor(remaining / 60)
      const seconds = Math.floor(remaining % 60)
      setCountdown(`${minutes}:${seconds.toString().padStart(2, '0')}`)
    }
    
    updateCountdown()
    const interval = setInterval(updateCountdown, 1000)
    
    return () => clearInterval(interval)
  }, [currentPhase, nextCycleAt])

  // Fetch data from API (less frequently - WebSocket handles real-time)
  useEffect(() => {
    async function fetchData() {
      try {
        const [statusData, logData] = await Promise.all([
          api.getPortfolioManagerStatus().catch(e => { console.error('PM status error:', e); return null }),
          fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081'}/api/logbook?limit=10`)
            .then(r => r.ok ? r.json() : [])
            .catch(e => { console.error('Logbook error:', e); return [] }),
        ])

        if (statusData) {
          setPmStatus(statusData)
          if (statusData.phase) {
            setCurrentPhase(statusData.phase as any)
          }
        }
        if (logData) setLogEntries(logData)
        
        setError(null)
      } catch (e) {
        console.error('Failed to fetch data:', e)
        setError('Failed to connect to backend')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    // Poll less frequently since WebSocket provides real-time data
    const interval = setInterval(fetchData, 15000)
    return () => clearInterval(interval)
  }, [])

  // Calculate metrics - prefer live data over polled data
  const stats = pmStatus?.portfolio?.statistics
  const positions = pmStatus?.portfolio?.positions || []
  
  // Use live equity data if available, otherwise fall back to API data
  const totalEquity = liveEquity?.total_equity ?? stats?.total_equity ?? 0
  const unrealizedPnl = liveEquity?.unrealized_pnl ?? stats?.unrealized_pnl ?? 0
  const startingCapital = stats?.starting_capital || 0
  // Total PnL = Total Equity - Starting Capital (correct accounting equation)
  const totalPnl = totalEquity - startingCapital
  const pnlPercent = startingCapital > 0 ? ((totalPnl / startingCapital) * 100) : 0
  
  // Build a map of live position data for quick lookup
  const livePositionMap = new Map<string, LivePositionData>()
  if (liveEquity?.position_details) {
    liveEquity.position_details.forEach(pd => {
      livePositionMap.set(pd.symbol, pd)
    })
  }

  // Handler for manually triggering a cycle
  const handleTriggerCycle = useCallback(async () => {
    if (triggeringCycle || currentPhase !== 'idle') return
    
    // Check market status before triggering
    if (marketStatus && !marketStatus.trading_allowed) {
      setError(`Cannot run analysis - ${marketStatus.description}`)
      return
    }
    
    setTriggeringCycle(true)
    try {
      await api.triggerCycle()
    } catch (e: any) {
      console.error('Failed to trigger cycle:', e)
      // Parse error message if it's a market closed error
      const errorMessage = e?.message || 'Failed to trigger cycle'
      if (errorMessage.toLowerCase().includes('market') || errorMessage.toLowerCase().includes('closed')) {
        setError('Cannot run analysis - Market is closed')
      } else {
        setError(errorMessage)
      }
    } finally {
      setTriggeringCycle(false)
    }
  }, [triggeringCycle, currentPhase, marketStatus])
  
  // Market status change handler
  const handleMarketStatusChange = useCallback((status: MarketStatus) => {
    setMarketStatus(status)
  }, [])

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
            <Brain className="w-10 h-10 text-void animate-pulse" />
          </div>
          <h1 className="text-xl font-semibold gradient-text mb-2">Stock Portfolio Manager</h1>
          <p className="text-text-muted text-sm">Loading portfolio...</p>
        </motion.div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-void">
      <Sidebar 
        isConnected={pmStatus?.running || wsConnected} 
        mobileOpen={mobileMenuOpen}
        onMobileClose={() => setMobileMenuOpen(false)}
      />

      <main className="flex-1 md:ml-[280px] min-w-0">
        {/* Mobile Header */}
        <MobileHeader 
          onMenuClick={() => setMobileMenuOpen(true)}
          isConnected={wsConnected}
          title="Stock Portfolio"
        />

        <div className="p-4 md:p-6 lg:p-8">
        {/* Header - Desktop version */}
        <header className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
          <div>
            <motion.h1 
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="text-2xl font-semibold text-text-primary tracking-tight flex items-center gap-3"
            >
              <Brain className="w-7 h-7 text-accent-cyan" />
              Stock Portfolio Manager
              {/* Dynamic Phase Indicator */}
              <AnimatePresence mode="wait">
                <motion.span 
                  key={currentPhase}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  transition={{ duration: 0.2 }}
                  className={clsx(
                    'px-2 py-0.5 text-xs font-bold rounded border flex items-center gap-1.5',
                    currentPhase === 'idle' && 'bg-slate-500/20 text-slate-400 border-slate-500/40',
                    currentPhase === 'fetching' && 'bg-cyan-500/20 text-cyan-400 border-cyan-500/40',
                    currentPhase === 'analyzing' && 'bg-purple-500/20 text-purple-400 border-purple-500/40',
                    currentPhase === 'trading' && 'bg-accent-emerald/20 text-accent-emerald border-accent-emerald/40',
                  )}
                >
                  {currentPhase === 'idle' && (
                    <>
                      <Clock className="w-3 h-3" />
                      {countdown ? `NEXT: ${countdown}` : 'IDLE'}
                    </>
                  )}
                  {currentPhase === 'fetching' && (
                    <>
                      <Download className="w-3 h-3 animate-bounce" />
                      FETCHING DATA
                    </>
                  )}
                  {currentPhase === 'analyzing' && (
                    <>
                      <Brain className="w-3 h-3 animate-pulse" />
                      {progressTotal > 0 ? `ANALYZING ${progressCurrent}/${progressTotal}` : 'GROK ANALYZING'}
                    </>
                  )}
                  {currentPhase === 'trading' && (
                    <>
                      <Zap className="w-3 h-3 animate-pulse" />
                      TRADING
                    </>
                  )}
                </motion.span>
              </AnimatePresence>
              <span className="px-2 py-0.5 text-xs font-bold bg-purple-500/20 text-purple-400 rounded border border-purple-500/40">
                {pmStatus?.mode?.toUpperCase() || 'PAPER'}
              </span>
            </motion.h1>
            <p className="text-xs text-text-muted mt-1 flex items-center gap-2">
              <Clock className="w-3 h-3" />
              {pmStatus?.cycle_interval_seconds ? `${Math.round(pmStatus.cycle_interval_seconds / 60)}min cycles` : '10min cycles'}
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* Live Indicator */}
            <LiveIndicator connected={wsConnected} lastUpdate={lastWsUpdate} />
            
            <button
              onClick={handleTriggerCycle}
              disabled={triggeringCycle || currentPhase !== 'idle' || Boolean(marketStatus && !marketStatus.trading_allowed)}
              title={marketStatus && !marketStatus.trading_allowed ? `Market is ${marketStatus.status.toLowerCase()}` : undefined}
              className={clsx(
                'flex items-center gap-2 px-3 py-2 rounded-lg font-medium text-sm transition-all',
                currentPhase === 'idle' && !triggeringCycle && (!marketStatus || marketStatus.trading_allowed)
                  ? 'bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/40 hover:bg-accent-emerald/30'
                  : marketStatus && !marketStatus.trading_allowed
                    ? 'bg-slate-500/10 text-slate-400 border border-slate-500/30 cursor-not-allowed'
                    : 'bg-surface-2 text-text-muted border border-surface-3 cursor-not-allowed'
              )}
            >
              {triggeringCycle ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : marketStatus && !marketStatus.trading_allowed ? (
                <Clock className="w-4 h-4" />
              ) : (
                <Play className="w-4 h-4" />
              )}
              {marketStatus && !marketStatus.trading_allowed ? 'Market Closed' : 'Run Analysis'}
            </button>
            <button
              onClick={() => window.location.reload()}
              className="btn-ghost p-2"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </header>

        {/* Market Status Banner */}
        <MarketStatusBanner 
          className="mb-6" 
          onStatusChange={handleMarketStatusChange}
        />

        {error && (
          <div className="mb-6 p-4 bg-accent-red/10 border border-accent-red/30 rounded-lg text-accent-red flex items-center justify-between">
            <span>{error}</span>
            <button 
              onClick={() => setError(null)}
              className="text-accent-red/70 hover:text-accent-red"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Hero Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className={clsx(
              'glass-card p-4',
              totalPnl >= 0 ? 'border-glow-emerald' : 'border-glow-red'
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-label">Total Equity</span>
              <DollarSign className="w-5 h-5 text-accent-cyan" />
            </div>
            <AnimatedValue
              value={totalEquity}
              format="currency"
              className="text-2xl font-mono font-semibold text-text-primary block"
            />
            <AnimatedValue
              value={totalPnl}
              format="currency"
              showSign
              className={clsx(
                'text-xs font-mono',
                totalPnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'
              )}
            />
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="glass-card p-4"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-label">Unrealized PnL</span>
              {unrealizedPnl >= 0 ? (
                <TrendingUp className="w-5 h-5 text-accent-emerald" />
              ) : (
                <TrendingDown className="w-5 h-5 text-accent-red" />
              )}
            </div>
            <AnimatedValue
              value={unrealizedPnl}
              format="currency"
              showSign
              className={clsx(
                'text-2xl font-mono font-semibold block',
                unrealizedPnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'
              )}
            />
            <div className="text-xs text-text-muted">
              Open positions
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card p-4"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-label">Realized PnL</span>
              <Wallet className="w-5 h-5 text-accent-amber" />
            </div>
            <AnimatedValue
              value={stats?.realized_pnl || 0}
              format="currency"
              showSign
              className={clsx(
                'text-2xl font-mono font-semibold block',
                (stats?.realized_pnl || 0) >= 0 ? 'text-accent-emerald' : 'text-accent-red'
              )}
            />
            <div className="text-xs text-text-muted">
              {stats?.winning_trades || 0}W / {stats?.losing_trades || 0}L ({(stats?.win_rate || 0).toFixed(0)}%)
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="glass-card p-4"
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-label">Positions</span>
              <BarChart3 className="w-5 h-5 text-purple-400" />
            </div>
            <div className="text-2xl font-mono font-semibold text-text-primary">
              {stats?.open_positions || positions.length} / {stats?.max_positions || 5}
            </div>
            <div className="text-xs text-text-muted">
              {stats?.available_slots || 0} slots available
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className={clsx(
              'glass-card p-4',
              stats?.deployment?.below_minimum && 'border-glow-red'
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-label">Deployment</span>
              {stats?.deployment?.below_minimum ? (
                <AlertTriangle className="w-5 h-5 text-accent-red" />
              ) : (
                <Target className="w-5 h-5 text-accent-cyan" />
              )}
            </div>
            <div className="text-2xl font-mono font-semibold text-text-primary">
              {(stats?.deployment?.deployment_percent || 0).toFixed(0)}%
            </div>
            <div className="text-xs text-text-muted">
              {stats?.deployment?.below_minimum 
                ? `Deploy $${stats?.deployment?.capital_to_deploy?.toFixed(0)}` 
                : 'On target'}
            </div>
          </motion.div>
        </div>

        {/* Equity Chart */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25 }}
          className="mb-6"
        >
          <EquityChart 
            data={equityData} 
            startingCapital={stats?.starting_capital || 0} 
          />
        </motion.div>

        {/* Main Grid: Positions + Activity */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
          {/* Positions Panel */}
          <div className="xl:col-span-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-card p-4"
            >
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-text-primary flex items-center gap-2">
                  <Shield className="w-5 h-5 text-accent-emerald" />
                  Open Positions
                  {wsConnected && liveEquity?.position_details && (
                    <span className="text-xs text-accent-emerald font-normal flex items-center gap-1">
                      <Radio className="w-3 h-3" /> Live prices
                    </span>
                  )}
                </h2>
                <a href="/positions" className="text-xs text-accent-cyan hover:underline flex items-center gap-1">
                  Details <ChevronRight className="w-3 h-3" />
                </a>
              </div>

              {positions.length > 0 ? (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  {positions.map((position, idx) => (
                    <motion.div
                      key={position.id}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: idx * 0.05 }}
                    >
                      <PositionCard 
                        position={position} 
                        liveData={livePositionMap.get(position.symbol)}
                      />
                    </motion.div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12 text-text-muted">
                  <Shield className="w-12 h-12 mx-auto mb-4 opacity-20" />
                  <p className="font-medium mb-1">No open positions</p>
                  <p className="text-sm text-text-dim">Grok is analyzing stocks for opportunities...</p>
                </div>
              )}
            </motion.div>
          </div>

          {/* Activity Feed */}
          <div className="xl:col-span-4 space-y-4">
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
            >
              <ActivityFeed entries={logEntries} />
            </motion.div>

            {/* Quick Stats */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 }}
              className="glass-card p-4"
            >
              <h3 className="text-sm font-semibold text-text-primary mb-4 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-accent-cyan" />
                Trading Statistics
              </h3>
              
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">Total Trades</span>
                  <span className="font-mono text-text-primary">{stats?.total_trades || 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">Win Rate</span>
                  <span className="font-mono text-accent-emerald">{(stats?.win_rate || 0).toFixed(1)}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">Trading Fees</span>
                  <span className="font-mono text-accent-red">{formatCurrency(stats?.total_fees || 0)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">Analysis Cycles</span>
                  <span className="font-mono text-text-primary">{pmStatus?.logbook?.total_cycles || 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text-secondary">Tokens Used</span>
                  <span className="font-mono text-text-muted">
                    {(pmStatus?.logbook?.total_tokens_used || 0).toLocaleString()}
                  </span>
                </div>
              </div>
            </motion.div>

            {/* Transactions Breakdown */}
            {stats?.transactions && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2 }}
                className="glass-card p-4"
              >
                <h3 className="text-sm font-semibold text-text-primary mb-4 flex items-center gap-2">
                  <Activity className="w-4 h-4 text-accent-cyan" />
                  Transaction Types
                </h3>
                
                <div className="grid grid-cols-4 gap-2">
                  <div className="text-center p-2 bg-accent-emerald/10 rounded-lg">
                    <div className="text-lg font-mono font-bold text-accent-emerald">
                      {stats.transactions.open}
                    </div>
                    <div className="text-xs text-text-muted">Open</div>
                  </div>
                  <div className="text-center p-2 bg-accent-red/10 rounded-lg">
                    <div className="text-lg font-mono font-bold text-accent-red">
                      {stats.transactions.close}
                    </div>
                    <div className="text-xs text-text-muted">Close</div>
                  </div>
                  <div className="text-center p-2 bg-accent-cyan/10 rounded-lg">
                    <div className="text-lg font-mono font-bold text-accent-cyan">
                      {stats.transactions.extend}
                    </div>
                    <div className="text-xs text-text-muted">Extend</div>
                  </div>
                  <div className="text-center p-2 bg-accent-amber/10 rounded-lg">
                    <div className="text-lg font-mono font-bold text-accent-amber">
                      {stats.transactions.reduce}
                    </div>
                    <div className="text-xs text-text-muted">Reduce</div>
                  </div>
                </div>
              </motion.div>
            )}
          </div>
        </div>
        </div>
      </main>
    </div>
  )
}
