'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { 
  Brain, 
  Search, 
  CheckCircle, 
  TrendingUp,
  Zap,
  BookOpen,
  Activity,
  RefreshCw,
} from 'lucide-react'
import { clsx } from 'clsx'
import Link from 'next/link'

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface AgentLog {
  agent_name: string
  action_type: string
  reasoning: string
  decision: string | null
  confidence: number | null
  duration_ms: number | null
  timestamp: string
}

interface Cycle {
  cycle_id: string
  start_time: string
  end_time: string
  log_count: number
  agents_involved: number
  avg_confidence: number | null
}

interface Strategy {
  strategy: string
  weight: number
  win_rate_24h: number | null
  pnl_24h: number
  trades_24h: number
}

// ═══════════════════════════════════════════════════════════════════════════════
// AGENT CONFIG
// ═══════════════════════════════════════════════════════════════════════════════

const AGENT_CONFIG: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  orchestrator: { icon: <Brain className="w-3 h-3" />, color: 'text-purple-400', label: 'Brain' },
  discovery: { icon: <Search className="w-3 h-3" />, color: 'text-cyan-400', label: 'Discovery' },
  validation: { icon: <CheckCircle className="w-3 h-3" />, color: 'text-emerald-400', label: 'Validation' },
  sentiment: { icon: <TrendingUp className="w-3 h-3" />, color: 'text-amber-400', label: 'Sentiment' },
  strategy_ensemble: { icon: <Zap className="w-3 h-3" />, color: 'text-pink-400', label: 'Strategy' },
  execution: { icon: <Activity className="w-3 h-3" />, color: 'text-blue-400', label: 'Execution' },
  learner: { icon: <BookOpen className="w-3 h-3" />, color: 'text-orange-400', label: 'Learner' },
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function AgentStatusCard() {
  const [logs, setLogs] = useState<AgentLog[]>([])
  const [cycles, setCycles] = useState<Cycle[]>([])
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    async function fetchData() {
      try {
        const [logsData, cyclesData, strategiesData] = await Promise.all([
          fetch(`${API_URL}/api/agents/logs?limit=5`).then(r => r.json()).catch(() => []),
          fetch(`${API_URL}/api/agents/cycles?limit=3`).then(r => r.json()).catch(() => []),
          fetch(`${API_URL}/api/strategies`).then(r => r.json()).catch(() => []),
        ])
        
        setLogs(Array.isArray(logsData) ? logsData : [])
        setCycles(Array.isArray(cyclesData) ? cyclesData : [])
        setStrategies(Array.isArray(strategiesData) ? strategiesData : [])
      } catch (error) {
        console.error('Failed to fetch agent status:', error)
      } finally {
        setLoading(false)
      }
    }
    
    fetchData()
    const interval = setInterval(fetchData, 15000)
    return () => clearInterval(interval)
  }, [])
  
  if (loading) {
    return (
      <div className="glass-card p-6">
        <div className="flex items-center justify-center h-40">
          <RefreshCw className="w-6 h-6 text-accent-cyan animate-spin" />
        </div>
      </div>
    )
  }
  
  const latestCycle = cycles[0]
  
  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
          <Brain className="w-4 h-4 text-purple-400" />
          Agentic System
        </h3>
        <Link 
          href="/agents"
          className="text-xs text-accent-cyan hover:underline"
        >
          View Logbook →
        </Link>
      </div>
      
      {/* Latest Cycle Info */}
      {latestCycle && (
        <div className="mb-4 p-3 bg-surface-2 rounded-lg">
          <div className="flex items-center justify-between text-xs">
            <span className="text-text-muted">Last Cycle</span>
            <span className="text-text-primary">
              {new Date(latestCycle.start_time).toLocaleTimeString()}
            </span>
          </div>
          <div className="flex items-center gap-4 mt-2 text-xs text-text-muted">
            <span>{latestCycle.log_count} actions</span>
            <span>{latestCycle.agents_involved} agents</span>
            {latestCycle.avg_confidence && (
              <span className="text-accent-emerald">
                {latestCycle.avg_confidence.toFixed(0)}% avg confidence
              </span>
            )}
          </div>
        </div>
      )}
      
      {/* Recent Activity */}
      <div className="space-y-2 mb-4">
        <span className="text-xs text-text-muted">Recent Activity</span>
        {logs.length === 0 ? (
          <p className="text-xs text-text-muted italic">No recent activity</p>
        ) : (
          logs.slice(0, 4).map((log, i) => {
            const config = AGENT_CONFIG[log.agent_name] || { 
              icon: <Activity className="w-3 h-3" />,
              color: 'text-gray-400',
              label: log.agent_name
            }
            
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                className="flex items-start gap-2 text-xs"
              >
                <span className={clsx('mt-0.5', config.color)}>
                  {config.icon}
                </span>
                <div className="flex-1 min-w-0">
                  <span className={config.color}>{config.label}</span>
                  <span className="text-text-muted mx-1">→</span>
                  <span className="text-text-secondary line-clamp-1">
                    {log.decision || log.reasoning}
                  </span>
                </div>
              </motion.div>
            )
          })
        )}
      </div>
      
      {/* Strategy Weights */}
      {strategies.length > 0 && (
        <div>
          <span className="text-xs text-text-muted">Strategy Weights</span>
          <div className="mt-2 flex flex-wrap gap-1">
            {strategies.map(s => (
              <div
                key={s.strategy}
                className={clsx(
                  'px-2 py-1 text-xs rounded',
                  s.pnl_24h >= 0 
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'bg-red-500/10 text-red-400 border border-red-500/20'
                )}
              >
                {s.strategy.replace('_', ' ')}: {(s.weight * 100).toFixed(0)}%
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}


export function UniverseStatusCard() {
  const [stats, setStats] = useState({
    approved_count: 0,
    pending_count: 0,
    x_discovery_count: 0,
    total_volume: 0,
    avg_hype_score: 0,
  })
  
  useEffect(() => {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    async function fetchStats() {
      try {
        const data = await fetch(`${API_URL}/api/universe/stats`).then(r => r.json())
        if (data) setStats(data)
      } catch (error) {
        console.error('Failed to fetch universe stats:', error)
      }
    }
    
    fetchStats()
    const interval = setInterval(fetchStats, 30000)
    return () => clearInterval(interval)
  }, [])
  
  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
          <Search className="w-4 h-4 text-cyan-400" />
          Dynamic Universe
        </h3>
        <Link 
          href="/universe"
          className="text-xs text-accent-cyan hover:underline"
        >
          Explore →
        </Link>
      </div>
      
      <div className="grid grid-cols-3 gap-3">
        <div className="text-center">
          <div className="text-2xl font-semibold text-accent-emerald">
            {stats.approved_count}
          </div>
          <div className="text-xs text-text-muted">Tradable</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-semibold text-accent-amber">
            {stats.pending_count}
          </div>
          <div className="text-xs text-text-muted">Pending</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-semibold text-blue-400">
            {stats.x_discovery_count}
          </div>
          <div className="text-xs text-text-muted">X Finds</div>
        </div>
      </div>
      
      <div className="mt-4 pt-4 border-t border-white/5">
        <div className="flex items-center justify-between text-xs">
          <span className="text-text-muted">Total Volume</span>
          <span className="text-text-primary font-mono">
            ${(stats.total_volume / 1e9).toFixed(1)}B
          </span>
        </div>
        <div className="flex items-center justify-between text-xs mt-1">
          <span className="text-text-muted">Avg Hype Score</span>
          <span className={clsx(
            'font-mono',
            stats.avg_hype_score > 50 ? 'text-accent-amber' : 'text-text-primary'
          )}>
            {stats.avg_hype_score.toFixed(0)}
          </span>
        </div>
      </div>
    </div>
  )
}

