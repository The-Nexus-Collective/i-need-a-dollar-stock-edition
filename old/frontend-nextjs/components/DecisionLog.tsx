'use client'

import { motion } from 'framer-motion'
import { clsx } from 'clsx'
import { 
  TrendingUp, 
  TrendingDown, 
  Minus,
  Filter,
  Clock,
  AlertTriangle,
  CheckCircle,
  XCircle,
  BarChart2,
  Activity,
} from 'lucide-react'

interface TradingDecision {
  id: string
  timestamp: string
  batch_id: string
  selected_coin: string | null
  selected_score: number | null
  decision: 'long' | 'short' | 'flat' | 'filtered'
  filter_reason: string | null
  position_size: number | null
  entry_price: number | null
  stop_loss: number | null
  take_profit: number | null
  equity_before: number | null
  risk_amount: number | null
  all_scores: Record<string, number> | null
  executed: boolean
}

interface DecisionStats {
  total_decisions: number
  long_decisions: number
  short_decisions: number
  flat_decisions: number
  filtered_decisions: number
  score_filtered: number
  volume_filtered: number
  executed_count: number
}

interface DecisionLogProps {
  decisions: TradingDecision[]
  stats: DecisionStats
}

const decisionConfig = {
  long: {
    icon: TrendingUp,
    color: 'text-accent-emerald',
    bg: 'bg-accent-emerald/10',
    border: 'border-accent-emerald/30',
    label: 'LONG',
  },
  short: {
    icon: TrendingDown,
    color: 'text-accent-red',
    bg: 'bg-accent-red/10',
    border: 'border-accent-red/30',
    label: 'SHORT',
  },
  flat: {
    icon: Minus,
    color: 'text-accent-amber',
    bg: 'bg-accent-amber/10',
    border: 'border-accent-amber/30',
    label: 'FLAT',
  },
  filtered: {
    icon: Filter,
    color: 'text-text-muted',
    bg: 'bg-void/50',
    border: 'border-text-dim/30',
    label: 'GEFILTERT',
  },
}

function formatFilterReason(reason: string | null): string {
  if (!reason) return 'Kein Grund angegeben'
  
  const reasonMap: Record<string, string> = {
    'score_below_threshold': 'Score unter Schwellenwert (< 65)',
    'volume_filter_failed': 'Volumen-Filter nicht bestanden',
    'all_filtered': 'Alle Coins gefiltert',
    'no_valid_signals': 'Keine validen Signale',
    'flatten_time': 'Tägliche Glattstellung (23:55)',
  }
  
  return reasonMap[reason] || reason
}

function DecisionCard({ decision }: { decision: TradingDecision }) {
  const config = decisionConfig[decision.decision]
  const Icon = config.icon
  const time = new Date(decision.timestamp)
  
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      className={clsx(
        'p-4 rounded-xl border',
        config.bg,
        config.border
      )}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={clsx('p-2 rounded-lg', config.bg)}>
            <Icon className={clsx('w-4 h-4', config.color)} />
          </div>
          <div>
            <span className={clsx('text-sm font-semibold', config.color)}>
              {config.label}
            </span>
            {decision.selected_coin && (
              <span className="ml-2 text-text-primary font-mono">
                {decision.selected_coin}
              </span>
            )}
          </div>
        </div>
        <div className="text-right">
          <div className="flex items-center gap-1 text-text-muted text-xs">
            <Clock className="w-3 h-3" />
            {time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
          <div className="text-[10px] text-text-dim">
            {time.toLocaleDateString()}
          </div>
        </div>
      </div>

      {/* Reason for filtered/flat */}
      {(decision.decision === 'filtered' || decision.decision === 'flat') && decision.filter_reason && (
        <div className="flex items-start gap-2 mb-3 p-2 rounded-lg bg-void/30">
          <AlertTriangle className="w-4 h-4 text-accent-amber flex-shrink-0 mt-0.5" />
          <p className="text-xs text-text-secondary">
            {formatFilterReason(decision.filter_reason)}
          </p>
        </div>
      )}

      {/* Trade details for long/short */}
      {(decision.decision === 'long' || decision.decision === 'short') && (
        <div className="grid grid-cols-2 gap-2 text-xs">
          {decision.selected_score && (
            <div>
              <span className="text-text-dim block">Score</span>
              <span className={clsx('font-mono font-medium', config.color)}>
                {decision.selected_score > 0 ? '+' : ''}{decision.selected_score.toFixed(1)}
              </span>
            </div>
          )}
          {decision.entry_price && (
            <div>
              <span className="text-text-dim block">Entry</span>
              <span className="font-mono text-text-primary">
                ${decision.entry_price.toLocaleString()}
              </span>
            </div>
          )}
          {decision.position_size && (
            <div>
              <span className="text-text-dim block">Size</span>
              <span className="font-mono text-text-primary">
                {decision.position_size.toFixed(6)}
              </span>
            </div>
          )}
          {decision.risk_amount && (
            <div>
              <span className="text-text-dim block">Risiko</span>
              <span className="font-mono text-accent-amber">
                ${decision.risk_amount.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Execution status */}
      <div className="mt-3 pt-3 border-t border-glass-border flex items-center justify-between">
        <span className="text-[10px] text-text-dim font-mono">
          {decision.batch_id.slice(0, 8)}...
        </span>
        <div className="flex items-center gap-1">
          {decision.executed ? (
            <>
              <CheckCircle className="w-3 h-3 text-accent-emerald" />
              <span className="text-[10px] text-accent-emerald">Ausgeführt</span>
            </>
          ) : (
            <>
              <XCircle className="w-3 h-3 text-text-dim" />
              <span className="text-[10px] text-text-dim">Nicht ausgeführt</span>
            </>
          )}
        </div>
      </div>
    </motion.div>
  )
}

export function DecisionLog({ decisions, stats }: DecisionLogProps) {
  const hasDecisions = decisions.length > 0
  
  return (
    <div className="space-y-6">
      {/* Stats Overview */}
      <div className="glass-card p-5">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-4 h-4 text-accent-cyan" />
          <span className="text-label">Filter-Statistik (Heute)</span>
        </div>
        
        <div className="grid grid-cols-4 gap-3">
          <div className="text-center p-3 rounded-lg bg-void/30">
            <div className="text-2xl font-mono font-bold text-text-primary">
              {stats.total_decisions}
            </div>
            <div className="text-[10px] text-text-dim uppercase tracking-wider">
              Entscheidungen
            </div>
          </div>
          <div className="text-center p-3 rounded-lg bg-accent-emerald/10">
            <div className="text-2xl font-mono font-bold text-accent-emerald">
              {stats.long_decisions + stats.short_decisions}
            </div>
            <div className="text-[10px] text-text-dim uppercase tracking-wider">
              Trades
            </div>
          </div>
          <div className="text-center p-3 rounded-lg bg-accent-amber/10">
            <div className="text-2xl font-mono font-bold text-accent-amber">
              {stats.filtered_decisions}
            </div>
            <div className="text-[10px] text-text-dim uppercase tracking-wider">
              Gefiltert
            </div>
          </div>
          <div className="text-center p-3 rounded-lg bg-accent-red/10">
            <div className="text-2xl font-mono font-bold text-accent-red">
              {stats.flat_decisions}
            </div>
            <div className="text-[10px] text-text-dim uppercase tracking-wider">
              Flat
            </div>
          </div>
        </div>

        {/* Filter breakdown */}
        {stats.total_decisions > 0 && (
          <div className="mt-4 pt-4 border-t border-glass-border">
            <div className="flex items-center justify-between text-xs">
              <span className="text-text-muted">Score-Filter:</span>
              <span className="font-mono text-text-secondary">{stats.score_filtered}x</span>
            </div>
            <div className="flex items-center justify-between text-xs mt-1">
              <span className="text-text-muted">Volume-Filter:</span>
              <span className="font-mono text-text-secondary">{stats.volume_filtered}x</span>
            </div>
          </div>
        )}
      </div>

      {/* Decision History */}
      <div className="glass-card p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-accent-cyan" />
            <span className="text-label">Entscheidungs-Log</span>
          </div>
          <span className="text-[10px] text-text-muted">
            Letzte {decisions.length} Stunden
          </span>
        </div>

        {hasDecisions ? (
          <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
            {decisions.map((decision, index) => (
              <DecisionCard key={decision.id} decision={decision} />
            ))}
          </div>
        ) : (
          <div className="text-center py-12">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-void/50 flex items-center justify-center">
              <BarChart2 className="w-8 h-8 text-text-dim" />
            </div>
            <p className="text-text-muted font-medium mb-1">Keine Entscheidungen</p>
            <p className="text-text-dim text-xs max-w-xs mx-auto">
              Trading-Entscheidungen werden stündlich getroffen und hier protokolliert.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

