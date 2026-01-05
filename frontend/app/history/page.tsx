'use client'

import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
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
  ChevronDown,
  ChevronUp,
  ArrowUpDown,
  Plus,
  Minus,
  X,
  ArrowRight,
  DollarSign,
  Wallet,
  PiggyBank,
  Receipt,
  CheckCircle2,
  AlertTriangle,
  BookOpen,
  FileSpreadsheet,
} from 'lucide-react'
import { clsx } from 'clsx'

import { Sidebar } from '@/components/Sidebar'
import { MobileHeader } from '@/components/MobileHeader'
import { api } from '@/lib/api'
import { useWebSocket } from '@/lib/websocket'

// Types matching the backend DTOs
interface LedgerEntry {
  id: number
  transactionId: string
  timestamp: string
  transactionType: string
  positionId: string | null
  account: string
  debit: number
  credit: number
  runningBalance: number | null
  description: string | null
  isDebit: boolean
  accountDisplay: string
  netEffect: number
}

interface Transaction {
  transactionId: string
  timestamp: string
  transactionType: 'OPEN' | 'CLOSE' | 'EXTEND' | 'REDUCE' | 'RESET' | 'MARGIN_CALL'
  transactionTypeDisplay: string
  positionId: string | null
  symbol: string | null
  direction: string | null
  price: number | null
  quantity: number | null
  sizeUsdt: number | null
  leverage: number | null
  conviction: number | null
  reason: string | null
  fee: number
  spread: number
  slippage: number
  totalCosts: number
  grossPnl: number
  netPnl: number
  pnlPercent: number
  ledgerEntries: LedgerEntry[] | null
  ledgerEntryCount: number
}

interface AccountBalances {
  cash: number
  positions: number
  realizedPnl: number
  tradingCosts: number
  startingCapital: number
  bookEquity: number
  initialized: boolean
}

interface Reconciliation {
  balanced: boolean
  timestamp: string
  totalDebits: number
  totalCredits: number
  imbalance: number
  discrepancies: string[]
  totalEntries: number
  totalTransactions: number
}

function formatCurrency(value: number | null | undefined, showSign = false): string {
  if (value == null) return '$0.00'
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
  const config: Record<string, { icon: typeof Plus; bg: string; text: string; border: string; label: string }> = {
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
    RESET: {
      icon: RefreshCw,
      bg: 'bg-purple-500/20',
      text: 'text-purple-400',
      border: 'border-purple-500/30',
      label: 'RESET',
    },
    MARGIN_CALL: {
      icon: AlertTriangle,
      bg: 'bg-red-600/30',
      text: 'text-red-400',
      border: 'border-red-500/50',
      label: 'LIQUIDATED',
    },
  }

  const cfg = config[type] || {
    icon: ArrowRight,
    bg: 'bg-glass-bg',
    text: 'text-text-muted',
    border: 'border-glass-border',
    label: type,
  }

  const Icon = cfg.icon

  return (
    <span className={clsx(
      'inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium border',
      cfg.bg, cfg.text, cfg.border
    )}>
      <Icon className="w-3 h-3" />
      {cfg.label}
    </span>
  )
}

// Ledger Entry List Component (expandable)
function LedgerEntryList({ entries }: { entries: LedgerEntry[] }) {
  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      className="bg-void/30 border-t border-glass-border"
    >
      <div className="p-4">
        <div className="flex items-center gap-2 mb-3">
          <BookOpen className="w-4 h-4 text-accent-cyan" />
          <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider">
            Ledger Entries
          </span>
        </div>
        <div className="space-y-2">
          {entries.map((entry) => (
            <div 
              key={entry.id}
              className="flex items-center justify-between p-3 bg-glass-bg/30 rounded-lg border border-glass-border/50"
            >
              <div className="flex items-center gap-3">
                <div className={clsx(
                  'w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold',
                  entry.isDebit 
                    ? 'bg-accent-emerald/20 text-accent-emerald' 
                    : 'bg-accent-red/20 text-accent-red'
                )}>
                  {entry.isDebit ? 'DR' : 'CR'}
                </div>
                <div>
                  <span className="text-sm font-medium text-text-primary">
                    {entry.accountDisplay}
                  </span>
                  <p className="text-xs text-text-muted">
                    {entry.description || entry.transactionType}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <span className={clsx(
                  'font-mono text-sm font-medium',
                  entry.netEffect >= 0 ? 'text-accent-emerald' : 'text-accent-red'
                )}>
                  {formatCurrency(entry.netEffect, true)}
                </span>
                {entry.runningBalance != null && (
                  <p className="text-xs text-text-dim font-mono">
                    Bal: {formatCurrency(entry.runningBalance)}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  )
}

// Transaction Row Component
function TransactionRow({ 
  txn, 
  index,
  onToggleLedger,
  isExpanded,
  loadingLedger
}: { 
  txn: Transaction
  index: number
  onToggleLedger: () => void
  isExpanded: boolean
  loadingLedger: boolean
}) {
  const isLong = txn.direction?.toUpperCase() === 'LONG'
  const symbol = txn.symbol || (txn.transactionType === 'RESET' ? 'System' : 'Unknown')
  const hasPnl = txn.transactionType === 'CLOSE' || txn.transactionType === 'REDUCE'

  return (
    <>
      <motion.tr
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: index * 0.02 }}
        className={clsx(
          'border-b border-glass-border hover:bg-glass-bg/50 transition-colors cursor-pointer',
          isExpanded && 'bg-glass-bg/30'
        )}
        onClick={onToggleLedger}
      >
        {/* Expand indicator */}
        <td className="py-4 px-2 w-8">
          <button className="p-1 hover:bg-glass-bg rounded">
            {loadingLedger ? (
              <div className="w-4 h-4 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
            ) : isExpanded ? (
              <ChevronUp className="w-4 h-4 text-accent-cyan" />
            ) : (
              <ChevronDown className="w-4 h-4 text-text-dim" />
            )}
          </button>
        </td>

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
          <span className="font-semibold text-text-primary">
            {symbol.replace('USDT', '')}
          </span>
          {txn.leverage && txn.direction && (
            <p className="text-xs text-text-muted">
              {txn.leverage}x {isLong ? 'Long' : 'Short'}
            </p>
          )}
        </td>

        {/* Transaction Type */}
        <td className="py-4 px-4">
          <TransactionTypeBadge type={txn.transactionType} />
        </td>

        {/* Size */}
        <td className="py-4 px-4 text-right">
          <span className="font-mono text-text-primary">
            {formatCurrency(txn.sizeUsdt)}
          </span>
        </td>

        {/* Costs */}
        <td className="py-4 px-4 text-right">
          {txn.totalCosts > 0 ? (
            <span className="font-mono text-accent-amber text-sm">
              -{formatCurrency(txn.totalCosts)}
            </span>
          ) : (
            <span className="text-text-dim">—</span>
          )}
        </td>

        {/* PnL */}
        <td className="py-4 px-4 text-right">
          {hasPnl && txn.netPnl !== 0 ? (
            <>
              <span className={clsx(
                'font-mono font-medium',
                txn.netPnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'
              )}>
                {formatCurrency(txn.netPnl, true)}
              </span>
              <p className={clsx(
                'text-xs',
                txn.pnlPercent >= 0 ? 'text-accent-emerald/70' : 'text-accent-red/70'
              )}>
                {txn.pnlPercent >= 0 ? '+' : ''}{txn.pnlPercent?.toFixed(2)}%
              </p>
            </>
          ) : (
            <span className="text-text-dim">—</span>
          )}
        </td>

        {/* Conviction */}
        <td className="py-4 px-4 text-right">
          {txn.conviction != null ? (
            <div className="flex items-center justify-end gap-2">
              <div className="w-12 h-1.5 bg-void rounded-full overflow-hidden">
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
          ) : (
            <span className="text-text-dim">—</span>
          )}
        </td>

        {/* Ledger count */}
        <td className="py-4 px-4 text-right">
          <span className="text-xs text-text-dim font-mono">
            {txn.ledgerEntryCount} entries
          </span>
        </td>
      </motion.tr>

      {/* Expanded ledger entries */}
      <AnimatePresence>
        {isExpanded && txn.ledgerEntries && (
          <tr>
            <td colSpan={9} className="p-0">
              <LedgerEntryList entries={txn.ledgerEntries} />
            </td>
          </tr>
        )}
      </AnimatePresence>
    </>
  )
}

// Account Balance Card Component
function BalanceCard({ 
  icon: Icon, 
  label, 
  value, 
  color,
  subtext,
  delay = 0 
}: { 
  icon: typeof DollarSign
  label: string
  value: number
  color: 'cyan' | 'emerald' | 'amber' | 'red' | 'purple'
  subtext?: string
  delay?: number
}) {
  const colorClasses = {
    cyan: 'text-accent-cyan bg-accent-cyan/10 border-accent-cyan/20',
    emerald: 'text-accent-emerald bg-accent-emerald/10 border-accent-emerald/20',
    amber: 'text-accent-amber bg-accent-amber/10 border-accent-amber/20',
    red: 'text-accent-red bg-accent-red/10 border-accent-red/20',
    purple: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className="glass-card p-5"
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-label">{label}</span>
        <div className={clsx('p-2 rounded-lg border', colorClasses[color])}>
          <Icon className="w-4 h-4" />
        </div>
      </div>
      <div className={clsx(
        'text-2xl font-mono font-semibold',
        value >= 0 ? 'text-text-primary' : 'text-accent-red'
      )}>
        {formatCurrency(value, label.includes('PnL'))}
      </div>
      {subtext && (
        <p className="text-xs text-text-muted mt-1">{subtext}</p>
      )}
    </motion.div>
  )
}

export default function HistoryPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [balances, setBalances] = useState<AccountBalances | null>(null)
  const [reconciliation, setReconciliation] = useState<Reconciliation | null>(null)
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [page, setPage] = useState(1)
  const [dateFilter, setDateFilter] = useState<'all' | 'today' | 'week' | 'month'>('all')
  const [typeFilter, setTypeFilter] = useState<'all' | 'OPEN' | 'CLOSE' | 'EXTEND' | 'REDUCE' | 'RESET' | 'MARGIN_CALL'>('all')
  const [expandedTxId, setExpandedTxId] = useState<string | null>(null)
  const [loadingLedger, setLoadingLedger] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const pageSize = 20
  
  const { isConnected } = useWebSocket({
    channel: 'trading',
    onMessage: (message) => {
      if (message.event_type?.includes('trade') || message.event_type?.includes('transaction')) {
        fetchData()
      }
    },
  })

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [txns, acctBalances, reconcileReport] = await Promise.all([
        api.getTransactions(500),
        api.getAccountBalances(),
        api.getReconciliation(),
      ])
      setTransactions(txns as Transaction[])
      setBalances(acctBalances)
      setReconciliation(reconcileReport)
    } catch (error) {
      console.error('Failed to fetch data:', error)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Toggle ledger expansion and fetch detail if needed
  const handleToggleLedger = async (txn: Transaction) => {
    if (expandedTxId === txn.transactionId) {
      setExpandedTxId(null)
      return
    }

    // If we already have ledger entries, just expand
    if (txn.ledgerEntries) {
      setExpandedTxId(txn.transactionId)
      return
    }

    // Fetch full transaction detail
    setLoadingLedger(txn.transactionId)
    try {
      const detail = await api.getTransactionDetail(txn.transactionId)
      // Update the transaction in the list with the ledger entries
      setTransactions(prev => prev.map(t => 
        t.transactionId === txn.transactionId ? { ...t, ledgerEntries: detail.ledgerEntries } : t
      ))
      setExpandedTxId(txn.transactionId)
    } catch (error) {
      console.error('Failed to fetch transaction detail:', error)
    } finally {
      setLoadingLedger(null)
    }
  }

  // Export to CSV
  const handleExport = async () => {
    setExporting(true)
    try {
      const blob = await api.exportTransactions(0, typeFilter !== 'all' ? typeFilter : undefined)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `transactions_${new Date().toISOString().split('T')[0]}.csv`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Failed to export:', error)
    } finally {
      setExporting(false)
    }
  }

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
    if (typeFilter !== 'all' && txn.transactionType !== typeFilter) {
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

  // Paginate
  const totalPages = Math.ceil(filteredTransactions.length / pageSize)
  const paginatedTransactions = filteredTransactions.slice((page - 1) * pageSize, page * pageSize)

  // Calculate transaction type breakdown
  const openCount = transactions.filter(t => t.transactionType === 'OPEN').length
  const closeCount = transactions.filter(t => t.transactionType === 'CLOSE').length
  const extendCount = transactions.filter(t => t.transactionType === 'EXTEND').length
  const reduceCount = transactions.filter(t => t.transactionType === 'REDUCE').length

  return (
    <div className="flex min-h-screen">
      <Sidebar 
        isConnected={isConnected} 
        mobileOpen={mobileMenuOpen}
        onMobileClose={() => setMobileMenuOpen(false)}
      />

      <main className="flex-1 md:ml-[280px] min-w-0">
        {/* Mobile Header */}
        <MobileHeader 
          onMenuClick={() => setMobileMenuOpen(true)}
          isConnected={isConnected}
          title="History"
        />

        <div className="p-4 md:p-6 lg:p-8">
        {/* Header */}
        <header className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
          <div>
            <motion.h1 
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="text-xl sm:text-2xl font-semibold text-text-primary tracking-tight"
            >
              Transaction History
            </motion.h1>
            <p className="text-xs text-text-muted mt-1">
              Unified view of trades and accounting ledger
            </p>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            {/* Reconciliation Status */}
            {reconciliation && (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className={clsx(
                  'flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium',
                  reconciliation.balanced
                    ? 'bg-accent-emerald/20 text-accent-emerald border border-accent-emerald/30'
                    : 'bg-accent-red/20 text-accent-red border border-accent-red/30'
                )}
              >
                {reconciliation.balanced ? (
                  <CheckCircle2 className="w-3.5 h-3.5" />
                ) : (
                  <AlertTriangle className="w-3.5 h-3.5" />
                )}
                <span className="hidden sm:inline">
                  {reconciliation.balanced ? 'Books Balanced' : 'Imbalance Detected'}
                </span>
              </motion.div>
            )}

            <button
              onClick={fetchData}
              className="btn-ghost p-2 min-h-[44px] min-w-[44px] flex items-center justify-center"
              disabled={loading}
            >
              <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />
            </button>
            <button 
              onClick={handleExport}
              className="btn-ghost p-2 min-h-[44px] min-w-[44px] flex items-center justify-center"
              disabled={exporting}
            >
              {exporting ? (
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
              ) : (
                <FileSpreadsheet className="w-4 h-4" />
              )}
            </button>
          </div>
        </header>

        {/* Account Balance Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <BalanceCard
            icon={Wallet}
            label="Cash Balance"
            value={balances?.cash ?? 0}
            color="cyan"
            subtext={balances?.initialized ? 'From ledger' : 'Not initialized'}
            delay={0}
          />
          <BalanceCard
            icon={PiggyBank}
            label="Positions Value"
            value={balances?.positions ?? 0}
            color="purple"
            subtext="Entry cost basis"
            delay={0.05}
          />
          <BalanceCard
            icon={TrendingUp}
            label="Realized PnL"
            value={balances?.realizedPnl ?? 0}
            color={balances?.realizedPnl && balances.realizedPnl >= 0 ? 'emerald' : 'red'}
            subtext="Net of all closed trades"
            delay={0.1}
          />
          <BalanceCard
            icon={Receipt}
            label="Trading Costs"
            value={balances?.tradingCosts ?? 0}
            color="amber"
            subtext="Fees + Spread + Slippage"
            delay={0.15}
          />
        </div>

        {/* Transaction Summary Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card p-4"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-muted">Opens</span>
              <span className="text-lg font-mono font-semibold text-accent-emerald">{openCount}</span>
            </div>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.02 }}
            className="glass-card p-4"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-muted">Closes</span>
              <span className="text-lg font-mono font-semibold text-accent-red">{closeCount}</span>
            </div>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.04 }}
            className="glass-card p-4"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-muted">Extends</span>
              <span className="text-lg font-mono font-semibold text-accent-cyan">{extendCount}</span>
            </div>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.06 }}
            className="glass-card p-4"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs text-text-muted">Reduces</span>
              <span className="text-lg font-mono font-semibold text-accent-amber">{reduceCount}</span>
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
              placeholder="Search by symbol..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-void/50 border border-glass-border rounded-lg text-sm text-text-primary placeholder:text-text-dim focus:outline-none focus:border-accent-cyan/50"
            />
          </div>

          {/* Transaction Type Filter */}
          <div className="flex gap-1 bg-void/50 p-1 rounded-lg flex-wrap">
            {(['all', 'OPEN', 'CLOSE', 'EXTEND', 'REDUCE', 'RESET', 'MARGIN_CALL'] as const).map((f) => (
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
                      f === 'RESET' ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30' :
                      f === 'MARGIN_CALL' ? 'bg-red-600/30 text-red-400 border border-red-500/50' :
                      'bg-accent-cyan/20 text-accent-cyan border border-accent-cyan/30'
                    : 'text-text-muted hover:text-text-secondary'
                )}
              >
                {f === 'all' ? 'All' : f === 'MARGIN_CALL' ? 'Liquidated' : f}
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

        {/* Transactions Table */}
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
                      <th className="py-3 px-2 w-8"></th>
                      <th className="text-left py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                        Time
                      </th>
                      <th className="text-left py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                        Symbol
                      </th>
                      <th className="text-left py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                        Type
                      </th>
                      <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                        Size
                      </th>
                      <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                        Costs
                      </th>
                      <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                        Net PnL
                      </th>
                      <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                        Conviction
                      </th>
                      <th className="text-right py-3 px-4 text-xs font-semibold text-text-muted uppercase tracking-wider">
                        Ledger
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedTransactions.map((txn, index) => (
                      <TransactionRow 
                        key={txn.transactionId} 
                        txn={txn} 
                        index={index}
                        onToggleLedger={() => handleToggleLedger(txn)}
                        isExpanded={expandedTxId === txn.transactionId}
                        loadingLedger={loadingLedger === txn.transactionId}
                      />
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between p-4 border-t border-glass-border">
                  <p className="text-sm text-text-muted">
                    Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, filteredTransactions.length)} of {filteredTransactions.length} transactions
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
                  : 'No transactions have been recorded yet.'}
              </p>
            </div>
          )}
        </motion.div>
        </div>
      </main>
    </div>
  )
}
