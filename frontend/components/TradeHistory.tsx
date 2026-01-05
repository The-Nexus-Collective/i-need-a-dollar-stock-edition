'use client'

import { motion } from 'framer-motion'
import { clsx } from 'clsx'
import { 
  TrendingUp, 
  TrendingDown, 
  Clock,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react'

interface Trade {
  id: string
  symbol: string
  side: 'buy' | 'sell'
  price: number
  quantity: number
  fee: number
  total: number
  pnl?: number
  executedAt: string
  status: 'filled' | 'pending' | 'cancelled'
}

interface TradeHistoryProps {
  trades: Trade[]
  limit?: number
}

export function TradeHistory({ trades, limit = 15 }: TradeHistoryProps) {
  const displayTrades = trades.slice(0, limit)

  if (displayTrades.length === 0) {
    return (
      <div className="glass-card p-8 text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-void/50 flex items-center justify-center">
          <Clock className="w-8 h-8 text-text-dim" />
        </div>
        <p className="text-text-muted">No trades recorded</p>
        <p className="text-xs text-text-dim mt-1">Trades will appear here when executed</p>
      </div>
    )
  }

  return (
    <div className="glass-card overflow-hidden">
      <div className="p-4 border-b border-glass-border">
        <div className="flex items-center justify-between">
          <span className="text-label">Trade History</span>
          <span className="text-[10px] text-text-muted">
            Last {displayTrades.length} trades
          </span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Symbol</th>
              <th>Side</th>
              <th>Price</th>
              <th>Quantity</th>
              <th>Fee</th>
              <th>Total</th>
              <th>P&L</th>
            </tr>
          </thead>
          <tbody>
            {displayTrades.map((trade, index) => (
              <motion.tr
                key={trade.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.03 }}
              >
                <td className="text-text-muted">
                  <div className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    <span className="text-xs">
                      {new Date(trade.executedAt).toLocaleTimeString([], { 
                        hour: '2-digit', 
                        minute: '2-digit' 
                      })}
                    </span>
                  </div>
                </td>
                <td>
                  <span className="font-semibold">{trade.symbol}</span>
                </td>
                <td>
                  <span className={clsx(
                    'badge',
                    trade.side === 'buy' ? 'badge-long' : 'badge-short'
                  )}>
                    {trade.side === 'buy' ? (
                      <span className="flex items-center gap-1">
                        <ArrowUpRight className="w-3 h-3" />
                        BUY
                      </span>
                    ) : (
                      <span className="flex items-center gap-1">
                        <ArrowDownRight className="w-3 h-3" />
                        SELL
                      </span>
                    )}
                  </span>
                </td>
                <td className="font-mono text-text-primary">
                  ${trade.price.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                </td>
                <td className="font-mono text-text-secondary">
                  {trade.quantity.toFixed(6)}
                </td>
                <td className="font-mono text-accent-amber">
                  ${trade.fee.toFixed(4)}
                </td>
                <td className="font-mono text-text-primary">
                  ${trade.total.toFixed(2)}
                </td>
                <td>
                  {trade.pnl !== undefined ? (
                    <span className={clsx(
                      'font-mono font-medium',
                      trade.pnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'
                    )}>
                      {trade.pnl >= 0 ? '+' : ''}{trade.pnl.toLocaleString('en-US', { 
                        style: 'currency', 
                        currency: 'USD' 
                      })}
                    </span>
                  ) : (
                    <span className="text-text-dim">—</span>
                  )}
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

