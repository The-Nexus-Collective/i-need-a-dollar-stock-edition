'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { 
  TrendingUp, 
  TrendingDown, 
  Clock, 
  Target,
  Shield,
  BarChart2,
  RefreshCw,
} from 'lucide-react'
import { clsx } from 'clsx'

import { Sidebar } from '@/components/Sidebar'
import { api } from '@/lib/api'
import { useWebSocket } from '@/lib/websocket'

interface Position {
  id: string
  symbol: string
  direction: string  // API returns 'LONG' or 'SHORT'
  quantity: number
  entry_price: number
  current_price: number
  size_usdt: number
  leverage: number
  stop_loss_price: number | null
  take_profit_price: number | null
  status: string
  entry_time: string
  exit_time: string | null
  exit_price: number | null
  realized_pnl: number
  conviction: number
  reasoning: string | null
  unrealized_pnl: number
  unrealized_pnl_pct: number
  liquidation_price: number
  margin_risk_pct: number
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
  // Handle direction from API
  const isLong = position.direction?.toUpperCase() === 'LONG'
  const displaySide = isLong ? 'LONG' : 'SHORT'
  
  // Use current_price or fallback to entry_price
  const currentPrice = position.current_price || position.entry_price || 0
  const entryPrice = position.entry_price || 0
  
  // Use unrealized PnL directly from PM
  const isProfitable = (position.unrealized_pnl || 0) >= 0
  const pnlPercent = position.unrealized_pnl_pct || 0

  // Get coin symbol (remove USDT suffix if present)
  const coin = position.symbol?.replace('USDT', '') || 'UNKNOWN'

  // Use liquidation price for risk display
  const liquidationPrice = position.liquidation_price || 0
  const distanceToLiq = liquidationPrice > 0 && currentPrice > 0
    ? Math.abs((currentPrice - liquidationPrice) / currentPrice) * 100
    : 0

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
            <span className="font-semibold text-text-primary">{coin}</span>
            <span className={clsx(
              'ml-2 text-xs px-2 py-0.5 rounded-full',
              isLong ? 'bg-accent-emerald/20 text-accent-emerald' : 'bg-accent-red/20 text-accent-red'
            )}>
              {displaySide}
            </span>
            {position.leverage && (
              <span className="ml-1 text-xs text-accent-cyan">{position.leverage}x</span>
            )}
            <p className="text-xs text-text-muted mt-0.5">
              <Clock className="w-3 h-3 inline mr-1" />
              {new Date(position.entry_time).toLocaleString()}
            </p>
          </div>
        </div>
      </td>

      {/* Quantity / Size */}
      <td className="py-4 px-4 text-right">
        <span className="font-mono text-text-primary">
          {position.quantity?.toFixed(6) || position.size_usdt?.toFixed(0) || '-'}
        </span>
        <p className="text-xs text-text-muted">
          {position.size_usdt ? formatCurrency(position.size_usdt) : formatCurrency((position.quantity || 0) * currentPrice)}
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
          {formatCurrency(currentPrice)}
        </span>
      </td>

      {/* Liquidation Price */}
      <td className="py-4 px-4 text-right">
        {liquidationPrice > 0 ? (
          <div className="flex items-center justify-end gap-2">
            <Shield className="w-4 h-4 text-accent-red" />
            <div>
              <span className="font-mono text-text-primary">
                {formatCurrency(liquidationPrice)}
              </span>
              <p className={clsx(
                'text-xs',
                distanceToLiq < 10 ? 'text-accent-red' : 
                distanceToLiq < 20 ? 'text-accent-amber' : 'text-accent-emerald'
              )}>
                {distanceToLiq.toFixed(1)}% away
              </p>
            </div>
          </div>
        ) : (
          <span className="text-text-muted">-</span>
        )}
      </td>

      {/* Conviction */}
      <td className="py-4 px-4 text-right">
        <div className="flex items-center justify-end gap-2">
          <Target className="w-4 h-4 text-accent-cyan" />
          <div>
            <span className={clsx(
              'font-mono font-semibold',
              position.conviction >= 70 ? 'text-accent-emerald' :
              position.conviction >= 50 ? 'text-accent-amber' : 'text-text-muted'
            )}>
              {position.conviction}%
            </span>
            <p className="text-xs text-text-muted">
              conviction
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
          {formatCurrency(position.unrealized_pnl || 0, true)}
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
  const [loading, setLoading] = useState(true)

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
      // Fetch from Portfolio Manager which has the actual live positions
      const pmStatus = await api.getPortfolioManagerStatus().catch(() => null)
      
      if (pmStatus && pmStatus.portfolio?.positions) {
        // Map PM positions to our Position interface
        const mappedPositions: Position[] = pmStatus.portfolio.positions.map(p => ({
          id: p.id,
          symbol: p.symbol,
          direction: p.direction,
          quantity: p.quantity,
          entry_price: p.entry_price,
          current_price: p.current_price,
          size_usdt: p.size_usdt,
          leverage: p.leverage,
          stop_loss_price: null, // PM doesn't use fixed SL
          take_profit_price: null, // PM doesn't use fixed TP
          status: 'open',
          entry_time: p.opened_at,
          exit_time: null,
          exit_price: null,
          realized_pnl: 0,
          conviction: p.conviction,
          reasoning: p.reason,
          unrealized_pnl: p.unrealized_pnl,
          unrealized_pnl_pct: p.unrealized_pnl_pct,
          liquidation_price: p.liquidation_price,
          margin_risk_pct: p.margin_risk_pct,
        }))
        setPositions(mappedPositions)
      } else {
        setPositions([])
      }
    } catch (error) {
      console.error('Failed to fetch positions:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchPositions()
    const interval = setInterval(fetchPositions, 5000) // Faster refresh for open positions
    return () => clearInterval(interval)
  }, [])

  // Calculate totals
  const totalUnrealizedPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl || 0), 0)
  
  // Leveraged Exposure = current notional value (quantity × current_price)
  const totalExposure = positions.reduce((sum, p) => 
    sum + ((p.quantity || 0) * (p.current_price || p.entry_price || 0)), 0)

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
              Open Positions
            </motion.h1>
            <p className="text-xs text-text-muted mt-1">
              Current holdings • Updates every 5 seconds
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
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
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
              <Target className="w-4 h-4 text-accent-amber" />
              <span className="text-label">Leveraged Exposure</span>
            </div>
            <div className="text-2xl font-mono font-semibold text-accent-amber">
              {formatCurrency(totalExposure)}
            </div>
            <p className="text-xs text-text-muted mt-1">current notional value</p>
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
          ) : positions.length > 0 ? (
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
                      Liquidation
                    </th>
                    <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                      Conviction
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
                  {positions.map((position) => (
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
                Keine offenen Positionen vorhanden.
              </p>
            </div>
          )}
        </motion.div>
      </main>
    </div>
  )
}

