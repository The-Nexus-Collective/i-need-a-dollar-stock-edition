'use client'

import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  BookOpen, 
  Clock, 
  TrendingUp,
  TrendingDown,
  RefreshCw,
  ChevronRight,
  Bot,
  Sparkles,
  Search,
  Brain,
  Target,
  AlertCircle,
  Code,
} from 'lucide-react'
import { clsx } from 'clsx'
import ReactMarkdown from 'react-markdown'

import { Sidebar } from '@/components/Sidebar'
import { MobileHeader } from '@/components/MobileHeader'
import { useWebSocket } from '@/lib/websocket'

// API URL
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081'

interface LogEntry {
  id: string
  timestamp: string
  cycle_number: number
  analysis_text: string
  market_summary: string
  positions_closed: Array<{ symbol: string; reason: string; pnl: number }>
  positions_opened: Array<{ symbol: string; direction: string; conviction: number; leverage: number; reason: string }>
  positions_kept: string[]
  coins_analyzed: number
  coins_skipped: number
  tokens_used: number
  total_equity: number
  unrealized_pnl: number
  open_positions: number
  raw_prompt?: string
  raw_response?: string
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

function formatTimeAgo(timestamp: string): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  
  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}h ago`
  
  return date.toLocaleDateString()
}

function LogEntryCard({ entry, isExpanded, onToggle }: { 
  entry: LogEntry
  isExpanded: boolean
  onToggle: () => void 
}) {
  const totalActions = entry.positions_opened.length + entry.positions_closed.length
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card overflow-hidden"
    >
      {/* Header - Always visible */}
      <div 
        className="p-5 cursor-pointer hover:bg-glass-bg/50 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-4">
            {/* Cycle badge */}
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-accent-cyan/20 to-accent-emerald/20 flex items-center justify-center border border-accent-cyan/30">
              <span className="text-lg font-mono font-bold text-accent-cyan">
                #{entry.cycle_number}
              </span>
            </div>
            
            <div className="flex-1">
              {/* Market Summary */}
              <p className="text-text-primary font-medium mb-1">
                {entry.market_summary || 'Portfolio Update'}
              </p>
              
              {/* Meta info */}
              <div className="flex flex-wrap items-center gap-4 text-xs text-text-muted">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {formatTimeAgo(entry.timestamp)}
                </span>
                <span className="flex items-center gap-1">
                  <Brain className="w-3 h-3" />
                  {entry.coins_analyzed} coins analyzed
                </span>
                <span className="flex items-center gap-1">
                  <Target className="w-3 h-3" />
                  {entry.open_positions} open positions
                </span>
              </div>
            </div>
          </div>
          
          {/* Actions summary */}
          <div className="flex items-center gap-3">
            {entry.positions_opened.length > 0 && (
              <div className="flex items-center gap-1 px-2 py-1 rounded bg-accent-emerald/20 text-accent-emerald text-xs font-medium">
                <TrendingUp className="w-3 h-3" />
                +{entry.positions_opened.length}
              </div>
            )}
            {entry.positions_closed.length > 0 && (
              <div className="flex items-center gap-1 px-2 py-1 rounded bg-accent-red/20 text-accent-red text-xs font-medium">
                <TrendingDown className="w-3 h-3" />
                -{entry.positions_closed.length}
              </div>
            )}
            <ChevronRight className={clsx(
              'w-5 h-5 text-text-dim transition-transform',
              isExpanded && 'rotate-90'
            )} />
          </div>
        </div>
        
        {/* Quick stats row */}
        <div className="flex items-center gap-6 mt-4 pt-4 border-t border-glass-border/50">
          <div>
            <span className="text-label block text-xs">Equity</span>
            <span className="text-text-primary font-mono font-medium">
              {formatCurrency(entry.total_equity)}
            </span>
          </div>
          <div>
            <span className="text-label block text-xs">Unrealized PnL</span>
            <span className={clsx(
              'font-mono font-medium',
              entry.unrealized_pnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'
            )}>
              {formatCurrency(entry.unrealized_pnl, true)}
            </span>
          </div>
          <div>
            <span className="text-label block text-xs">Tokens Used</span>
            <span className="text-text-secondary font-mono text-sm">
              {entry.tokens_used.toLocaleString()}
            </span>
          </div>
        </div>
      </div>
      
      {/* Expanded content */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5 space-y-4">
              {/* Analysis text from Grok */}
              <div className="p-4 bg-void/50 rounded-xl border border-glass-border">
                <div className="flex items-center gap-2 mb-3">
                  <Bot className="w-4 h-4 text-accent-cyan" />
                  <span className="text-sm font-medium text-text-primary">Grok's Analysis</span>
                  <Sparkles className="w-3 h-3 text-accent-amber" />
                </div>
                <div className="prose prose-invert prose-sm max-w-none text-text-secondary">
                  <ReactMarkdown>
                    {entry.analysis_text}
                  </ReactMarkdown>
                </div>
              </div>
              
              {/* Positions Opened */}
              {entry.positions_opened.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-accent-emerald mb-2 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4" />
                    Positions Opened ({entry.positions_opened.length})
                  </h4>
                  <div className="grid gap-2">
                    {entry.positions_opened.map((pos, i) => (
                      <div key={i} className="p-3 bg-accent-emerald/10 rounded-lg border border-accent-emerald/20">
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-semibold text-text-primary">{pos.symbol}</span>
                          <div className="flex items-center gap-2">
                            <span className={clsx(
                              'px-2 py-0.5 rounded text-xs font-medium',
                              pos.direction === 'LONG' 
                                ? 'bg-accent-emerald/20 text-accent-emerald'
                                : 'bg-accent-red/20 text-accent-red'
                            )}>
                              {pos.direction}
                            </span>
                            <span className="text-xs text-text-muted">{pos.leverage}x</span>
                            <span className="text-xs text-accent-cyan">{pos.conviction}% conviction</span>
                          </div>
                        </div>
                        <p className="text-xs text-text-secondary">{pos.reason}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Positions Closed */}
              {entry.positions_closed.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-accent-red mb-2 flex items-center gap-2">
                    <TrendingDown className="w-4 h-4" />
                    Positions Closed ({entry.positions_closed.length})
                  </h4>
                  <div className="grid gap-2">
                    {entry.positions_closed.map((pos, i) => (
                      <div key={i} className="p-3 bg-accent-red/10 rounded-lg border border-accent-red/20">
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-semibold text-text-primary">{pos.symbol}</span>
                          <span className={clsx(
                            'font-mono text-sm',
                            pos.pnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'
                          )}>
                            {formatCurrency(pos.pnl, true)}
                          </span>
                        </div>
                        <p className="text-xs text-text-secondary">{pos.reason}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Positions Kept */}
              {entry.positions_kept.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-text-secondary mb-2 flex items-center gap-2">
                    <Target className="w-4 h-4" />
                    Positions Kept ({entry.positions_kept.length})
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {entry.positions_kept.map((symbol, i) => (
                      <span key={i} className="px-2 py-1 bg-void/50 rounded text-xs text-text-muted border border-glass-border">
                        {symbol}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Debug: Raw Grok Prompt & Response */}
              {(entry.raw_prompt || entry.raw_response) && (
                <details className="mt-4 pt-4 border-t border-glass-border/50 group">
                  <summary className="cursor-pointer text-xs text-text-dim hover:text-text-muted flex items-center gap-2 select-none">
                    <Code className="w-3 h-3" />
                    <span>Debug: Raw Grok Prompt & Response</span>
                    <ChevronRight className="w-3 h-3 transition-transform group-open:rotate-90" />
                  </summary>
                  <div className="mt-3 space-y-3">
                    {entry.raw_prompt && (
                      <div>
                        <div className="text-xs text-text-dim mb-1 font-medium">Prompt sent to Grok:</div>
                        <pre className="p-3 bg-void/80 rounded-lg border border-glass-border text-xs text-text-muted overflow-x-auto max-h-64 overflow-y-auto whitespace-pre-wrap break-words font-mono">
                          {entry.raw_prompt}
                        </pre>
                      </div>
                    )}
                    {entry.raw_response && (
                      <div>
                        <div className="text-xs text-text-dim mb-1 font-medium">Raw response from Grok:</div>
                        <pre className="p-3 bg-void/80 rounded-lg border border-glass-border text-xs text-text-muted overflow-x-auto max-h-64 overflow-y-auto whitespace-pre-wrap break-words font-mono">
                          {entry.raw_response}
                        </pre>
                      </div>
                    )}
                  </div>
                </details>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

export default function LogbookPage() {
  const [entries, setEntries] = useState<LogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [stats, setStats] = useState<{
    total_entries: number
    total_cycles: number
    total_tokens_used: number
  } | null>(null)

  const { isConnected } = useWebSocket({
    channel: 'all',
    onMessage: (message) => {
      if (message.type === 'logbook_entry') {
        // Add new entry to the top
        setEntries(prev => [message.data, ...prev.slice(0, 49)])
      }
    },
  })

  async function fetchEntries() {
    try {
      setLoading(true)
      const response = await fetch(`${API_URL}/api/logbook?limit=50`)
      if (response.ok) {
        const data = await response.json()
        setEntries(data)
      }
    } catch (error) {
      console.error('Failed to fetch logbook entries:', error)
    } finally {
      setLoading(false)
    }
  }

  async function fetchStats() {
    try {
      const response = await fetch(`${API_URL}/api/logbook/stats`)
      if (response.ok) {
        const data = await response.json()
        setStats(data)
      }
    } catch (error) {
      console.error('Failed to fetch logbook stats:', error)
    }
  }

  useEffect(() => {
    fetchEntries()
    fetchStats()
  }, [])

  // Filter entries
  const filteredEntries = entries.filter(entry => {
    if (!searchQuery) return true
    const query = searchQuery.toLowerCase()
    return (
      entry.analysis_text.toLowerCase().includes(query) ||
      entry.market_summary.toLowerCase().includes(query) ||
      entry.positions_opened.some(p => p.symbol.toLowerCase().includes(query)) ||
      entry.positions_closed.some(p => p.symbol.toLowerCase().includes(query))
    )
  })

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
          title="Logbook"
        />

        <div className="p-4 md:p-6 lg:p-8">
        {/* Header */}
        <header className="flex flex-col sm:flex-row sm:items-center justify-between mb-6 gap-4">
          <div>
            <motion.h1 
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="text-xl sm:text-2xl font-semibold text-text-primary tracking-tight flex items-center gap-3"
            >
              <BookOpen className="w-6 sm:w-7 h-6 sm:h-7 text-accent-cyan" />
              Trading Logbook
            </motion.h1>
            <p className="text-xs text-text-muted mt-1">
              Grok's analysis and trading decisions for each 10-minute cycle
            </p>
          </div>

          <button
            onClick={fetchEntries}
            className="btn-ghost p-2 min-h-[44px] min-w-[44px] flex items-center justify-center self-start sm:self-auto"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </header>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card p-5"
          >
            <span className="text-label block mb-2">Total Cycles</span>
            <div className="text-2xl font-mono font-semibold text-text-primary">
              {stats?.total_cycles ?? 0}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card p-5"
          >
            <span className="text-label block mb-2">Logged Entries</span>
            <div className="text-2xl font-mono font-semibold text-accent-cyan">
              {stats?.total_entries ?? 0}
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card p-5"
          >
            <span className="text-label block mb-2">Tokens Used</span>
            <div className="text-2xl font-mono font-semibold text-accent-amber">
              {(stats?.total_tokens_used ?? 0).toLocaleString()}
            </div>
          </motion.div>
        </div>

        {/* Search */}
        <div className="mb-6">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-text-dim" />
            <input
              type="text"
              placeholder="Search entries..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-void/50 border border-glass-border rounded-lg text-sm text-text-primary placeholder:text-text-dim focus:outline-none focus:border-accent-cyan/50"
            />
          </div>
        </div>

        {/* Entries List */}
        <div className="space-y-4">
          {loading ? (
            <div className="glass-card p-12 text-center">
              <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin mx-auto mb-4" />
              <p className="text-text-muted">Loading logbook entries...</p>
            </div>
          ) : filteredEntries.length > 0 ? (
            filteredEntries.map((entry) => (
              <LogEntryCard
                key={entry.id}
                entry={entry}
                isExpanded={expandedId === entry.id}
                onToggle={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
              />
            ))
          ) : (
            <div className="glass-card p-12 text-center">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-void/50 flex items-center justify-center">
                <AlertCircle className="w-8 h-8 text-text-dim" />
              </div>
              <p className="text-text-muted font-medium mb-1">No Entries Yet</p>
              <p className="text-text-dim text-sm">
                {searchQuery 
                  ? 'No entries match your search.'
                  : 'The bot hasn\'t completed any trading cycles yet.'}
              </p>
            </div>
          )}
        </div>
        </div>
      </main>
    </div>
  )
}

