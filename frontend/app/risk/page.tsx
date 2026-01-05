'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { 
  AlertTriangle, 
  Shield, 
  TrendingDown,
  Activity,
  CheckCircle,
  XCircle,
  Bell,
  RefreshCw,
  AlertCircle,
  Info,
  Gauge,
  TrendingUp,
  Zap,
} from 'lucide-react'
import { clsx } from 'clsx'

import { Sidebar } from '@/components/Sidebar'
import { api } from '@/lib/api'
import { useWebSocket } from '@/lib/websocket'

interface RiskEvent {
  id: string
  timestamp: string
  event_type: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  trigger_value: number
  threshold_value: number
  action_taken: string
  details: any
  acknowledged: boolean
}

interface MarginPosition {
  coin: string
  side: string
  leverage: number
  entry_price: number
  current_price: number
  liquidation_price: number
  distance_to_liq_pct: number
  price_change_pct: number
  margin_used: number
  status: 'safe' | 'warning' | 'danger' | 'liquidated'
}

interface MarginHealth {
  overall_status: 'safe' | 'warning' | 'danger' | 'critical'
  summary: {
    total_positions: number
    positions_safe: number
    positions_warning: number
    positions_danger: number
    total_margin_used: number
    margin_utilization_pct: number
    closest_to_liq_pct: number | null
  }
  positions: MarginPosition[]
}

function formatCurrency(value: number, showSign = false): string {
  // Handle NaN, undefined, or null values
  if (value == null || isNaN(value)) {
    return '$0.00'
  }
  
  const formatted = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(Math.abs(value))
  
  if (showSign && value !== 0) {
    return value >= 0 ? `+${formatted}` : `-${formatted}`
  }
  return value < 0 ? `-${formatted}` : formatted
}

function formatPercentage(value: number, showSign = false): string {
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

const severityConfig = {
  low: {
    color: 'text-accent-cyan',
    bg: 'bg-accent-cyan/10',
    border: 'border-accent-cyan/30',
    icon: Info,
  },
  medium: {
    color: 'text-accent-amber',
    bg: 'bg-accent-amber/10',
    border: 'border-accent-amber/30',
    icon: AlertCircle,
  },
  high: {
    color: 'text-accent-red',
    bg: 'bg-accent-red/10',
    border: 'border-accent-red/30',
    icon: AlertTriangle,
  },
  critical: {
    color: 'text-accent-red',
    bg: 'bg-accent-red/20',
    border: 'border-accent-red/50',
    icon: XCircle,
  },
}

// ═══════════════════════════════════════════════════════════════════════════════
// MARGIN HEALTH SECTION
// ═══════════════════════════════════════════════════════════════════════════════

const marginStatusConfig = {
  safe: {
    color: 'text-accent-emerald',
    bg: 'bg-accent-emerald/10',
    border: 'border-accent-emerald/30',
    label: 'Healthy',
  },
  warning: {
    color: 'text-accent-amber',
    bg: 'bg-accent-amber/10',
    border: 'border-accent-amber/30',
    label: 'Warning',
  },
  danger: {
    color: 'text-accent-red',
    bg: 'bg-accent-red/10',
    border: 'border-accent-red/30',
    label: 'At Risk',
  },
  liquidated: {
    color: 'text-accent-red',
    bg: 'bg-accent-red/20',
    border: 'border-accent-red/50',
    label: 'Liquidated',
  },
  critical: {
    color: 'text-accent-red',
    bg: 'bg-accent-red/20',
    border: 'border-accent-red/50',
    label: 'Critical',
  },
}

function MarginPositionCard({ position }: { position: MarginPosition }) {
  const config = marginStatusConfig[position.status]
  const isLong = position.side === 'long'
  
  // Handle NaN values
  const distanceToLiq = isNaN(position.distance_to_liq_pct) ? 0 : position.distance_to_liq_pct
  
  // Progress bar: 0% = at liquidation, 100% = very safe (>20% distance)
  const progressPct = Math.min(100, Math.max(0, distanceToLiq * 5))
  
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={clsx(
        'glass-card p-4 border-l-4',
        config.border
      )}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-text-primary">{position.coin}</span>
          <span className={clsx(
            'px-2 py-0.5 text-xs font-bold rounded uppercase',
            isLong 
              ? 'bg-accent-emerald/20 text-accent-emerald' 
              : 'bg-accent-red/20 text-accent-red'
          )}>
            {position.side}
          </span>
          <span className="px-2 py-0.5 text-xs font-mono font-bold rounded bg-accent-cyan/20 text-accent-cyan">
            {position.leverage.toFixed(1)}x
          </span>
        </div>
        <span className={clsx(
          'px-2 py-0.5 text-xs font-medium rounded uppercase',
          config.bg,
          config.color
        )}>
          {config.label}
        </span>
      </div>

      {/* Distance to liquidation progress bar */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="text-text-muted">Distance to Liquidation</span>
          <span className={clsx('font-mono font-bold', config.color)}>
            {distanceToLiq.toFixed(1)}%
          </span>
        </div>
        <div className="h-2 bg-surface-2 rounded-full overflow-hidden">
          <div 
            className={clsx(
              'h-full rounded-full transition-all duration-500',
              position.status === 'safe' ? 'bg-accent-emerald' :
              position.status === 'warning' ? 'bg-accent-amber' : 'bg-accent-red'
            )}
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {/* Price info grid */}
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="p-2 rounded bg-void/30">
          <span className="text-text-dim block mb-0.5">Entry</span>
          <span className="font-mono text-text-primary">${position.entry_price.toLocaleString()}</span>
        </div>
        <div className="p-2 rounded bg-void/30">
          <span className="text-text-dim block mb-0.5">Current</span>
          <span className={clsx(
            'font-mono',
            position.price_change_pct >= 0 ? 'text-accent-emerald' : 'text-accent-red'
          )}>
            ${position.current_price.toLocaleString()}
          </span>
        </div>
        <div className="p-2 rounded bg-void/30">
          <span className="text-text-dim block mb-0.5">Liquidation</span>
          <span className="font-mono text-accent-red">
            {position.liquidation_price ? `$${position.liquidation_price.toLocaleString()}` : '-'}
          </span>
        </div>
      </div>
    </motion.div>
  )
}

function MarginHealthSection({ marginHealth, loading }: { marginHealth: MarginHealth | null; loading: boolean }) {
  if (loading) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-8 mb-8 text-center"
      >
        <div className="w-6 h-6 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-text-muted text-sm">Loading margin health...</p>
      </motion.div>
    )
  }

  if (!marginHealth || marginHealth.summary.total_positions === 0) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-8 mb-8"
      >
        <div className="flex items-center gap-2 mb-4">
          <Gauge className="w-5 h-5 text-accent-cyan" />
          <h2 className="text-lg font-semibold text-text-primary">Margin Health</h2>
        </div>
        <div className="text-center py-6">
          <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-accent-cyan/10 flex items-center justify-center">
            <CheckCircle className="w-6 h-6 text-accent-cyan" />
          </div>
          <p className="text-text-secondary">No open positions</p>
          <p className="text-text-dim text-sm mt-1">Margin health will appear when positions are opened</p>
        </div>
      </motion.div>
    )
  }

  const overallConfig = marginStatusConfig[marginHealth.overall_status]
  const atRiskCount = marginHealth.summary.positions_warning + marginHealth.summary.positions_danger

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-8"
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <Gauge className="w-5 h-5 text-accent-cyan" />
        <h2 className="text-lg font-semibold text-text-primary">Margin Health</h2>
        <span className={clsx(
          'px-2 py-0.5 text-xs font-bold rounded uppercase ml-2',
          overallConfig.bg,
          overallConfig.color
        )}>
          {overallConfig.label}
        </span>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="glass-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-accent-cyan" />
            <span className="text-label">Margin Used</span>
          </div>
          <div className="text-xl font-mono font-semibold text-text-primary">
            {formatCurrency(marginHealth.summary.total_margin_used)}
          </div>
          <p className="text-xs text-text-muted mt-1">
            {marginHealth.summary.margin_utilization_pct.toFixed(1)}% of capital
          </p>
        </div>

        <div className="glass-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className={clsx('w-4 h-4', atRiskCount > 0 ? 'text-accent-amber' : 'text-accent-emerald')} />
            <span className="text-label">Positions at Risk</span>
          </div>
          <div className={clsx(
            'text-xl font-mono font-semibold',
            atRiskCount > 0 ? 'text-accent-amber' : 'text-accent-emerald'
          )}>
            {atRiskCount}
          </div>
          <p className="text-xs text-text-muted mt-1">
            of {marginHealth.summary.total_positions} total positions
          </p>
        </div>

        <div className="glass-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-4 h-4 text-accent-amber" />
            <span className="text-label">Closest to Liq.</span>
          </div>
          <div className={clsx(
            'text-xl font-mono font-semibold',
            marginHealth.summary.closest_to_liq_pct && marginHealth.summary.closest_to_liq_pct < 10 
              ? 'text-accent-red' 
              : marginHealth.summary.closest_to_liq_pct && marginHealth.summary.closest_to_liq_pct < 15
                ? 'text-accent-amber'
                : 'text-accent-emerald'
          )}>
            {marginHealth.summary.closest_to_liq_pct !== null 
              ? `${marginHealth.summary.closest_to_liq_pct.toFixed(1)}%` 
              : '—'}
          </div>
          <p className="text-xs text-text-muted mt-1">
            distance to liquidation
          </p>
        </div>

        <div className={clsx('glass-card p-4 border', overallConfig.border)}>
          <div className="flex items-center gap-2 mb-2">
            <Shield className={clsx('w-4 h-4', overallConfig.color)} />
            <span className="text-label">Overall Status</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={clsx(
              'w-3 h-3 rounded-full',
              marginHealth.overall_status === 'safe' 
                ? 'bg-accent-emerald shadow-[0_0_8px_rgba(0,255,136,0.5)]'
                : marginHealth.overall_status === 'warning'
                  ? 'bg-accent-amber shadow-[0_0_8px_rgba(255,170,51,0.5)] animate-pulse'
                  : 'bg-accent-red shadow-[0_0_8px_rgba(255,71,87,0.5)] animate-pulse'
            )} />
            <span className={clsx('text-xl font-semibold', overallConfig.color)}>
              {overallConfig.label}
            </span>
          </div>
          <p className="text-xs text-text-muted mt-1">
            {marginHealth.summary.positions_safe} safe, {marginHealth.summary.positions_warning} warning, {marginHealth.summary.positions_danger} danger
          </p>
        </div>
      </div>

      {/* Position Cards */}
      {marginHealth.positions.length > 0 && (
        <>
          <h3 className="text-sm font-semibold text-text-secondary mb-3 uppercase tracking-wider">
            Position Details (sorted by risk)
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {marginHealth.positions.map((position, idx) => (
              <motion.div
                key={position.coin}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
              >
                <MarginPositionCard position={position} />
              </motion.div>
            ))}
          </div>
        </>
      )}
    </motion.div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// MARGIN CALL HISTORY SECTION
// ═══════════════════════════════════════════════════════════════════════════════

function MarginCallHistorySection({ 
  events, 
  loading, 
  onAcknowledge 
}: { 
  events: RiskEvent[]; 
  loading: boolean; 
  onAcknowledge: (id: string) => void 
}) {
  // Filter for margin call and margin warning events
  const marginEvents = events.filter(e => 
    e.event_type === 'MARGIN_CALL' || e.event_type === 'MARGIN_WARNING'
  )
  
  const marginCallCount = marginEvents.filter(e => e.event_type === 'MARGIN_CALL').length
  
  if (loading) {
    return null
  }
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="mt-8"
    >
      <div className="flex items-center gap-2 mb-4">
        <AlertTriangle className="w-5 h-5 text-accent-red" />
        <h2 className="text-lg font-semibold text-text-primary">Margin Call History</h2>
        {marginCallCount > 0 && (
          <span className="px-2 py-0.5 text-xs font-bold rounded-full bg-accent-red/20 text-accent-red border border-accent-red/30">
            {marginCallCount} liquidated
          </span>
        )}
      </div>
      
      {marginEvents.length === 0 ? (
        <div className="glass-card p-6 text-center">
          <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-accent-emerald/10 flex items-center justify-center">
            <Shield className="w-6 h-6 text-accent-emerald" />
          </div>
          <p className="text-text-secondary">No margin calls</p>
          <p className="text-text-dim text-sm mt-1">All positions are within safe margin levels</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {marginEvents.map((event, idx) => (
            <motion.div
              key={event.id}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: idx * 0.05 }}
            >
              <MarginCallCard event={event} onAcknowledge={onAcknowledge} />
            </motion.div>
          ))}
        </div>
      )}
    </motion.div>
  )
}

function MarginCallCard({ event, onAcknowledge }: { event: RiskEvent; onAcknowledge: (id: string) => void }) {
  const isMarginCall = event.event_type === 'MARGIN_CALL'
  const details = event.details || {}
  
  const symbol = details.symbol || 'Unknown'
  const direction = details.direction || ''
  const entryPrice = details.entryPrice || 0
  const exitPrice = details.exitPrice || event.trigger_value || 0
  const lossAmount = details.lossAmount || 0
  const leverage = details.leverage || 1
  const sizeUsdt = details.sizeUsdt || 0
  
  return (
    <div className={clsx(
      'glass-card p-4 border-l-4',
      isMarginCall 
        ? 'border-accent-red bg-accent-red/5' 
        : 'border-accent-amber bg-accent-amber/5',
      event.acknowledged && 'opacity-60'
    )}>
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={clsx(
            'p-2 rounded-lg',
            isMarginCall ? 'bg-accent-red/20' : 'bg-accent-amber/20'
          )}>
            <XCircle className={clsx(
              'w-5 h-5',
              isMarginCall ? 'text-accent-red' : 'text-accent-amber'
            )} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-text-primary">{symbol.replace('USDT', '')}</span>
              <span className={clsx(
                'px-1.5 py-0.5 text-xs font-bold rounded uppercase',
                direction.toLowerCase() === 'long' 
                  ? 'bg-accent-emerald/20 text-accent-emerald' 
                  : 'bg-accent-red/20 text-accent-red'
              )}>
                {direction}
              </span>
              <span className="px-1.5 py-0.5 text-xs font-mono rounded bg-accent-cyan/20 text-accent-cyan">
                {leverage}x
              </span>
            </div>
            <span className={clsx(
              'text-xs font-semibold uppercase',
              isMarginCall ? 'text-accent-red' : 'text-accent-amber'
            )}>
              {isMarginCall ? 'LIQUIDATED' : 'WARNING'}
            </span>
          </div>
        </div>
        
        {!event.acknowledged && (
          <button
            onClick={() => onAcknowledge(event.id)}
            className="btn-ghost p-1.5 text-accent-cyan hover:bg-accent-cyan/10"
          >
            <CheckCircle className="w-4 h-4" />
          </button>
        )}
      </div>
      
      {isMarginCall && (
        <div className="grid grid-cols-2 gap-2 text-xs mb-3">
          <div className="p-2 rounded bg-void/30">
            <span className="text-text-dim block mb-0.5">Entry</span>
            <span className="font-mono text-text-primary">${Number(entryPrice).toLocaleString()}</span>
          </div>
          <div className="p-2 rounded bg-void/30">
            <span className="text-text-dim block mb-0.5">Exit</span>
            <span className="font-mono text-accent-red">${Number(exitPrice).toLocaleString()}</span>
          </div>
        </div>
      )}
      
      <div className="flex items-center justify-between text-xs">
        <span className="text-text-muted">
          {new Date(event.timestamp).toLocaleString()}
        </span>
        {isMarginCall && lossAmount && (
          <span className="font-mono font-bold text-accent-red">
            -{formatCurrency(Math.abs(Number(lossAmount)))}
          </span>
        )}
      </div>
      
      {event.action_taken && (
        <div className="mt-2 p-2 rounded bg-void/30">
          <span className="text-xs text-text-dim">{event.action_taken}</span>
        </div>
      )}
      
      {event.acknowledged && (
        <div className="mt-2 flex items-center gap-1 text-xs text-text-dim">
          <CheckCircle className="w-3 h-3" />
          Acknowledged
        </div>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// RISK EVENT CARD
// ═══════════════════════════════════════════════════════════════════════════════

function RiskEventCard({ event, onAcknowledge }: { event: RiskEvent; onAcknowledge: (id: string) => void }) {
  const config = severityConfig[event.severity]
  const Icon = config.icon

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={clsx(
        'glass-card p-5 border-l-4',
        config.border,
        event.acknowledged && 'opacity-60'
      )}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-3">
          <div className={clsx('p-2 rounded-lg', config.bg)}>
            <Icon className={clsx('w-5 h-5', config.color)} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-text-primary">
                {(event.event_type || 'unknown').replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
              </h3>
              <span className={clsx(
                'px-2 py-0.5 rounded-full text-xs font-medium uppercase',
                config.bg,
                config.color
              )}>
                {event.severity}
              </span>
            </div>
            <p className="text-sm text-text-muted mt-1">
              {new Date(event.timestamp).toLocaleString()}
            </p>
          </div>
        </div>

        {!event.acknowledged && (
          <button
            onClick={() => onAcknowledge(event.id)}
            className="btn-ghost p-2 text-accent-cyan hover:bg-accent-cyan/10"
          >
            <CheckCircle className="w-4 h-4" />
          </button>
        )}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-text-dim block mb-1">Trigger Value</span>
          <span className={clsx('font-mono font-medium', config.color)}>
            {typeof event.trigger_value === 'number' 
              ? event.trigger_value.toFixed(4) 
              : event.trigger_value}
          </span>
        </div>
        <div>
          <span className="text-text-dim block mb-1">Threshold</span>
          <span className="font-mono text-text-primary">
            {typeof event.threshold_value === 'number' 
              ? event.threshold_value.toFixed(4) 
              : event.threshold_value}
          </span>
        </div>
      </div>

      {event.action_taken && (
        <div className="mt-4 p-3 rounded-lg bg-void/30">
          <span className="text-xs text-text-dim block mb-1">Action Taken</span>
          <span className="text-sm text-text-secondary">{event.action_taken}</span>
        </div>
      )}

      {event.acknowledged && (
        <div className="mt-3 flex items-center gap-1 text-xs text-text-dim">
          <CheckCircle className="w-3 h-3" />
          Acknowledged
        </div>
      )}
    </motion.div>
  )
}

export default function RiskPage() {
  const [riskEvents, setRiskEvents] = useState<RiskEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [marginLoading, setMarginLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'unacknowledged' | 'critical' | 'high'>('all')
  const [marginHealth, setMarginHealth] = useState<MarginHealth | null>(null)
  const [portfolioData, setPortfolioData] = useState({
    var_95: null as number | null,
    max_drawdown: null as number | null,
    total_equity: 108000,
    daily_pnl_percent: 0,
  })
  const [accountData, setAccountData] = useState({
    balance: 108000,
    initialBalance: 108000,
    totalFees: 0,
    slippageCost: 0,
    totalTrades: 0,
    winningTrades: 0,
    mode: 'paper' as const,
  })

  const { isConnected } = useWebSocket({
    channel: 'risk',
    onMessage: (message) => {
      if (message.event_type?.includes('risk') || message.type === 'margin_call') {
        fetchRiskEvents()
        fetchMarginHealth()
      }
    },
  })

  async function fetchMarginHealth() {
    try {
      // First try the Portfolio Manager status which has live positions
      const pmStatus = await api.getPortfolioManagerStatus().catch(() => null)
      
      if (pmStatus && pmStatus.portfolio?.positions && pmStatus.portfolio.positions.length > 0) {
        // Build margin health from PM positions
        const positions = pmStatus.portfolio.positions
        const stats = pmStatus.portfolio.statistics
        
        // Map positions to MarginPosition format
        const marginPositions: MarginPosition[] = positions.map(p => {
          // Handle missing or invalid values
          const currentPrice = p.current_price || p.entry_price || 0
          const liquidationPrice = p.liquidation_price || 0
          
          // Calculate distance to liquidation, handle edge cases
          let distanceToLiq = 0
          if (currentPrice > 0 && liquidationPrice > 0) {
            distanceToLiq = Math.abs((currentPrice - liquidationPrice) / currentPrice) * 100
          }
          // Handle NaN
          if (isNaN(distanceToLiq)) {
            distanceToLiq = 100 // Default to safe if we can't calculate
          }
          
          const status: 'safe' | 'warning' | 'danger' = 
            distanceToLiq < 5 ? 'danger' :
            distanceToLiq < 15 ? 'warning' : 'safe'
          
          return {
            coin: p.symbol?.replace('USDT', '') || 'UNKNOWN',
            side: (p.direction || 'LONG').toLowerCase(),
            leverage: p.leverage || 1,
            entry_price: p.entry_price || 0,
            current_price: currentPrice,
            liquidation_price: liquidationPrice,
            distance_to_liq_pct: distanceToLiq,
            price_change_pct: p.pnl_percent || 0,
            margin_used: (p.size_usdt || 0) / (p.leverage || 1),
            status,
          }
        })
        
        // Sort by risk (closest to liquidation first)
        marginPositions.sort((a, b) => a.distance_to_liq_pct - b.distance_to_liq_pct)
        
        const positionsSafe = marginPositions.filter(p => p.status === 'safe').length
        const positionsWarning = marginPositions.filter(p => p.status === 'warning').length
        const positionsDanger = marginPositions.filter(p => p.status === 'danger').length
        
        const totalMarginUsed = marginPositions.reduce((sum, p) => sum + p.margin_used, 0)
        const marginUtilization = (totalMarginUsed / stats.current_capital) * 100
        const closestToLiq = marginPositions.length > 0 ? marginPositions[0].distance_to_liq_pct : null
        
        const overallStatus: 'safe' | 'warning' | 'danger' | 'critical' = 
          positionsDanger > 0 ? 'danger' :
          positionsWarning > 0 ? 'warning' : 'safe'
        
        setMarginHealth({
          overall_status: overallStatus,
          summary: {
            total_positions: marginPositions.length,
            positions_safe: positionsSafe,
            positions_warning: positionsWarning,
            positions_danger: positionsDanger,
            total_margin_used: totalMarginUsed,
            margin_utilization_pct: marginUtilization,
            closest_to_liq_pct: closestToLiq,
          },
          positions: marginPositions,
        })
      } else {
        // Fall back to the API endpoint
        const data = await api.getMarginHealth().catch(() => null)
        setMarginHealth(data)
      }
    } catch (error) {
      console.error('Failed to fetch margin health:', error)
    } finally {
      setMarginLoading(false)
    }
  }

  async function fetchRiskEvents() {
    try {
      const [events, portfolio] = await Promise.all([
        api.getRiskEvents(undefined, 100).catch(() => []),
        api.getPortfolio().catch(() => null),
      ])
      setRiskEvents(events as RiskEvent[])
      if (portfolio) {
        setPortfolioData({
          var_95: portfolio.var_95,
          max_drawdown: portfolio.max_drawdown,
          total_equity: portfolio.total_equity,
          daily_pnl_percent: portfolio.daily_pnl_percent,
        })
      }
    } catch (error) {
      console.error('Failed to fetch risk events:', error)
    } finally {
      setLoading(false)
    }
  }

  async function handleAcknowledge(eventId: string) {
    try {
      await api.acknowledgeRiskEvent(eventId)
      setRiskEvents(prev => 
        prev.map(e => e.id === eventId ? { ...e, acknowledged: true } : e)
      )
    } catch (error) {
      console.error('Failed to acknowledge event:', error)
    }
  }

  useEffect(() => {
    fetchRiskEvents()
    fetchMarginHealth()
    const riskInterval = setInterval(fetchRiskEvents, 30000)
    const marginInterval = setInterval(fetchMarginHealth, 10000)
    return () => {
      clearInterval(riskInterval)
      clearInterval(marginInterval)
    }
  }, [])

  // Filter events
  const filteredEvents = riskEvents.filter(event => {
    if (filter === 'unacknowledged') return !event.acknowledged
    if (filter === 'critical') return event.severity === 'critical'
    if (filter === 'high') return event.severity === 'high' || event.severity === 'critical'
    return true
  })

  // Count by severity
  const criticalCount = riskEvents.filter(e => e.severity === 'critical' && !e.acknowledged).length
  const highCount = riskEvents.filter(e => e.severity === 'high' && !e.acknowledged).length
  const unacknowledgedCount = riskEvents.filter(e => !e.acknowledged).length

  // Risk parameters (from env or defaults)
  const riskParams = {
    maxPositionSize: 0.10, // 10% of portfolio
    maxDrawdown: 0.15, // 15%
    dailyLossLimit: 0.05, // 5%
    varLimit: 0.02, // 2% VaR 95
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar isConnected={isConnected} />

      <main className="flex-1 ml-[280px] p-6 lg:p-8">
        {/* Header */}
        <header className="flex items-center justify-between mb-8">
          <div>
            <motion.h1 
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="text-2xl font-semibold text-text-primary tracking-tight"
            >
              Risk Management
            </motion.h1>
            <p className="text-xs text-text-muted mt-1">
              Monitor risk metrics and manage alerts
            </p>
          </div>

          <div className="flex items-center gap-3">
            {unacknowledgedCount > 0 && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent-red/10 border border-accent-red/30">
                <Bell className="w-4 h-4 text-accent-red" />
                <span className="text-sm font-medium text-accent-red">
                  {unacknowledgedCount} unread
                </span>
              </div>
            )}
            <button
              onClick={fetchRiskEvents}
              className="btn-ghost p-2"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </header>

        {/* Margin Health Section */}
        <MarginHealthSection marginHealth={marginHealth} loading={marginLoading} />
        
        {/* Margin Call History Section */}
        <MarginCallHistorySection events={riskEvents} loading={loading} onAcknowledge={handleAcknowledge} />
        
        {/* Risk Events Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="mt-8"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-accent-amber" />
              <h2 className="text-lg font-semibold text-text-primary">Risk Events</h2>
            </div>
            
            {/* Filter buttons */}
            <div className="flex gap-1 bg-void/50 p-1 rounded-lg">
              {(['all', 'unacknowledged', 'critical', 'high'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={clsx(
                    'px-3 py-1.5 text-xs font-medium rounded-md transition-all',
                    filter === f
                      ? 'bg-accent-cyan/20 text-accent-cyan border border-accent-cyan/30'
                      : 'text-text-muted hover:text-text-secondary'
                  )}
                >
                  {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>
          </div>
          
          {loading ? (
            <div className="glass-card p-8 text-center">
              <div className="w-6 h-6 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <p className="text-text-muted text-sm">Loading risk events...</p>
            </div>
          ) : filteredEvents.filter(e => e.event_type !== 'MARGIN_CALL' && e.event_type !== 'MARGIN_WARNING').length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredEvents
                .filter(e => e.event_type !== 'MARGIN_CALL' && e.event_type !== 'MARGIN_WARNING')
                .map((event) => (
                  <RiskEventCard 
                    key={event.id} 
                    event={event} 
                    onAcknowledge={handleAcknowledge} 
                  />
                ))}
            </div>
          ) : (
            <div className="glass-card p-8 text-center">
              <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-accent-emerald/10 flex items-center justify-center">
                <CheckCircle className="w-6 h-6 text-accent-emerald" />
              </div>
              <p className="text-text-secondary">No risk events</p>
              <p className="text-text-dim text-sm mt-1">System is operating normally</p>
            </div>
          )}
        </motion.div>
      </main>
    </div>
  )
}

