'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { 
  TrendingUp, 
  TrendingDown, 
  Clock, 
  Search,
  Calendar,
  Download,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
} from 'lucide-react'
import { clsx } from 'clsx'

import { Sidebar } from '@/components/Sidebar'
import { api } from '@/lib/api'
import { useWebSocket } from '@/lib/websocket'

interface Trade {
  id: string
  coin: string
  side: string
  order_type: string
  quantity: number
  price: number
  fee: number
  status: string
  is_paper: boolean
  executed_at: string
  created_at: string
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

function TradeRow({ trade, index }: { trade: Trade; index: number }) {
  const isBuy = trade.side.toLowerCase() === 'buy'
  const total = trade.quantity * trade.price
  const totalWithFee = total + trade.fee

  return (
    <motion.tr
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.02 }}
      className="border-b border-glass-border hover:bg-glass-bg/50 transition-colors"
    >
      {/* Time */}
      <td className="py-4 px-4">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-text-dim" />
          <div>
            <span className="text-sm text-text-primary font-mono">
              {new Date(trade.executed_at || trade.created_at).toLocaleTimeString()}
            </span>
            <p className="text-xs text-text-muted">
              {new Date(trade.executed_at || trade.created_at).toLocaleDateString()}
            </p>
          </div>
        </div>
      </td>

      {/* Coin */}
      <td className="py-4 px-4">
        <span className="font-semibold text-text-primary">{trade.coin}</span>
      </td>

      {/* Side */}
      <td className="py-4 px-4">
        <span className={clsx(
          'inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium',
          isBuy ? 'bg-accent-emerald/20 text-accent-emerald' : 'bg-accent-red/20 text-accent-red'
        )}>
          {isBuy ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
          {trade.side.toUpperCase()}
        </span>
      </td>

      {/* Type */}
      <td className="py-4 px-4">
        <span className="text-sm text-text-secondary capitalize">
          {trade.order_type || 'market'}
        </span>
      </td>

      {/* Quantity */}
      <td className="py-4 px-4 text-right">
        <span className="font-mono text-text-primary">{trade.quantity.toFixed(6)}</span>
      </td>

      {/* Price */}
      <td className="py-4 px-4 text-right">
        <span className="font-mono text-text-primary">{formatCurrency(trade.price)}</span>
      </td>

      {/* Fee */}
      <td className="py-4 px-4 text-right">
        <span className="font-mono text-accent-amber">{formatCurrency(trade.fee)}</span>
      </td>

      {/* Total */}
      <td className="py-4 px-4 text-right">
        <div className="font-mono text-text-primary">{formatCurrency(total)}</div>
        <p className="text-xs text-text-muted">+{formatCurrency(trade.fee)} fee</p>
      </td>

      {/* Status */}
      <td className="py-4 px-4 text-right">
        <span className={clsx(
          'px-2 py-1 rounded-full text-xs font-medium',
          trade.status === 'filled' || trade.status === 'executed'
            ? 'bg-accent-emerald/20 text-accent-emerald'
            : trade.status === 'pending'
              ? 'bg-accent-amber/20 text-accent-amber'
              : 'bg-text-dim/20 text-text-muted'
        )}>
          {trade.status.toUpperCase()}
        </span>
        {trade.is_paper && (
          <span className="ml-2 px-2 py-1 rounded-full text-xs bg-accent-cyan/20 text-accent-cyan">
            PAPER
          </span>
        )}
      </td>
    </motion.tr>
  )
}

export default function HistoryPage() {
  const [trades, setTrades] = useState<Trade[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [sortField, setSortField] = useState<'time' | 'coin' | 'quantity' | 'price'>('time')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')
  const [page, setPage] = useState(1)
  const [dateFilter, setDateFilter] = useState<'all' | 'today' | 'week' | 'month'>('all')
  const pageSize = 20
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
      if (message.event_type?.includes('trade')) {
        fetchTrades()
      }
    },
  })

  async function fetchTrades() {
    try {
      const data = await api.getTrades(500)
      setTrades(data)
    } catch (error) {
      console.error('Failed to fetch trades:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTrades()
  }, [])

  // Filter trades
  const filteredTrades = trades.filter(trade => {
    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      if (!trade.coin.toLowerCase().includes(query) && 
          !trade.side.toLowerCase().includes(query)) {
        return false
      }
    }

    // Date filter
    if (dateFilter !== 'all') {
      const tradeDate = new Date(trade.executed_at || trade.created_at)
      const now = new Date()
      
      if (dateFilter === 'today') {
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
        if (tradeDate < today) return false
      } else if (dateFilter === 'week') {
        const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
        if (tradeDate < weekAgo) return false
      } else if (dateFilter === 'month') {
        const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
        if (tradeDate < monthAgo) return false
      }
    }

    return true
  })

  // Sort trades
  const sortedTrades = [...filteredTrades].sort((a, b) => {
    let comparison = 0
    switch (sortField) {
      case 'time':
        comparison = new Date(a.executed_at || a.created_at).getTime() - 
                     new Date(b.executed_at || b.created_at).getTime()
        break
      case 'coin':
        comparison = a.coin.localeCompare(b.coin)
        break
      case 'quantity':
        comparison = a.quantity - b.quantity
        break
      case 'price':
        comparison = a.price - b.price
        break
    }
    return sortDirection === 'asc' ? comparison : -comparison
  })

  // Paginate
  const totalPages = Math.ceil(sortedTrades.length / pageSize)
  const paginatedTrades = sortedTrades.slice((page - 1) * pageSize, page * pageSize)

  // Calculate summary
  const totalVolume = trades.reduce((sum, t) => sum + (t.quantity * t.price), 0)
  const totalFees = trades.reduce((sum, t) => sum + t.fee, 0)
  const buyTrades = trades.filter(t => t.side.toLowerCase() === 'buy').length
  const sellTrades = trades.filter(t => t.side.toLowerCase() === 'sell').length

  const handleSort = (field: typeof sortField) => {
    if (sortField === field) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
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
              Trade History
            </motion.h1>
            <p className="text-xs text-text-muted mt-1">
              Complete log of all executed trades
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={fetchTrades}
              className="btn-ghost p-2"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button className="btn-ghost p-2">
              <Download className="w-4 h-4" />
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
            <span className="text-label block mb-2">Total Trades</span>
            <div className="text-2xl font-mono font-semibold text-text-primary">
              {trades.length}
            </div>
            <p className="text-xs text-text-muted mt-1">
              {buyTrades} buys · {sellTrades} sells
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card p-5"
          >
            <span className="text-label block mb-2">Total Volume</span>
            <div className="text-2xl font-mono font-semibold text-text-primary">
              {formatCurrency(totalVolume)}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card p-5"
          >
            <span className="text-label block mb-2">Total Fees</span>
            <div className="text-2xl font-mono font-semibold text-accent-amber">
              {formatCurrency(totalFees)}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="glass-card p-5"
          >
            <span className="text-label block mb-2">Avg Trade Size</span>
            <div className="text-2xl font-mono font-semibold text-text-primary">
              {trades.length > 0 ? formatCurrency(totalVolume / trades.length) : '$0.00'}
            </div>
          </motion.div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-4 mb-6">
          {/* Search */}
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-text-dim" />
            <input
              type="text"
              placeholder="Search by coin..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-void/50 border border-glass-border rounded-lg text-sm text-text-primary placeholder:text-text-dim focus:outline-none focus:border-accent-cyan/50"
            />
          </div>

          {/* Date Filter */}
          <div className="flex gap-1 bg-void/50 p-1 rounded-lg">
            {(['all', 'today', 'week', 'month'] as const).map((f) => (
              <button
                key={f}
                onClick={() => { setDateFilter(f); setPage(1) }}
                className={clsx(
                  'px-3 py-1.5 text-xs font-medium rounded-md transition-all',
                  dateFilter === f
                    ? 'bg-accent-cyan/20 text-accent-cyan border border-accent-cyan/30'
                    : 'text-text-muted hover:text-text-secondary'
                )}
              >
                {f === 'all' ? 'All Time' : f === 'today' ? 'Today' : f === 'week' ? '7 Days' : '30 Days'}
              </button>
            ))}
          </div>
        </div>

        {/* Trades Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card overflow-hidden"
        >
          {loading ? (
            <div className="p-12 text-center">
              <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <p className="text-text-muted">Loading trades...</p>
            </div>
          ) : paginatedTrades.length > 0 ? (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-glass-border bg-void/30">
                      <th 
                        className="text-left py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider cursor-pointer hover:text-text-secondary"
                        onClick={() => handleSort('time')}
                      >
                        <div className="flex items-center gap-1">
                          Time
                          <ArrowUpDown className="w-3 h-3" />
                        </div>
                      </th>
                      <th 
                        className="text-left py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider cursor-pointer hover:text-text-secondary"
                        onClick={() => handleSort('coin')}
                      >
                        <div className="flex items-center gap-1">
                          Coin
                          <ArrowUpDown className="w-3 h-3" />
                        </div>
                      </th>
                      <th className="text-left py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                        Side
                      </th>
                      <th className="text-left py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                        Type
                      </th>
                      <th 
                        className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider cursor-pointer hover:text-text-secondary"
                        onClick={() => handleSort('quantity')}
                      >
                        <div className="flex items-center justify-end gap-1">
                          Quantity
                          <ArrowUpDown className="w-3 h-3" />
                        </div>
                      </th>
                      <th 
                        className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider cursor-pointer hover:text-text-secondary"
                        onClick={() => handleSort('price')}
                      >
                        <div className="flex items-center justify-end gap-1">
                          Price
                          <ArrowUpDown className="w-3 h-3" />
                        </div>
                      </th>
                      <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                        Fee
                      </th>
                      <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                        Total
                      </th>
                      <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedTrades.map((trade, index) => (
                      <TradeRow key={trade.id} trade={trade} index={index} />
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between p-4 border-t border-glass-border">
                  <p className="text-sm text-text-muted">
                    Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, sortedTrades.length)} of {sortedTrades.length} trades
                  </p>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={page === 1}
                      className="p-2 rounded-lg hover:bg-glass-bg disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <span className="text-sm text-text-secondary">
                      Page {page} of {totalPages}
                    </span>
                    <button
                      onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                      disabled={page === totalPages}
                      className="p-2 rounded-lg hover:bg-glass-bg disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="p-12 text-center">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-void/50 flex items-center justify-center">
                <Calendar className="w-8 h-8 text-text-dim" />
              </div>
              <p className="text-text-muted font-medium mb-1">Keine Trades</p>
              <p className="text-text-dim text-sm">
                {searchQuery 
                  ? 'Keine Trades gefunden für diese Suche.'
                  : 'Der Bot hat noch keine Trades ausgeführt.'}
              </p>
            </div>
          )}
        </motion.div>
      </main>
    </div>
  )
}

