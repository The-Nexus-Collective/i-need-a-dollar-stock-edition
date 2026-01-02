'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { 
  TrendingUp, 
  TrendingDown, 
  Clock, 
  Target,
  Shield,
  DollarSign,
  BarChart2,
  Filter,
  RefreshCw,
} from 'lucide-react'
import { clsx } from 'clsx'

import { Sidebar } from '@/components/Sidebar'
import { api } from '@/lib/api'
import { useWebSocket } from '@/lib/websocket'

interface Position {
  id: string
  coin: string
  side: 'long' | 'short'
  quantity: number
  entry_price: number
  current_price: number
  unrealized_pnl: number
  realized_pnl: number
  stop_loss: number
  take_profit: number
  status: string
  opened_at: string
  closed_at: string | null
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

function PositionRow({ position }: { position: Position }) {
  const isLong = position.side === 'long'
  const isProfitable = position.unrealized_pnl >= 0
  const pnlPercent = position.entry_price > 0 
    ? ((position.current_price - position.entry_price) / position.entry_price) * 100 * (isLong ? 1 : -1)
    : 0

  // Calculate distance to SL/TP
  const distanceToSL = isLong 
    ? ((position.current_price - position.stop_loss) / position.current_price) * 100
    : ((position.stop_loss - position.current_price) / position.current_price) * 100
  
  const distanceToTP = isLong
    ? ((position.take_profit - position.current_price) / position.current_price) * 100
    : ((position.current_price - position.take_profit) / position.current_price) * 100

  return (
    <motion.tr
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="border-b border-glass-border hover:bg-glass-bg/50 transition-colors"
    >
      {/* Coin & Side */}
      <td className="py-4 px-4">
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
            <span className="font-semibold text-text-primary">{position.coin}</span>
            <span className={clsx(
              'ml-2 text-xs px-2 py-0.5 rounded-full',
              isLong ? 'bg-accent-emerald/20 text-accent-emerald' : 'bg-accent-red/20 text-accent-red'
            )}>
              {position.side.toUpperCase()}
            </span>
            <p className="text-xs text-text-muted mt-0.5">
              <Clock className="w-3 h-3 inline mr-1" />
              {new Date(position.opened_at).toLocaleString()}
            </p>
          </div>
        </div>
      </td>

      {/* Quantity */}
      <td className="py-4 px-4 text-right">
        <span className="font-mono text-text-primary">{position.quantity.toFixed(6)}</span>
        <p className="text-xs text-text-muted">
          {formatCurrency(position.quantity * position.current_price)}
        </p>
      </td>

      {/* Entry Price */}
      <td className="py-4 px-4 text-right">
        <span className="font-mono text-text-primary">
          {formatCurrency(position.entry_price)}
        </span>
      </td>

      {/* Current Price */}
      <td className="py-4 px-4 text-right">
        <span className={clsx(
          'font-mono',
          isProfitable ? 'text-accent-emerald' : 'text-accent-red'
        )}>
          {formatCurrency(position.current_price)}
        </span>
      </td>

      {/* Stop Loss */}
      <td className="py-4 px-4 text-right">
        <div className="flex items-center justify-end gap-2">
          <Shield className="w-4 h-4 text-accent-red" />
          <div>
            <span className="font-mono text-text-primary">
              {formatCurrency(position.stop_loss)}
            </span>
            <p className="text-xs text-accent-red">
              {distanceToSL.toFixed(1)}% away
            </p>
          </div>
        </div>
      </td>

      {/* Take Profit */}
      <td className="py-4 px-4 text-right">
        <div className="flex items-center justify-end gap-2">
          <Target className="w-4 h-4 text-accent-emerald" />
          <div>
            <span className="font-mono text-text-primary">
              {formatCurrency(position.take_profit)}
            </span>
            <p className="text-xs text-accent-emerald">
              {distanceToTP.toFixed(1)}% away
            </p>
          </div>
        </div>
      </td>

      {/* Unrealized PnL */}
      <td className="py-4 px-4 text-right">
        <div className={clsx(
          'font-mono font-semibold',
          isProfitable ? 'text-accent-emerald' : 'text-accent-red'
        )}>
          {formatCurrency(position.unrealized_pnl, true)}
        </div>
        <p className={clsx(
          'text-xs',
          isProfitable ? 'text-accent-emerald' : 'text-accent-red'
        )}>
          {formatPercentage(pnlPercent, true)}
        </p>
      </td>

      {/* Status */}
      <td className="py-4 px-4 text-right">
        <span className={clsx(
          'px-2 py-1 rounded-full text-xs font-medium',
          position.status === 'open' ? 'bg-accent-cyan/20 text-accent-cyan' : 'bg-text-dim/20 text-text-muted'
        )}>
          {position.status.toUpperCase()}
        </span>
      </td>
    </motion.tr>
  )
}

export default function PositionsPage() {
  const [positions, setPositions] = useState<Position[]>([])
  const [closedPositions, setClosedPositions] = useState<Position[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'all' | 'open' | 'closed'>('all')
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
    channel: 'trading',
    onMessage: (message) => {
      if (message.event_type?.includes('position')) {
        fetchPositions()
      }
    },
  })

  async function fetchPositions() {
    try {
      const [openData, closedData] = await Promise.all([
        api.getPositions('open').catch(() => []),
        api.getPositions('closed').catch(() => []),
      ])
      setPositions(openData)
      setClosedPositions(closedData)
    } catch (error) {
      console.error('Failed to fetch positions:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPositions()
    const interval = setInterval(fetchPositions, 10000)
    return () => clearInterval(interval)
  }, [])

  const displayedPositions = filter === 'all' 
    ? [...positions, ...closedPositions]
    : filter === 'open' 
      ? positions 
      : closedPositions

  // Calculate totals
  const totalUnrealizedPnl = positions.reduce((sum, p) => sum + p.unrealized_pnl, 0)
  const totalRealizedPnl = closedPositions.reduce((sum, p) => sum + p.realized_pnl, 0)
  const totalValue = positions.reduce((sum, p) => sum + (p.quantity * p.current_price), 0)

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
              Positions
            </motion.h1>
            <p className="text-xs text-text-muted mt-1">
              Manage and monitor your trading positions
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={fetchPositions}
              className="btn-ghost p-2"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </header>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card p-5"
          >
            <div className="flex items-center gap-2 mb-2">
              <BarChart2 className="w-4 h-4 text-accent-cyan" />
              <span className="text-label">Open Positions</span>
            </div>
            <div className="text-2xl font-mono font-semibold text-text-primary">
              {positions.length}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card p-5"
          >
            <div className="flex items-center gap-2 mb-2">
              <DollarSign className="w-4 h-4 text-accent-cyan" />
              <span className="text-label">Total Value</span>
            </div>
            <div className="text-2xl font-mono font-semibold text-text-primary">
              {formatCurrency(totalValue)}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card p-5"
          >
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-accent-emerald" />
              <span className="text-label">Unrealized P&L</span>
            </div>
            <div className={clsx(
              'text-2xl font-mono font-semibold',
              totalUnrealizedPnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'
            )}>
              {formatCurrency(totalUnrealizedPnl, true)}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="glass-card p-5"
          >
            <div className="flex items-center gap-2 mb-2">
              <Target className="w-4 h-4 text-accent-amber" />
              <span className="text-label">Realized P&L</span>
            </div>
            <div className={clsx(
              'text-2xl font-mono font-semibold',
              totalRealizedPnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'
            )}>
              {formatCurrency(totalRealizedPnl, true)}
            </div>
          </motion.div>
        </div>

        {/* Filter Tabs */}
        <div className="flex gap-2 mb-6">
          {(['all', 'open', 'closed'] as const).map((f) => (
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
              {f === 'all' ? 'All Positions' : f === 'open' ? 'Open' : 'Closed'}
              <span className="ml-2 text-xs opacity-60">
                ({f === 'all' ? positions.length + closedPositions.length : f === 'open' ? positions.length : closedPositions.length})
              </span>
            </button>
          ))}
        </div>

        {/* Positions Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card overflow-hidden"
        >
          {loading ? (
            <div className="p-12 text-center">
              <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <p className="text-text-muted">Loading positions...</p>
            </div>
          ) : displayedPositions.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-glass-border bg-void/30">
                    <th className="text-left py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                      Position
                    </th>
                    <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                      Quantity
                    </th>
                    <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                      Entry
                    </th>
                    <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                      Current
                    </th>
                    <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                      Stop Loss
                    </th>
                    <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                      Take Profit
                    </th>
                    <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                      P&L
                    </th>
                    <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {displayedPositions.map((position) => (
                    <PositionRow key={position.id} position={position} />
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-12 text-center">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-void/50 flex items-center justify-center">
                <BarChart2 className="w-8 h-8 text-text-dim" />
              </div>
              <p className="text-text-muted font-medium mb-1">Keine Positionen</p>
              <p className="text-text-dim text-sm">
                {filter === 'open' 
                  ? 'Keine offenen Positionen vorhanden.'
                  : filter === 'closed'
                    ? 'Keine geschlossenen Positionen vorhanden.'
                    : 'Der Bot hat noch keine Trades ausgeführt.'}
              </p>
            </div>
          )}
        </motion.div>
      </main>
    </div>
  )
}

