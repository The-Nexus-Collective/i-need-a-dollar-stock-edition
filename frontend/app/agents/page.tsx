'use client'

import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Brain, 
  Search, 
  CheckCircle, 
  TrendingUp,
  Zap,
  BookOpen,
  Activity,
  Clock,
  Filter,
  RefreshCw,
  ChevronDown,
  ChevronRight,
} from 'lucide-react'
import { clsx } from 'clsx'

import { Sidebar } from '@/components/Sidebar'
import { api } from '@/lib/api'
import { useWebSocket } from '@/lib/websocket'

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface AgentPersona {
  name: string
  emoji: string
  role: string
  personality: string
}

interface AgentLog {
  id: string
  timestamp: string
  cycle_id: string
  agent_name: string
  action_type: string
  reasoning: string
  decision: string | null
  confidence: number | null
  duration_ms: number | null
  tokens_used: number | null
  persona?: AgentPersona
  narrative?: string
}

interface Cycle {
  cycle_id: string
  start_time: string
  end_time: string
  log_count: number
  agents_involved: number
  total_tokens: number
  avg_confidence: number | null
}

// ═══════════════════════════════════════════════════════════════════════════════
// AGENT ICONS & COLORS
// ═══════════════════════════════════════════════════════════════════════════════

const AGENT_CONFIG: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  orchestrator: { icon: <Brain className="w-4 h-4" />, color: 'text-purple-400', label: 'Orchestrator' },
  discovery: { icon: <Search className="w-4 h-4" />, color: 'text-cyan-400', label: 'Discovery' },
  validation: { icon: <CheckCircle className="w-4 h-4" />, color: 'text-emerald-400', label: 'Validation' },
  sentiment: { icon: <TrendingUp className="w-4 h-4" />, color: 'text-amber-400', label: 'Sentiment' },
  strategy_ensemble: { icon: <Zap className="w-4 h-4" />, color: 'text-pink-400', label: 'Strategy' },
  execution: { icon: <Activity className="w-4 h-4" />, color: 'text-blue-400', label: 'Execution' },
  learner: { icon: <BookOpen className="w-4 h-4" />, color: 'text-orange-400', label: 'Learner' },
}

const ACTION_COLORS: Record<string, string> = {
  think: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  act: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  decide: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  dispatch: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  error: 'bg-red-500/20 text-red-400 border-red-500/30',
  cycle_start: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  cycle_complete: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
}

// ═══════════════════════════════════════════════════════════════════════════════
// LOG ENTRY COMPONENT - Chat-like interface with personas
// ═══════════════════════════════════════════════════════════════════════════════

function LogEntry({ log, isExpanded, onToggle }: { 
  log: AgentLog
  isExpanded: boolean
  onToggle: () => void 
}) {
  const agentConfig = AGENT_CONFIG[log.agent_name] || { 
    icon: <Activity className="w-4 h-4" />, 
    color: 'text-gray-400',
    label: log.agent_name 
  }
  
  // Use persona from API if available
  const personaName = log.persona?.name || agentConfig.label
  const personaEmoji = log.persona?.emoji || ''
  const personality = log.persona?.personality || ''
  
  const actionColor = ACTION_COLORS[log.action_type] || 'bg-gray-500/20 text-gray-400 border-gray-500/30'
  
  const time = new Date(log.timestamp).toLocaleTimeString()
  
  // Confidence indicator
  const getConfidenceIndicator = (conf: number) => {
    if (conf >= 80) return { emoji: '💪', label: 'High confidence', color: 'text-emerald-400' }
    if (conf >= 50) return { emoji: '📊', label: 'Moderate', color: 'text-amber-400' }
    return { emoji: '🤔', label: 'Uncertain', color: 'text-red-400' }
  }
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="group"
    >
      {/* Chat bubble style */}
      <div 
        className="flex gap-3 cursor-pointer hover:bg-white/5 rounded-lg p-3 transition-colors"
        onClick={onToggle}
      >
        {/* Avatar */}
        <div className={clsx(
          'w-10 h-10 rounded-full flex items-center justify-center text-lg shrink-0',
          'bg-gradient-to-br from-purple-500/20 to-cyan-500/20 border border-white/10'
        )}>
          {personaEmoji || agentConfig.icon}
        </div>
        
        {/* Message Content */}
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-2 mb-1">
            <span className={clsx('font-semibold text-sm', agentConfig.color)}>
              {personaName}
            </span>
            <span className={clsx(
              'px-2 py-0.5 text-xs rounded-full border',
              actionColor
            )}>
              {log.action_type}
            </span>
            <span className="text-xs text-text-muted ml-auto">
              {time}
            </span>
          </div>
          
          {/* Message bubble */}
          <div className="bg-surface-2 rounded-2xl rounded-tl-sm px-4 py-3 border border-white/5">
            <p className="text-sm text-text-primary leading-relaxed">
              {log.reasoning}
            </p>
            
            {/* Decision highlight */}
            {log.decision && (
              <div className="mt-2 pt-2 border-t border-white/10">
                <span className="text-xs text-text-muted">Decision: </span>
                <span className="text-sm text-accent-cyan font-medium">
                  {log.decision}
                </span>
              </div>
            )}
            
            {/* Metrics bar */}
            <div className="flex items-center gap-3 mt-2 text-xs text-text-muted">
              {log.confidence && (
                <span className={getConfidenceIndicator(log.confidence).color}>
                  {getConfidenceIndicator(log.confidence).emoji} {log.confidence.toFixed(0)}%
                </span>
              )}
              {log.duration_ms && (
                <span>⏱️ {log.duration_ms}ms</span>
              )}
              {log.tokens_used && (
                <span>🔤 {log.tokens_used} tokens</span>
              )}
            </div>
          </div>
          
          {/* Expanded: Personality & Context */}
          <AnimatePresence>
            {isExpanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="mt-2 ml-4 p-3 bg-surface-1 rounded-lg border border-white/5 text-xs"
              >
                {personality && (
                  <div className="mb-2">
                    <span className="text-text-muted">🎭 Personality: </span>
                    <span className="text-text-secondary italic">{personality}</span>
                  </div>
                )}
                <div className="text-text-muted">
                  Agent: {log.agent_name} | Cycle: {log.cycle_id.slice(0, 8)}...
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
        
        {/* Expand Icon */}
        <div className="text-text-muted opacity-0 group-hover:opacity-100 transition-opacity">
          {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </div>
      </div>
    </motion.div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// CYCLE CARD COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

function CycleCard({ cycle, isActive, onClick }: {
  cycle: Cycle
  isActive: boolean
  onClick: () => void
}) {
  const startTime = new Date(cycle.start_time)
  const duration = new Date(cycle.end_time).getTime() - startTime.getTime()
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      onClick={onClick}
      className={clsx(
        'p-4 rounded-lg border cursor-pointer transition-all',
        isActive 
          ? 'bg-accent-cyan/10 border-accent-cyan/50' 
          : 'bg-surface-2 border-white/5 hover:border-white/20'
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-medium text-text-primary">
          {startTime.toLocaleTimeString()}
        </span>
        <span className="text-xs text-text-muted">
          {(duration / 1000).toFixed(1)}s
        </span>
      </div>
      
      <div className="flex items-center gap-4 text-xs text-text-muted">
        <span>{cycle.log_count} logs</span>
        <span>{cycle.agents_involved} agents</span>
        {cycle.avg_confidence && (
          <span>{cycle.avg_confidence.toFixed(0)}% avg</span>
        )}
      </div>
    </motion.div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════════════════════

export default function AgentsPage() {
  // State
  const [logs, setLogs] = useState<AgentLog[]>([])
  const [cycles, setCycles] = useState<Cycle[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedCycle, setSelectedCycle] = useState<string | null>(null)
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null)
  const [expandedLogs, setExpandedLogs] = useState<Set<string>>(new Set())
  const [autoRefresh, setAutoRefresh] = useState(true)
  
  // Account data for sidebar
  const [accountData] = useState({
    balance: 100000,
    initialBalance: 100000,
    totalFees: 0,
    slippageCost: 0,
    totalTrades: 0,
    winningTrades: 0,
    mode: 'paper' as const,
  })
  
  // WebSocket for real-time logs
  const { isConnected } = useWebSocket({
    channel: 'all',
    onMessage: (message) => {
      if (message.type === 'agent_log' && autoRefresh) {
        setLogs(prev => [message.data, ...prev].slice(0, 200))
      }
    },
  })
  
  // Fetch data
  const fetchData = useCallback(async () => {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    try {
      const [logsData, cyclesData] = await Promise.all([
        fetch(`${API_URL}/api/agents/logs?limit=100`).then(r => r.json()).catch(() => []),
        fetch(`${API_URL}/api/agents/cycles?limit=20`).then(r => r.json()).catch(() => []),
      ])
      
      setLogs(Array.isArray(logsData) ? logsData : [])
      setCycles(Array.isArray(cyclesData) ? cyclesData : [])
    } catch (error) {
      console.error('Failed to fetch agent data:', error)
    } finally {
      setLoading(false)
    }
  }, [])
  
  useEffect(() => {
    fetchData()
    
    if (autoRefresh) {
      const interval = setInterval(fetchData, 10000)
      return () => clearInterval(interval)
    }
  }, [fetchData, autoRefresh])
  
  // Filter logs
  const filteredLogs = logs.filter(log => {
    if (selectedCycle && log.cycle_id !== selectedCycle) return false
    if (selectedAgent && log.agent_name !== selectedAgent) return false
    return true
  })
  
  // Toggle log expansion
  const toggleExpand = (id: string) => {
    setExpandedLogs(prev => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }
  
  // Loading state
  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar isConnected={isConnected} />
        <main className="flex-1 ml-[280px] p-8 flex items-center justify-center">
          <div className="text-center">
            <Brain className="w-12 h-12 mx-auto mb-4 text-purple-400 animate-pulse" />
            <p className="text-text-muted">Loading Agent Logbook...</p>
          </div>
        </main>
      </div>
    )
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
              className="text-2xl font-semibold text-text-primary tracking-tight flex items-center gap-3"
            >
              <Brain className="w-7 h-7 text-purple-400" />
              Agent Logbook
            </motion.h1>
            <p className="text-xs text-text-muted mt-1">
              Complete transparency into agent reasoning and decisions
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            {/* Auto-refresh toggle */}
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={clsx(
                'flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium transition-all',
                autoRefresh
                  ? 'bg-accent-emerald/10 text-accent-emerald border border-accent-emerald/30'
                  : 'bg-surface-2 text-text-muted border border-white/10'
              )}
            >
              <RefreshCw className={clsx('w-3 h-3', autoRefresh && 'animate-spin')} />
              {autoRefresh ? 'Live' : 'Paused'}
            </button>
            
            {/* Connection status */}
            <div className={clsx(
              'flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium',
              isConnected 
                ? 'bg-accent-emerald/10 text-accent-emerald border border-accent-emerald/30'
                : 'bg-accent-red/10 text-accent-red border border-accent-red/30'
            )}>
              <div className={clsx('w-2 h-2 rounded-full', isConnected ? 'bg-accent-emerald' : 'bg-accent-red')} />
              {isConnected ? 'Connected' : 'Disconnected'}
            </div>
          </div>
        </header>
        
        <div className="grid grid-cols-12 gap-6">
          {/* Left Column - Cycles */}
          <div className="col-span-3 space-y-4">
            <div className="glass-card p-4">
              <h3 className="text-sm font-medium text-text-primary mb-4 flex items-center gap-2">
                <Clock className="w-4 h-4 text-text-muted" />
                Recent Cycles
              </h3>
              
              <div className="space-y-2 max-h-[600px] overflow-y-auto">
                <button
                  onClick={() => setSelectedCycle(null)}
                  className={clsx(
                    'w-full text-left p-3 rounded-lg text-sm transition-all',
                    !selectedCycle
                      ? 'bg-accent-cyan/10 text-accent-cyan'
                      : 'text-text-muted hover:bg-surface-2'
                  )}
                >
                  All Cycles
                </button>
                
                {cycles.map(cycle => (
                  <CycleCard
                    key={cycle.cycle_id}
                    cycle={cycle}
                    isActive={selectedCycle === cycle.cycle_id}
                    onClick={() => setSelectedCycle(cycle.cycle_id)}
                  />
                ))}
              </div>
            </div>
            
            {/* Agent Filter */}
            <div className="glass-card p-4">
              <h3 className="text-sm font-medium text-text-primary mb-4 flex items-center gap-2">
                <Filter className="w-4 h-4 text-text-muted" />
                Filter by Agent
              </h3>
              
              <div className="space-y-1">
                <button
                  onClick={() => setSelectedAgent(null)}
                  className={clsx(
                    'w-full text-left px-3 py-2 rounded-lg text-sm transition-all flex items-center gap-2',
                    !selectedAgent
                      ? 'bg-accent-cyan/10 text-accent-cyan'
                      : 'text-text-muted hover:bg-surface-2'
                  )}
                >
                  All Agents
                </button>
                
                {Object.entries(AGENT_CONFIG).map(([key, config]) => (
                  <button
                    key={key}
                    onClick={() => setSelectedAgent(key)}
                    className={clsx(
                      'w-full text-left px-3 py-2 rounded-lg text-sm transition-all flex items-center gap-2',
                      selectedAgent === key
                        ? 'bg-accent-cyan/10 text-accent-cyan'
                        : 'text-text-muted hover:bg-surface-2'
                    )}
                  >
                    <span className={config.color}>{config.icon}</span>
                    {config.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
          
          {/* Right Column - Log Timeline */}
          <div className="col-span-9">
            <div className="glass-card p-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-sm font-medium text-text-primary flex items-center gap-2">
                  <Activity className="w-4 h-4 text-text-muted" />
                  Agent Activity Timeline
                  <span className="text-xs text-text-muted ml-2">
                    ({filteredLogs.length} entries)
                  </span>
                </h3>
              </div>
              
              {filteredLogs.length === 0 ? (
                <div className="text-center py-12 text-text-muted">
                  <Brain className="w-12 h-12 mx-auto mb-4 opacity-30" />
                  <p>No agent activity yet</p>
                  <p className="text-xs mt-1">Logs will appear as agents make decisions</p>
                </div>
              ) : (
                <div className="space-y-1 max-h-[700px] overflow-y-auto">
                  {filteredLogs.map(log => (
                    <LogEntry
                      key={log.id}
                      log={log}
                      isExpanded={expandedLogs.has(log.id)}
                      onToggle={() => toggleExpand(log.id)}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

