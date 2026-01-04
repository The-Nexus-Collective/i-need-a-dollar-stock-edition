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
  Plus,
  Minus,
  X,
  ArrowRight,
} from 'lucide-react'
import { clsx } from 'clsx'

import { Sidebar } from '@/components/Sidebar'
import { api } from '@/lib/api'
import { useWebSocket } from '@/lib/websocket'
import { usePortfolio } from '@/lib/usePortfolio'

// Transaction interface matching the /api/transactions endpoint
interface Transaction {
  id: string
  position_id: string
  symbol: string
  direction: string
  transaction_type: 'OPEN' | 'CLOSE' | 'EXTEND' | 'REDUCE'
  price: number
  quantity: number
  size_usdt: number
  leverage: number
  position_size_before: number
  position_size_after: number
  avg_entry_before: number
  avg_entry_after: number
  realized_pnl: number
  realized_pnl_pct: number
  fee: number
  spread: number
  slippage: number
  reason: string
  conviction: number
  timestamp: string
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

// Transaction type badge component
function TransactionTypeBadge({ type }: { type: string }) {
  const config = {
    OPEN: {
      icon: Plus,
      bg: 'bg-accent-emerald/20',
      text: 'text-accent-emerald',
      border: 'border-accent-emerald/30',
      label: 'OPEN',
    },
    CLOSE: {
      icon: X,
      bg: 'bg-accent-red/20',
      text: 'text-accent-red',
      border: 'border-accent-red/30',
      label: 'CLOSE',
    },
    EXTEND: {
      icon: TrendingUp,
      bg: 'bg-accent-cyan/20',
      text: 'text-accent-cyan',
      border: 'border-accent-cyan/30',
      label: 'EXTEND',
    },
    REDUCE: {
      icon: Minus,
      bg: 'bg-accent-amber/20',
      text: 'text-accent-amber',
      border: 'border-accent-amber/30',
      label: 'REDUCE',
    },
  }[type] || {
    icon: ArrowRight,
    bg: 'bg-glass-bg',
    text: 'text-text-muted',
    border: 'border-glass-border',
    label: type,
  }

  const Icon = config.icon

  return (
    <span className={clsx(
      'inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium border',
      config.bg, config.text, config.border
    )}>
      <Icon className="w-3 h-3" />
      {config.label}
    </span>
  )
}

function TransactionRow({ txn, index }: { txn: Transaction; index: number }) {
  const isLong = txn.direction?.toUpperCase() === 'LONG'
  const symbol = txn.symbol || 'UNKNOWN'
  const hasPnl = txn.transaction_type === 'CLOSE' || txn.transaction_type === 'REDUCE'

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
              {new Date(txn.timestamp).toLocaleTimeString()}
            </span>
            <p className="text-xs text-text-muted">
              {new Date(txn.timestamp).toLocaleDateString()}
            </p>
          </div>
        </div>
      </td>

      {/* Symbol */}
      <td className="py-4 px-4">
        <span className="font-semibold text-text-primary">{symbol.replace('USDT', '')}</span>
        <p className="text-xs text-text-muted">{txn.leverage}x {isLong ? 'Long' : 'Short'}</p>
      </td>

      {/* Transaction Type */}
      <td className="py-4 px-4">
        <TransactionTypeBadge type={txn.transaction_type} />
      </td>

      {/* Price */}
      <td className="py-4 px-4 text-right">
        <span className="font-mono text-text-primary">{formatCurrency(txn.price)}</span>
      </td>

      {/* Size */}
      <td className="py-4 px-4 text-right">
        <span className="font-mono text-text-primary">{formatCurrency(txn.size_usdt)}</span>
        {(txn.transaction_type === 'EXTEND' || txn.transaction_type === 'REDUCE') && (
          <p className="text-xs text-text-muted">
            {formatCurrency(txn.position_size_before)} → {formatCurrency(txn.position_size_after)}
          </p>
        )}
      </td>

      {/* PnL */}
      <td className="py-4 px-4 text-right">
        {hasPnl && txn.realized_pnl !== 0 ? (
          <>
            <span className={clsx(
              'font-mono font-medium',
              txn.realized_pnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'
            )}>
              {formatCurrency(txn.realized_pnl, true)}
            </span>
            <p className={clsx(
              'text-xs',
              txn.realized_pnl_pct >= 0 ? 'text-accent-emerald/70' : 'text-accent-red/70'
            )}>
              {txn.realized_pnl_pct >= 0 ? '+' : ''}{txn.realized_pnl_pct.toFixed(2)}%
            </p>
          </>
        ) : (
          <span className="text-text-dim">—</span>
        )}
      </td>

      {/* Conviction */}
      <td className="py-4 px-4 text-right">
        <div className="flex items-center justify-end gap-2">
          <div className="w-16 h-1.5 bg-void rounded-full overflow-hidden">
            <div 
              className={clsx(
                'h-full rounded-full',
                txn.conviction >= 80 ? 'bg-accent-emerald' :
                txn.conviction >= 60 ? 'bg-accent-cyan' :
                'bg-accent-amber'
              )}
              style={{ width: `${txn.conviction}%` }}
            />
          </div>
          <span className="text-xs font-mono text-text-secondary w-8">
            {txn.conviction}%
          </span>
        </div>
      </td>

      {/* Reason */}
      <td className="py-4 px-4 max-w-[200px]">
        <p className="text-xs text-text-muted truncate" title={txn.reason}>
          {txn.reason || '—'}
        </p>
      </td>
    </motion.tr>
  )
}

export default function HistoryPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [sortField, setSortField] = useState<'time' | 'symbol' | 'pnl' | 'size'>('time')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')
  const [page, setPage] = useState(1)
  const [dateFilter, setDateFilter] = useState<'all' | 'today' | 'week' | 'month'>('all')
  const [typeFilter, setTypeFilter] = useState<'all' | 'OPEN' | 'CLOSE' | 'EXTEND' | 'REDUCE'>('all')
  const pageSize = 20
  
  // Get portfolio stats from backend
  const { portfolio } = usePortfolio()

  const { isConnected } = useWebSocket({
    channel: 'trading',
    onMessage: (message) => {
      if (message.event_type?.includes('trade') || message.event_type?.includes('transaction')) {
        fetchTransactions()
      }
    },
  })

  async function fetchTransactions() {
    try {
      const data = await api.getTransactions(500)
      setTransactions(data as Transaction[])
    } catch (error) {
      console.error('Failed to fetch transactions:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchTransactions()
  }, [])

  // Filter transactions
  const filteredTransactions = transactions.filter(txn => {
    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      const symbol = txn.symbol?.toLowerCase() || ''
      const direction = txn.direction?.toLowerCase() || ''
      if (!symbol.includes(query) && !direction.includes(query)) {
        return false
      }
    }

    // Transaction type filter
    if (typeFilter !== 'all' && txn.transaction_type !== typeFilter) {
      return false
    }

    // Date filter
    if (dateFilter !== 'all') {
      const txnDate = new Date(txn.timestamp)
      const now = new Date()
      
      if (dateFilter === 'today') {
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
        if (txnDate < today) return false
      } else if (dateFilter === 'week') {
        const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
        if (txnDate < weekAgo) return false
      } else if (dateFilter === 'month') {
        const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
        if (txnDate < monthAgo) return false
      }
    }

    return true
  })

  // Sort transactions
  const sortedTransactions = [...filteredTransactions].sort((a, b) => {
    let comparison = 0
    switch (sortField) {
      case 'time':
        comparison = new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        break
      case 'symbol':
        comparison = (a.symbol || '').localeCompare(b.symbol || '')
        break
      case 'pnl':
        comparison = (a.realized_pnl || 0) - (b.realized_pnl || 0)
        break
      case 'size':
        comparison = (a.size_usdt || 0) - (b.size_usdt || 0)
        break
    }
    return sortDirection === 'asc' ? comparison : -comparison
  })

  // Paginate
  const totalPages = Math.ceil(sortedTransactions.length / pageSize)
  const paginatedTransactions = sortedTransactions.slice((page - 1) * pageSize, page * pageSize)

  // Use portfolio stats from backend
  const totalPnL = portfolio.totalPnl
  const winRate = portfolio.winRate
  const winningTrades = portfolio.winningTrades
  const totalTrades = portfolio.totalTrades
  
  // Calculate transaction type breakdown
  const openCount = transactions.filter(t => t.transaction_type === 'OPEN').length
  const closeCount = transactions.filter(t => t.transaction_type === 'CLOSE').length
  const extendCount = transactions.filter(t => t.transaction_type === 'EXTEND').length
  const reduceCount = transactions.filter(t => t.transaction_type === 'REDUCE').length

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
              Transaction History
            </motion.h1>
            <p className="text-xs text-text-muted mt-1">
              Complete log of all position transactions
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={fetchTransactions}
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
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card p-5"
          >
            <span className="text-label block mb-2">Total Transactions</span>
            <div className="text-2xl font-mono font-semibold text-text-primary">
              {transactions.length}
            </div>
            <div className="flex gap-2 mt-2 flex-wrap">
              <span className="text-xs px-1.5 py-0.5 rounded bg-accent-emerald/20 text-accent-emerald">{openCount} opens</span>
              <span className="text-xs px-1.5 py-0.5 rounded bg-accent-red/20 text-accent-red">{closeCount} closes</span>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="glass-card p-5"
          >
            <span className="text-label block mb-2">Scaling</span>
            <div className="text-2xl font-mono font-semibold text-text-primary">
              {extendCount + reduceCount}
            </div>
            <div className="flex gap-2 mt-2 flex-wrap">
              <span className="text-xs px-1.5 py-0.5 rounded bg-accent-cyan/20 text-accent-cyan">{extendCount} extends</span>
              <span className="text-xs px-1.5 py-0.5 rounded bg-accent-amber/20 text-accent-amber">{reduceCount} reduces</span>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card p-5"
          >
            <span className="text-label block mb-2">Total PnL</span>
            <div className={clsx(
              'text-2xl font-mono font-semibold',
              totalPnL >= 0 ? 'text-accent-emerald' : 'text-accent-red'
            )}>
              {formatCurrency(totalPnL, true)}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="glass-card p-5"
          >
            <span className="text-label block mb-2">Win Rate</span>
            <div className={clsx(
              'text-2xl font-mono font-semibold',
              winRate >= 50 ? 'text-accent-emerald' : 'text-accent-amber'
            )}>
              {winRate.toFixed(1)}%
            </div>
            <p className="text-xs text-text-muted mt-1">
              {winningTrades} / {totalTrades} winning
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card p-5"
          >
            <span className="text-label block mb-2">Deployment</span>
            <div className="text-2xl font-mono font-semibold text-text-primary">
              {(portfolio as any).deployment_percent?.toFixed(1) || '0.0'}%
            </div>
            <p className="text-xs text-text-muted mt-1">
              Target: 75%
            </p>
          </motion.div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-4 mb-6">
          {/* Search */}
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-text-dim" />
            <input
              type="text"
              placeholder="Search by symbol..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-void/50 border border-glass-border rounded-lg text-sm text-text-primary placeholder:text-text-dim focus:outline-none focus:border-accent-cyan/50"
            />
          </div>

          {/* Transaction Type Filter */}
          <div className="flex gap-1 bg-void/50 p-1 rounded-lg">
            {(['all', 'OPEN', 'CLOSE', 'EXTEND', 'REDUCE'] as const).map((f) => (
              <button
                key={f}
                onClick={() => { setTypeFilter(f); setPage(1) }}
                className={clsx(
                  'px-3 py-1.5 text-xs font-medium rounded-md transition-all',
                  typeFilter === f
                    ? f === 'OPEN' ? 'bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/30' :
                      f === 'CLOSE' ? 'bg-accent-red/20 text-accent-red border border-accent-red/30' :
                      f === 'EXTEND' ? 'bg-accent-cyan/20 text-accent-cyan border border-accent-cyan/30' :
                      f === 'REDUCE' ? 'bg-accent-amber/20 text-accent-amber border border-accent-amber/30' :
                      'bg-accent-cyan/20 text-accent-cyan border border-accent-cyan/30'
                    : 'text-text-muted hover:text-text-secondary'
                )}
              >
                {f === 'all' ? 'All' : f}
              </button>
            ))}
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
              <p className="text-text-muted">Loading transactions...</p>
            </div>
          ) : paginatedTransactions.length > 0 ? (
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
                        onClick={() => handleSort('symbol')}
                      >
                        <div className="flex items-center gap-1">
                          Symbol
                          <ArrowUpDown className="w-3 h-3" />
                        </div>
                      </th>
                      <th className="text-left py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                        Type
                      </th>
                      <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                        Price
                      </th>
                      <th 
                        className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider cursor-pointer hover:text-text-secondary"
                        onClick={() => handleSort('size')}
                      >
                        <div className="flex items-center justify-end gap-1">
                          Size
                          <ArrowUpDown className="w-3 h-3" />
                        </div>
                      </th>
                      <th 
                        className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider cursor-pointer hover:text-text-secondary"
                        onClick={() => handleSort('pnl')}
                      >
                        <div className="flex items-center justify-end gap-1">
                          PnL
                          <ArrowUpDown className="w-3 h-3" />
                        </div>
                      </th>
                      <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                        Conviction
                      </th>
                      <th className="text-left py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                        Reason
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedTransactions.map((txn, index) => (
                      <TransactionRow key={txn.id} txn={txn} index={index} />
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between p-4 border-t border-glass-border">
                  <p className="text-sm text-text-muted">
                    Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, sortedTransactions.length)} of {sortedTransactions.length} transactions
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
              <p className="text-text-muted font-medium mb-1">No Transactions</p>
              <p className="text-text-dim text-sm">
                {searchQuery 
                  ? 'No transactions found for this search.'
                  : 'The bot has not executed any transactions yet.'}
              </p>
            </div>
          )}
        </motion.div>
      </main>
    </div>
  )
}
