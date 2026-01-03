'use client'

import { useEffect, useState } from 'react'
import { Sidebar } from '@/components/Sidebar'
import { useWebSocket } from '@/lib/websocket'

/**
 * Evolution Dashboard - Watch the Swarm Evolve
 * 
 * Displays:
 * - Agent beliefs and their evolution
 * - Hypothesis pool and testing
 * - Strategy gene evolution
 * - Memory insights
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Agent {
  id: string
  name: string
  emoji: string
  role: string
  running: boolean
  energy: number
  beliefs_count: number
  hypotheses_count: number
  last_perception: string | null
  pending_signals: number
}

interface SwarmStatus {
  running: boolean
  started_at: string | null
  agent_count: number
  agents: Agent[]
  signal_network: {
    active_agents: number
    recent_signals: number
  }
  memory: {
    cached_memories: number
  }
}

interface Strategy {
  strategy: string
  weight: number
  win_rate_24h?: number | null
  pnl_24h?: number | null
  trades_24h?: number | null
  affinity?: {
    low_vol: number
    normal: number
    high_vol: number
  } | null
}

const DEFAULT_AFFINITY = { low_vol: 50, normal: 50, high_vol: 50 }

interface Memory {
  id: string
  title: string
  content: string
  category: string
  memory_type: string
  importance: number
  recall_count: number
  created_at: string
  coins: string[]
}

const AGENT_COLORS: Record<string, string> = {
  'scout': 'from-emerald-500 to-teal-600',
  'analyst': 'from-indigo-500 to-purple-600',
  'oracle': 'from-purple-500 to-pink-600',
  'tactician': 'from-amber-500 to-orange-600',
  'operator': 'from-blue-500 to-cyan-600',
  'sage': 'from-violet-500 to-purple-600',
}

export default function EvolutionPage() {
  const [status, setStatus] = useState<SwarmStatus | null>(null)
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [memories, setMemories] = useState<Memory[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  
  const [accountData] = useState({
    balance: 100000,
    initialBalance: 100000,
    totalFees: 0,
    slippageCost: 0,
    totalTrades: 0,
    winningTrades: 0,
    mode: 'paper' as const,
  })
  
  const { isConnected } = useWebSocket({ channel: 'all' })
  
  const fetchData = async () => {
    try {
      const [statusRes, strategiesRes, memoriesRes] = await Promise.all([
        fetch(`${API_URL}/ws/swarm/status`),
        fetch(`${API_URL}/api/strategies`),
        fetch(`${API_URL}/api/memories?limit=20`),
      ])
      
      if (statusRes.ok) {
        setStatus(await statusRes.json())
      }
      if (strategiesRes.ok) {
        setStrategies(await strategiesRes.json())
      }
      if (memoriesRes.ok) {
        setMemories(await memoriesRes.json())
      }
      
      setError(null)
    } catch (e) {
      setError('Failed to load swarm data')
      console.error(e)
    } finally {
      setLoading(false)
    }
  }
  
  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [])
  
  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar isConnected={isConnected} />
        <main className="flex-1 ml-[280px] p-8 flex items-center justify-center">
          <div className="text-center">
            <div className="w-16 h-16 border-4 border-violet-500 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
            <p className="text-text-muted">Loading swarm data...</p>
          </div>
        </main>
      </div>
    )
  }
  
  return (
    <div className="flex min-h-screen">
      <Sidebar isConnected={isConnected} />
      <main className="flex-1 ml-[280px] p-6 lg:p-8">
        <div className="space-y-6">
        {/* Header */}
        <header className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-text-primary tracking-tight flex items-center gap-3">
              <span className="text-3xl">🧬</span>
              <span>Evolution Dashboard</span>
            </h1>
            <p className="text-xs text-text-muted mt-1">Watch the swarm learn and evolve</p>
          </div>
          
          {/* Swarm status */}
          <div className={`px-4 py-2 rounded-xl ${
            status?.running ? 'bg-accent-emerald/10 text-accent-emerald border border-accent-emerald/30' : 'bg-surface-2 text-text-muted border border-white/5'
          }`}>
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                status?.running ? 'bg-accent-emerald animate-pulse' : 'bg-text-muted'
              }`} />
              <span className="font-medium text-sm">
                {status?.running ? 'Swarm Active' : 'Swarm Inactive'}
              </span>
            </div>
          </div>
        </header>
        
        {error && (
          <div className="bg-accent-red/10 border border-accent-red/30 text-accent-red px-4 py-3 rounded-xl">
            {error}
          </div>
        )}
        
        {/* Agent Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {status?.agents.map((agent) => (
            <div
              key={agent.id}
              className="glass-card p-5 hover:border-white/20 transition-all"
            >
              <div className="flex items-center gap-3 mb-4">
                <div className={`w-12 h-12 rounded-full bg-gradient-to-br ${
                  AGENT_COLORS[agent.id] || 'from-slate-500 to-slate-600'
                } flex items-center justify-center shadow-lg`}>
                  <span className="text-2xl">{agent.emoji}</span>
                </div>
                <div>
                  <h3 className="font-semibold text-text-primary">{agent.name}</h3>
                  <p className="text-xs text-text-muted">{agent.role}</p>
                </div>
              </div>
              
              <div className="space-y-3">
                {/* Energy bar */}
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-text-muted text-xs">Energy</span>
                    <span className="text-text-primary text-xs">{Math.round(agent.energy * 100)}%</span>
                  </div>
                  <div className="h-2 bg-surface-2 rounded-full overflow-hidden">
                    <div 
                      className={`h-full bg-gradient-to-r ${AGENT_COLORS[agent.id] || 'from-slate-500 to-slate-600'}`}
                      style={{ width: `${agent.energy * 100}%` }}
                    />
                  </div>
                </div>
                
                {/* Stats */}
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="bg-surface-2 rounded-lg p-2">
                    <div className="text-lg font-semibold text-text-primary">{agent.beliefs_count}</div>
                    <div className="text-xs text-text-muted">Beliefs</div>
                  </div>
                  <div className="bg-surface-2 rounded-lg p-2">
                    <div className="text-lg font-semibold text-text-primary">{agent.hypotheses_count}</div>
                    <div className="text-xs text-text-muted">Hypotheses</div>
                  </div>
                  <div className="bg-surface-2 rounded-lg p-2">
                    <div className="text-lg font-semibold text-text-primary">{agent.pending_signals}</div>
                    <div className="text-xs text-text-muted">Pending</div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
        
        {/* Strategy Evolution */}
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4 flex items-center gap-2">
            <span>🧬</span>
            <span>Strategy Gene Pool</span>
          </h2>
          
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left text-text-muted text-xs uppercase tracking-wider">
                  <th className="pb-3">Strategy</th>
                  <th className="pb-3">Weight</th>
                  <th className="pb-3">Win Rate (24h)</th>
                  <th className="pb-3">PnL (24h)</th>
                  <th className="pb-3">Trades (24h)</th>
                  <th className="pb-3">Regime Affinity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {strategies.map((strategy) => {
                  const pnl = strategy.pnl_24h ?? 0
                  const trades = strategy.trades_24h ?? 0
                  const winRate = strategy.win_rate_24h
                  const affinity = strategy.affinity ?? DEFAULT_AFFINITY
                  return (
                    <tr key={strategy.strategy} className="text-text-primary">
                      <td className="py-3 font-medium capitalize">{strategy.strategy.replace('_', ' ')}</td>
                      <td className="py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-20 h-2 bg-surface-2 rounded-full overflow-hidden">
                            <div 
                              className="h-full bg-accent-purple"
                              style={{ width: `${strategy.weight * 100}%` }}
                            />
                          </div>
                          <span className="text-sm text-text-muted">
                            {(strategy.weight * 100).toFixed(1)}%
                          </span>
                        </div>
                      </td>
                      <td className="py-3">
                        {winRate != null ? (
                          <span className={winRate >= 50 ? 'text-accent-emerald' : 'text-accent-red'}>
                            {winRate.toFixed(1)}%
                          </span>
                        ) : (
                          <span className="text-text-muted">-</span>
                        )}
                      </td>
                      <td className="py-3">
                        <span className={pnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'}>
                          {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}
                        </span>
                      </td>
                      <td className="py-3 text-text-muted">{trades}</td>
                      <td className="py-3">
                        <div className="flex gap-1">
                          <span className="px-2 py-0.5 text-xs rounded bg-accent-cyan/20 text-accent-cyan" title="Low Vol">
                            L:{affinity.low_vol}
                          </span>
                          <span className="px-2 py-0.5 text-xs rounded bg-surface-2 text-text-secondary" title="Normal">
                            N:{affinity.normal}
                          </span>
                          <span className="px-2 py-0.5 text-xs rounded bg-accent-red/20 text-accent-red" title="High Vol">
                            H:{affinity.high_vol}
                          </span>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
        
        {/* Memories */}
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold text-text-primary mb-4 flex items-center gap-2">
            <span>🧠</span>
            <span>Swarm Memory</span>
            <span className="text-sm font-normal text-text-muted ml-2">
              ({status?.memory.cached_memories || 0} cached)
            </span>
          </h2>
          
          {memories.length === 0 ? (
            <p className="text-text-muted text-center py-8">No memories yet. The swarm is learning...</p>
          ) : (
            <div className="space-y-3">
              {memories.map((memory) => (
                <div 
                  key={memory.id}
                  className="bg-surface-2 rounded-lg p-4 border border-white/5"
                >
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="font-medium text-text-primary">{memory.title}</h3>
                    <div className="flex items-center gap-2">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-accent-purple/20 text-accent-purple">
                        {memory.category}
                      </span>
                      <span className="text-xs text-text-muted">
                        ⭐ {(memory.importance * 100).toFixed(0)}
                      </span>
                    </div>
                  </div>
                  <p className="text-text-secondary text-sm">{memory.content}</p>
                  {memory.coins.length > 0 && (
                    <div className="mt-2 flex gap-1">
                      {memory.coins.map((coin) => (
                        <span key={coin} className="text-xs px-2 py-0.5 rounded bg-surface-1 text-text-secondary">
                          {coin}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
        
        {/* Network Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="glass-card p-6 text-center">
            <div className="text-4xl mb-2">📡</div>
            <div className="text-3xl font-semibold text-text-primary">{status?.signal_network.recent_signals || 0}</div>
            <div className="text-text-muted text-xs">Recent Signals</div>
          </div>
          
          <div className="glass-card p-6 text-center">
            <div className="text-4xl mb-2">🤖</div>
            <div className="text-3xl font-semibold text-text-primary">{status?.agent_count || 0}</div>
            <div className="text-text-muted text-xs">Active Agents</div>
          </div>
          
          <div className="glass-card p-6 text-center">
            <div className="text-4xl mb-2">🕐</div>
            <div className="text-xl font-semibold text-text-primary">
              {status?.started_at ? new Date(status.started_at).toLocaleTimeString('de-DE') : '-'}
            </div>
            <div className="text-text-muted text-xs">Started At</div>
          </div>
        </div>
      </div>
      </main>
    </div>
  )
}

