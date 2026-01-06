'use client'

import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import {
  Card,
  Title,
  Text,
  Badge,
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
  TextInput,
  Select,
  SelectItem,
  Button,
} from '@tremor/react'
import {
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  MagnifyingGlassIcon,
  BanknotesIcon,
  CalculatorIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
} from '@heroicons/react/24/solid'
import { Sidebar } from '@/components/Sidebar'
import { MobileHeader } from '@/components/MobileHeader'

interface AccountingBreakdown {
  startingCapital: number
  cashBalance: number
  positionsValue: number
  realizedPnl: number
  costBreakdown: {
    totalTradingCosts: number
    fees: number
    spread: number
    slippage: number
  }
  bookEquity: number
  expectedEquity: number
  equityDiscrepancy: number
  accountBalances: Record<string, number>
  reconciliation: {
    balanced: boolean
    totalDebits: number
    totalCredits: number
    imbalance: number
    discrepancies: string[]
  }
  totalLedgerEntries: number
  totalTransactions: number
  initialized: boolean
  timestamp: string
}

interface AuditEntry {
  id: number
  timestamp: string
  event_type: string
  actor: string
  action: string
  entity_type: string
  entity_id: string
  reasoning: string
  hash: string
}

interface ChainVerification {
  valid: boolean
  checked: number
  errors: Array<{
    id: number
    type: string
  }>
}

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [verification, setVerification] = useState<ChainVerification | null>(null)
  const [verifying, setVerifying] = useState(false)
  const [breakdown, setBreakdown] = useState<AccountingBreakdown | null>(null)
  const [breakdownLoading, setBreakdownLoading] = useState(true)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  
  // Filters
  const [eventTypeFilter, setEventTypeFilter] = useState<string>('')
  const [actorFilter, setActorFilter] = useState<string>('')
  const [searchQuery, setSearchQuery] = useState<string>('')

  useEffect(() => {
    fetchAuditLog()
    fetchAccountingBreakdown()
  }, [eventTypeFilter])

  async function fetchAuditLog() {
    try {
      setLoading(true)
      const data = await api.getAuditLog({
        event_type: eventTypeFilter || undefined,
        limit: 200,
      })
      setEntries(data)
    } catch (error) {
      console.error('Failed to fetch audit log:', error)
    } finally {
      setLoading(false)
    }
  }

  async function fetchAccountingBreakdown() {
    try {
      setBreakdownLoading(true)
      const data = await api.getAccountingBreakdown()
      setBreakdown(data)
    } catch (error) {
      console.error('Failed to fetch accounting breakdown:', error)
    } finally {
      setBreakdownLoading(false)
    }
  }

  async function verifyChain() {
    try {
      setVerifying(true)
      const result = await api.verifyAuditChain(1000)
      setVerification(result)
    } catch (error) {
      console.error('Failed to verify chain:', error)
    } finally {
      setVerifying(false)
    }
  }

  // Filter entries
  const filteredEntries = entries.filter(entry => {
    if (actorFilter && entry.actor !== actorFilter) return false
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      return (
        entry.event_type.toLowerCase().includes(query) ||
        entry.action.toLowerCase().includes(query) ||
        entry.entity_id?.toLowerCase().includes(query) ||
        entry.reasoning?.toLowerCase().includes(query)
      )
    }
    return true
  })

  // Get unique actors for filter
  const actors = [...new Set(entries.map(e => e.actor))]
  const eventTypes = [...new Set(entries.map(e => e.event_type))]

  function getEventIcon(eventType: string | undefined | null) {
    if (!eventType) return <div className="w-4 h-4 rounded-full bg-accent-cyan/20" />
    if (eventType.includes('approved')) return <CheckCircleIcon className="w-4 h-4 text-accent-emerald" />
    if (eventType.includes('rejected')) return <XCircleIcon className="w-4 h-4 text-accent-red" />
    if (eventType.includes('risk')) return <ShieldCheckIcon className="w-4 h-4 text-accent-amber" />
    return <div className="w-4 h-4 rounded-full bg-accent-cyan/20" />
  }

  function getEventColor(eventType: string | undefined | null): "emerald" | "red" | "amber" | "cyan" | "gray" {
    if (!eventType) return 'gray'
    if (eventType.includes('approved')) return 'emerald'
    if (eventType.includes('rejected')) return 'red'
    if (eventType.includes('risk')) return 'amber'
    if (eventType.includes('signal')) return 'cyan'
    return 'gray'
  }

  return (
    <div className="flex min-h-screen bg-void">
      <Sidebar 
        isConnected={true} 
        mobileOpen={mobileMenuOpen}
        onMobileClose={() => setMobileMenuOpen(false)}
      />

      <main className="flex-1 md:ml-[280px] min-w-0">
        {/* Mobile Header */}
        <MobileHeader 
          onMenuClick={() => setMobileMenuOpen(true)}
          isConnected={true}
          title="Audit Trail"
        />

        <div className="p-4 md:p-6 lg:p-8">
      {/* Header */}
      <header className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8 gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gradient tracking-tight">
            ◈ AUDIT TRAIL
          </h1>
          <p className="text-xs text-text-muted tracking-widest uppercase mt-1">
            Immutable Hash-Chained Decision Log
          </p>
        </div>
        
        {/* Chain Verification */}
        <div className="flex items-center gap-4">
          <Button
            size="xs"
            variant="secondary"
            onClick={verifyChain}
            loading={verifying}
            icon={ShieldCheckIcon}
          >
            Verify Chain
          </Button>
          
          {verification && (
            <div className={`flex items-center gap-2 px-4 py-2 rounded-lg ${
              verification.valid 
                ? 'bg-accent-emerald/10 border border-accent-emerald/30'
                : 'bg-accent-red/10 border border-accent-red/30'
            }`}>
              {verification.valid ? (
                <>
                  <CheckCircleIcon className="w-5 h-5 text-accent-emerald" />
                  <span className="text-sm text-accent-emerald">
                    Chain Valid ({verification.checked} entries)
                  </span>
                </>
              ) : (
                <>
                  <ExclamationTriangleIcon className="w-5 h-5 text-accent-red" />
                  <span className="text-sm text-accent-red">
                    {verification.errors.length} integrity errors
                  </span>
                </>
              )}
            </div>
          )}
        </div>
      </header>

      {/* Accounting Breakdown Panel */}
      <div className="glass rounded-2xl p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gradient flex items-center gap-2">
            <CalculatorIcon className="w-5 h-5 text-accent-cyan" />
            Accounting Breakdown
          </h2>
          <Button
            size="xs"
            variant="secondary"
            onClick={fetchAccountingBreakdown}
            loading={breakdownLoading}
          >
            Refresh
          </Button>
        </div>

        {breakdownLoading && !breakdown ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-6 h-6 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
          </div>
        ) : breakdown ? (
          <div className="space-y-6">
            {/* Reconciliation Status Banner */}
            <div className={`flex items-center gap-3 p-4 rounded-xl ${
              breakdown.reconciliation.balanced 
                ? 'bg-accent-emerald/10 border border-accent-emerald/30'
                : 'bg-accent-red/10 border border-accent-red/30'
            }`}>
              {breakdown.reconciliation.balanced ? (
                <>
                  <CheckCircleIcon className="w-6 h-6 text-accent-emerald" />
                  <div>
                    <p className="font-medium text-accent-emerald">Books Balanced</p>
                    <p className="text-xs text-text-muted">Accounting equation verified • {breakdown.totalLedgerEntries} entries</p>
                  </div>
                </>
              ) : (
                <>
                  <ExclamationTriangleIcon className="w-6 h-6 text-accent-red" />
                  <div>
                    <p className="font-medium text-accent-red">Reconciliation Issues Found</p>
                    <p className="text-xs text-accent-red/80">{breakdown.reconciliation.discrepancies.join(' • ')}</p>
                  </div>
                </>
              )}
            </div>

            {/* Account Balances Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="glass rounded-xl p-4">
                <div className="flex items-center gap-2 mb-1">
                  <BanknotesIcon className="w-4 h-4 text-accent-cyan" />
                  <p className="text-xs text-text-muted uppercase">Starting Capital</p>
                </div>
                <p className="text-xl font-mono font-semibold">
                  ${breakdown.startingCapital.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
              </div>
              
              <div className="glass rounded-xl p-4">
                <div className="flex items-center gap-2 mb-1">
                  <BanknotesIcon className="w-4 h-4 text-accent-emerald" />
                  <p className="text-xs text-text-muted uppercase">Cash Balance</p>
                </div>
                <p className="text-xl font-mono font-semibold">
                  ${breakdown.cashBalance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
              </div>
              
              <div className="glass rounded-xl p-4">
                <div className="flex items-center gap-2 mb-1">
                  <ArrowTrendingUpIcon className="w-4 h-4 text-purple-400" />
                  <p className="text-xs text-text-muted uppercase">Positions (Entry Cost)</p>
                </div>
                <p className="text-xl font-mono font-semibold">
                  ${breakdown.positionsValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
              </div>
              
              <div className="glass rounded-xl p-4">
                <div className="flex items-center gap-2 mb-1">
                  {breakdown.realizedPnl >= 0 ? (
                    <ArrowTrendingUpIcon className="w-4 h-4 text-accent-emerald" />
                  ) : (
                    <ArrowTrendingDownIcon className="w-4 h-4 text-accent-red" />
                  )}
                  <p className="text-xs text-text-muted uppercase">Realized PnL</p>
                </div>
                <p className={`text-xl font-mono font-semibold ${
                  breakdown.realizedPnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'
                }`}>
                  {breakdown.realizedPnl >= 0 ? '+' : ''}${breakdown.realizedPnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
              </div>
            </div>

            {/* Cost Breakdown */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="glass rounded-xl p-4">
                <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                  <ExclamationTriangleIcon className="w-4 h-4 text-accent-amber" />
                  Trading Costs Breakdown
                </h3>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-text-secondary">Total Trading Costs</span>
                    <span className="font-mono text-accent-red">
                      -${breakdown.costBreakdown.totalTradingCosts.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-text-muted">├ Fees</span>
                    <span className="font-mono text-text-secondary">
                      ${breakdown.costBreakdown.fees.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-text-muted">├ Spread</span>
                    <span className="font-mono text-text-secondary">
                      ${breakdown.costBreakdown.spread.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-text-muted">└ Slippage</span>
                    <span className="font-mono text-text-secondary">
                      ${breakdown.costBreakdown.slippage.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                </div>
              </div>

              <div className="glass rounded-xl p-4">
                <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                  <CalculatorIcon className="w-4 h-4 text-accent-cyan" />
                  Equity Verification
                </h3>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-text-secondary">Book Equity (Cash + Positions)</span>
                    <span className="font-mono">
                      ${breakdown.bookEquity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm text-text-secondary">Expected Equity</span>
                    <span className="font-mono">
                      ${breakdown.expectedEquity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="border-t border-glass-border pt-2 mt-2">
                    <div className="flex justify-between items-center">
                      <span className="text-sm text-text-secondary">Discrepancy</span>
                      <span className={`font-mono font-semibold ${
                        Math.abs(breakdown.equityDiscrepancy) < 0.01 
                          ? 'text-accent-emerald' 
                          : 'text-accent-red'
                      }`}>
                        {breakdown.equityDiscrepancy >= 0 ? '+' : ''}${breakdown.equityDiscrepancy.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* All Account Balances */}
            <div className="glass rounded-xl p-4">
              <h3 className="text-sm font-semibold text-text-primary mb-3">All Account Balances</h3>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {Object.entries(breakdown.accountBalances).map(([account, balance]) => (
                  <div key={account} className="bg-background-secondary rounded-lg p-3">
                    <p className="text-[10px] text-text-muted uppercase mb-1">{account.replace(/_/g, ' ')}</p>
                    <p className={`font-mono text-sm ${
                      balance < 0 ? 'text-accent-red' : 'text-text-primary'
                    }`}>
                      ${(balance as number).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* Reconciliation Details */}
            <div className="glass rounded-xl p-4">
              <h3 className="text-sm font-semibold text-text-primary mb-3">Double-Entry Verification</h3>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-xs text-text-muted uppercase mb-1">Total Debits</p>
                  <p className="font-mono text-lg">${breakdown.reconciliation.totalDebits.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                </div>
                <div>
                  <p className="text-xs text-text-muted uppercase mb-1">Total Credits</p>
                  <p className="font-mono text-lg">${breakdown.reconciliation.totalCredits.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                </div>
                <div>
                  <p className="text-xs text-text-muted uppercase mb-1">Imbalance</p>
                  <p className={`font-mono text-lg ${
                    Math.abs(breakdown.reconciliation.imbalance) < 0.01 
                      ? 'text-accent-emerald' 
                      : 'text-accent-red'
                  }`}>
                    ${breakdown.reconciliation.imbalance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </p>
                </div>
              </div>
              
              {breakdown.reconciliation.discrepancies.length > 0 && (
                <div className="mt-4 p-3 bg-accent-red/10 rounded-lg border border-accent-red/30">
                  <p className="text-xs text-accent-red font-medium mb-1">Discrepancies Found:</p>
                  {breakdown.reconciliation.discrepancies.map((d, i) => (
                    <p key={i} className="text-xs text-accent-red/80">• {d}</p>
                  ))}
                </div>
              )}
            </div>

            <p className="text-[10px] text-text-muted text-right">
              Last updated: {new Date(breakdown.timestamp).toLocaleString()}
            </p>
          </div>
        ) : (
          <div className="text-center py-8 text-text-muted">
            Failed to load accounting breakdown
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="glass rounded-2xl p-4 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="text-xs text-text-muted uppercase tracking-wider block mb-2">
              Search
            </label>
            <TextInput
              icon={MagnifyingGlassIcon}
              placeholder="Search entries..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          
          <div>
            <label className="text-xs text-text-muted uppercase tracking-wider block mb-2">
              Event Type
            </label>
            <Select
              value={eventTypeFilter}
              onValueChange={setEventTypeFilter}
              placeholder="All Events"
            >
              <SelectItem value="">All Events</SelectItem>
              {eventTypes.map(type => (
                <SelectItem key={type} value={type}>{type}</SelectItem>
              ))}
            </Select>
          </div>
          
          <div>
            <label className="text-xs text-text-muted uppercase tracking-wider block mb-2">
              Actor
            </label>
            <Select
              value={actorFilter}
              onValueChange={setActorFilter}
              placeholder="All Actors"
            >
              <SelectItem value="">All Actors</SelectItem>
              {actors.map(actor => (
                <SelectItem key={actor} value={actor}>{actor}</SelectItem>
              ))}
            </Select>
          </div>
          
          <div className="flex items-end">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                setSearchQuery('')
                setEventTypeFilter('')
                setActorFilter('')
              }}
            >
              Clear Filters
            </Button>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="glass rounded-xl p-4">
          <p className="text-xs text-text-muted uppercase mb-1">Total Entries</p>
          <p className="text-2xl font-semibold">{entries.length}</p>
        </div>
        <div className="glass rounded-xl p-4">
          <p className="text-xs text-text-muted uppercase mb-1">Shown</p>
          <p className="text-2xl font-semibold">{filteredEntries.length}</p>
        </div>
        <div className="glass rounded-xl p-4">
          <p className="text-xs text-text-muted uppercase mb-1">Actors</p>
          <p className="text-2xl font-semibold">{actors.length}</p>
        </div>
        <div className="glass rounded-xl p-4">
          <p className="text-xs text-text-muted uppercase mb-1">Event Types</p>
          <p className="text-2xl font-semibold">{eventTypes.length}</p>
        </div>
      </div>

      {/* Audit Table */}
      <div className="glass rounded-2xl p-6">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <Table>
            <TableHead>
              <TableRow>
                <TableHeaderCell className="text-text-muted">Time</TableHeaderCell>
                <TableHeaderCell className="text-text-muted">Event</TableHeaderCell>
                <TableHeaderCell className="text-text-muted">Actor</TableHeaderCell>
                <TableHeaderCell className="text-text-muted">Action</TableHeaderCell>
                <TableHeaderCell className="text-text-muted">Entity</TableHeaderCell>
                <TableHeaderCell className="text-text-muted">Reasoning</TableHeaderCell>
                <TableHeaderCell className="text-text-muted">Hash</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredEntries.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell className="text-text-secondary text-xs whitespace-nowrap">
                    {new Date(entry.timestamp).toLocaleString()}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {getEventIcon(entry.event_type)}
                      <Badge color={getEventColor(entry.event_type)} size="xs">
                        {entry.event_type}
                      </Badge>
                    </div>
                  </TableCell>
                  <TableCell className="text-text-secondary text-xs">
                    {entry.actor}
                  </TableCell>
                  <TableCell className="font-medium">
                    {entry.action}
                  </TableCell>
                  <TableCell className="text-xs">
                    {entry.entity_type && (
                      <span className="text-text-muted">
                        {entry.entity_type}:{' '}
                        <span className="text-accent-cyan font-mono">
                          {entry.entity_id?.slice(0, 8)}...
                        </span>
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-text-secondary max-w-xs truncate">
                    {entry.reasoning || '—'}
                  </TableCell>
                  <TableCell>
                    <code className="text-[10px] text-text-muted font-mono bg-background-secondary px-2 py-1 rounded">
                      {entry.hash?.slice(0, 12)}...
                    </code>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {!loading && filteredEntries.length === 0 && (
          <div className="text-center py-12 text-text-muted">
            No audit entries found
          </div>
        )}
      </div>

      {/* Hash Chain Explanation */}
      <div className="glass rounded-xl p-4 mt-6">
        <div className="flex items-start gap-3">
          <ShieldCheckIcon className="w-5 h-5 text-accent-cyan mt-0.5" />
          <div>
            <h3 className="text-sm font-medium text-text-primary mb-1">
              Cryptographic Hash Chain
            </h3>
            <p className="text-xs text-text-muted">
              Each audit entry contains a SHA-256 hash of its contents and a reference to the 
              previous entry's hash. This creates an immutable chain where any modification 
              would break the chain's integrity. Use the "Verify Chain" button to validate 
              that no entries have been tampered with.
            </p>
          </div>
        </div>
      </div>
        </div>
      </main>
    </div>
  )
}
