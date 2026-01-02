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

function formatCurrency(value: number, showSign = false): string {
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
                {event.event_type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
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
  const [filter, setFilter] = useState<'all' | 'unacknowledged' | 'critical' | 'high'>('all')
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
      if (message.event_type?.includes('risk')) {
        fetchRiskEvents()
      }
    },
  })

  async function fetchRiskEvents() {
    try {
      const [events, portfolio] = await Promise.all([
        api.getRiskEvents(undefined, 100).catch(() => []),
        api.getPortfolio().catch(() => null),
      ])
      setRiskEvents(events)
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
    const interval = setInterval(fetchRiskEvents, 30000)
    return () => clearInterval(interval)
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
      <Sidebar accountData={accountData} isConnected={isConnected} />

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

        {/* Risk Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card p-5"
          >
            <div className="flex items-center gap-2 mb-2">
              <Activity className="w-4 h-4 text-accent-cyan" />
              <span className="text-label">VaR (95%)</span>
            </div>
            <div className="text-2xl font-mono font-semibold text-text-primary">
              {portfolioData.var_95 
                ? formatCurrency(portfolioData.var_95)
                : '—'}
            </div>
            <p className="text-xs text-text-muted mt-1">
              Max daily loss at 95% confidence
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card p-5"
          >
            <div className="flex items-center gap-2 mb-2">
              <TrendingDown className="w-4 h-4 text-accent-red" />
              <span className="text-label">Max Drawdown</span>
            </div>
            <div className={clsx(
              'text-2xl font-mono font-semibold',
              portfolioData.max_drawdown && portfolioData.max_drawdown > 0.10 
                ? 'text-accent-red' 
                : 'text-text-primary'
            )}>
              {portfolioData.max_drawdown 
                ? formatPercentage(portfolioData.max_drawdown * 100)
                : '0.00%'}
            </div>
            <p className="text-xs text-text-muted mt-1">
              Limit: {formatPercentage(riskParams.maxDrawdown * 100)}
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card p-5"
          >
            <div className="flex items-center gap-2 mb-2">
              <Shield className="w-4 h-4 text-accent-emerald" />
              <span className="text-label">Daily P&L</span>
            </div>
            <div className={clsx(
              'text-2xl font-mono font-semibold',
              portfolioData.daily_pnl_percent >= 0 ? 'text-accent-emerald' : 'text-accent-red'
            )}>
              {formatPercentage(portfolioData.daily_pnl_percent, true)}
            </div>
            <p className="text-xs text-text-muted mt-1">
              Limit: {formatPercentage(riskParams.dailyLossLimit * 100)}
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="glass-card p-5"
          >
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-accent-amber" />
              <span className="text-label">Active Alerts</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className={clsx(
                'text-2xl font-mono font-semibold',
                criticalCount > 0 ? 'text-accent-red' : highCount > 0 ? 'text-accent-amber' : 'text-accent-emerald'
              )}>
                {criticalCount + highCount}
              </span>
              <span className="text-sm text-text-muted">
                ({criticalCount} critical)
              </span>
            </div>
          </motion.div>
        </div>

        {/* Risk Parameters */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="glass-card p-5 mb-8"
        >
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-4 h-4 text-accent-cyan" />
            <span className="text-label">Risk Parameters</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-3 rounded-lg bg-void/30">
              <span className="text-xs text-text-dim block mb-1">Max Position Size</span>
              <span className="font-mono text-text-primary">{formatPercentage(riskParams.maxPositionSize * 100)}</span>
            </div>
            <div className="p-3 rounded-lg bg-void/30">
              <span className="text-xs text-text-dim block mb-1">Max Drawdown Limit</span>
              <span className="font-mono text-text-primary">{formatPercentage(riskParams.maxDrawdown * 100)}</span>
            </div>
            <div className="p-3 rounded-lg bg-void/30">
              <span className="text-xs text-text-dim block mb-1">Daily Loss Limit</span>
              <span className="font-mono text-text-primary">{formatPercentage(riskParams.dailyLossLimit * 100)}</span>
            </div>
            <div className="p-3 rounded-lg bg-void/30">
              <span className="text-xs text-text-dim block mb-1">VaR Limit (95%)</span>
              <span className="font-mono text-text-primary">{formatPercentage(riskParams.varLimit * 100)}</span>
            </div>
          </div>
        </motion.div>

        {/* Filter Tabs */}
        <div className="flex gap-2 mb-6">
          {(['all', 'unacknowledged', 'high', 'critical'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={clsx(
                'px-4 py-2 rounded-lg text-sm font-medium transition-all',
                filter === f
                  ? 'bg-accent-cyan/20 text-accent-cyan border border-accent-cyan/30'
                  : 'text-text-muted hover:text-text-secondary hover:bg-glass-bg'
              )}
            >
              {f === 'all' ? 'All Events' : f === 'unacknowledged' ? 'Unread' : f.charAt(0).toUpperCase() + f.slice(1)}
              {f === 'unacknowledged' && unacknowledgedCount > 0 && (
                <span className="ml-2 px-1.5 py-0.5 rounded-full bg-accent-red/20 text-accent-red text-xs">
                  {unacknowledgedCount}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Risk Events */}
        {loading ? (
          <div className="glass-card p-12 text-center">
            <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-text-muted">Loading risk events...</p>
          </div>
        ) : filteredEvents.length > 0 ? (
          <div className="space-y-4">
            {filteredEvents.map((event) => (
              <RiskEventCard 
                key={event.id} 
                event={event} 
                onAcknowledge={handleAcknowledge}
              />
            ))}
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="glass-card p-12 text-center"
          >
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-accent-emerald/10 flex items-center justify-center">
              <CheckCircle className="w-8 h-8 text-accent-emerald" />
            </div>
            <p className="text-text-primary font-medium mb-1">Keine Risk Events</p>
            <p className="text-text-dim text-sm">
              {filter === 'unacknowledged' 
                ? 'Alle Events wurden bestätigt.'
                : 'Keine Risk Events vorhanden. Das System läuft normal.'}
            </p>
          </motion.div>
        )}
      </main>
    </div>
  )
}

