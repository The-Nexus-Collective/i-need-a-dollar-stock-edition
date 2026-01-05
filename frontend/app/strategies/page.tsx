'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { 
  Zap,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Layers,
  Target,
  Activity,
} from 'lucide-react'
import { clsx } from 'clsx'

import { Sidebar } from '@/components/Sidebar'
import { MobileHeader } from '@/components/MobileHeader'
import { useWebSocket } from '@/lib/websocket'

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

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

// Default affinity values
const DEFAULT_AFFINITY = { low_vol: 50, normal: 50, high_vol: 50 }

// ═══════════════════════════════════════════════════════════════════════════════
// STRATEGY DESCRIPTIONS
// ═══════════════════════════════════════════════════════════════════════════════

const STRATEGY_INFO: Record<string, { 
  description: string
  icon: React.ReactNode
  color: string
  bestIn: string
}> = {
  momentum: {
    description: 'Rides strong trends, following sentiment direction with high conviction',
    icon: <TrendingUp className="w-5 h-5" />,
    color: 'from-blue-500 to-cyan-500',
    bestIn: 'Low/Normal volatility',
  },
  mean_reversion: {
    description: 'Fades extreme readings, expecting price to revert to mean',
    icon: <RefreshCw className="w-5 h-5" />,
    color: 'from-purple-500 to-pink-500',
    bestIn: 'Normal volatility, ranging',
  },
  hype_following: {
    description: 'Trades high-engagement coins from X with strong narratives',
    icon: <Zap className="w-5 h-5" />,
    color: 'from-amber-500 to-orange-500',
    bestIn: 'Euphoria, trending markets',
  },
  contrarian: {
    description: 'Goes against extreme crowd sentiment, betting on reversal',
    icon: <Target className="w-5 h-5" />,
    color: 'from-red-500 to-rose-500',
    bestIn: 'High volatility, panic',
  },
  volatility_expansion: {
    description: 'Catches breakouts from low volatility, riding initial moves',
    icon: <Activity className="w-5 h-5" />,
    color: 'from-emerald-500 to-teal-500',
    bestIn: 'Low volatility breakouts',
  },
  narrative_driven: {
    description: 'Trades dominant market themes and narratives (AI, DeFi, etc)',
    icon: <Layers className="w-5 h-5" />,
    color: 'from-indigo-500 to-violet-500',
    bestIn: 'Clear thematic trends',
  },
}

// ═══════════════════════════════════════════════════════════════════════════════
// STRATEGY CARD
// ═══════════════════════════════════════════════════════════════════════════════

function StrategyCard({ strategy }: { strategy: Strategy }) {
  const info = STRATEGY_INFO[strategy.strategy] || {
    description: 'Unknown strategy',
    icon: <Zap className="w-5 h-5" />,
    color: 'from-gray-500 to-gray-600',
    bestIn: 'Unknown',
  }
  
  const pnl = strategy.pnl_24h ?? 0
  const trades = strategy.trades_24h ?? 0
  const winRate = strategy.win_rate_24h
  const affinity = strategy.affinity ?? DEFAULT_AFFINITY
  const isPositive = pnl >= 0
  const weightPercent = (strategy.weight * 100).toFixed(0)
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-6 hover:border-white/20 transition-all"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={clsx(
            'w-10 h-10 rounded-xl flex items-center justify-center text-white',
            'bg-gradient-to-br',
            info.color
          )}>
            {info.icon}
          </div>
          <div>
            <h3 className="font-semibold text-text-primary capitalize">
              {(strategy.strategy || 'unknown').replace('_', ' ')}
            </h3>
            <p className="text-xs text-text-muted">{info.bestIn}</p>
          </div>
        </div>
        
        {/* Weight Badge */}
        <div className={clsx(
          'px-3 py-1 rounded-full text-sm font-semibold',
          'bg-gradient-to-r',
          info.color,
          'text-white shadow-lg'
        )}>
          {weightPercent}%
        </div>
      </div>
      
      {/* Description */}
      <p className="text-sm text-text-secondary mb-4">
        {info.description}
      </p>
      
      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="text-center p-2 bg-surface-2 rounded-lg">
          <div className={clsx(
            'text-lg font-semibold',
            isPositive ? 'text-accent-emerald' : 'text-accent-red'
          )}>
            {isPositive ? '+' : ''}{pnl.toFixed(0)}
          </div>
          <div className="text-xs text-text-muted">PnL 24h</div>
        </div>
        
        <div className="text-center p-2 bg-surface-2 rounded-lg">
          <div className="text-lg font-semibold text-text-primary">
            {trades}
          </div>
          <div className="text-xs text-text-muted">Trades</div>
        </div>
        
        <div className="text-center p-2 bg-surface-2 rounded-lg">
          <div className={clsx(
            'text-lg font-semibold',
            winRate != null && winRate >= 50 
              ? 'text-accent-emerald' 
              : 'text-accent-amber'
          )}>
            {winRate != null ? winRate.toFixed(0) : '-'}%
          </div>
          <div className="text-xs text-text-muted">Win Rate</div>
        </div>
      </div>
      
      {/* Regime Affinity */}
      <div>
        <span className="text-xs text-text-muted mb-2 block">Regime Affinity</span>
        <div className="flex gap-2">
          <AffinityBar label="Low Vol" value={affinity.low_vol} />
          <AffinityBar label="Normal" value={affinity.normal} />
          <AffinityBar label="High Vol" value={affinity.high_vol} />
        </div>
      </div>
    </motion.div>
  )
}

function AffinityBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex-1">
      <div className="flex justify-between text-xs mb-1">
        <span className="text-text-muted">{label}</span>
        <span className="text-text-secondary">{value}</span>
      </div>
      <div className="h-1.5 bg-surface-2 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className={clsx(
            'h-full rounded-full',
            value >= 70 ? 'bg-accent-emerald' :
            value >= 50 ? 'bg-accent-cyan' :
            value >= 30 ? 'bg-accent-amber' : 'bg-accent-red'
          )}
        />
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════════════════════

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([])
  const [loading, setLoading] = useState(true)
  const [marketRegime, setMarketRegime] = useState('normal')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  
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
  
  useEffect(() => {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080'
    async function fetchData() {
      try {
        const data = await fetch(`${API_URL}/api/strategies`).then(r => r.json())
        if (Array.isArray(data)) setStrategies(data)
      } catch (error) {
        console.error('Failed to fetch strategies:', error)
      } finally {
        setLoading(false)
      }
    }
    
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])
  
  // Calculate total weight
  const totalWeight = strategies.reduce((sum, s) => sum + s.weight, 0)
  const totalPnL = strategies.reduce((sum, s) => sum + (s.pnl_24h ?? 0), 0)
  const totalTrades = strategies.reduce((sum, s) => sum + (s.trades_24h ?? 0), 0)
  
  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar isConnected={isConnected} mobileOpen={mobileMenuOpen} onMobileClose={() => setMobileMenuOpen(false)} />
        <main className="flex-1 md:ml-[280px] p-8 flex items-center justify-center">
          <div className="text-center">
            <Zap className="w-12 h-12 mx-auto mb-4 text-pink-400 animate-pulse" />
            <p className="text-text-muted">Loading Strategy Ensemble...</p>
          </div>
        </main>
      </div>
    )
  }
  
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
          title="Strategies"
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
              <Zap className="w-6 sm:w-7 h-6 sm:h-7 text-pink-400" />
              Strategy Ensemble
            </motion.h1>
            <p className="text-xs text-text-muted mt-1">
              6 sub-strategies with meta-learning weights
            </p>
          </div>
          
          {/* Market Regime */}
          <div className={clsx(
            'px-4 py-2 rounded-xl text-sm font-medium',
            marketRegime === 'low_vol' && 'bg-blue-500/10 text-blue-400 border border-blue-500/30',
            marketRegime === 'normal' && 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30',
            marketRegime === 'high_vol' && 'bg-amber-500/10 text-amber-400 border border-amber-500/30',
            marketRegime === 'euphoria' && 'bg-pink-500/10 text-pink-400 border border-pink-500/30',
            marketRegime === 'panic' && 'bg-red-500/10 text-red-400 border border-red-500/30',
          )}>
            Regime: {marketRegime.replace('_', ' ').toUpperCase()}
          </div>
        </header>
        
        {/* Summary Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card p-4"
          >
            <div className="text-xs text-text-muted mb-1">Active Strategies</div>
            <div className="text-2xl font-semibold text-text-primary">
              {strategies.length}
            </div>
          </motion.div>
          
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="glass-card p-4"
          >
            <div className="text-xs text-text-muted mb-1">Total Weight</div>
            <div className="text-2xl font-semibold text-text-primary">
              {(totalWeight * 100).toFixed(0)}%
            </div>
          </motion.div>
          
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card p-4"
          >
            <div className="text-xs text-text-muted mb-1">24h PnL</div>
            <div className={clsx(
              'text-2xl font-semibold',
              totalPnL >= 0 ? 'text-accent-emerald' : 'text-accent-red'
            )}>
              {totalPnL >= 0 ? '+' : ''}{totalPnL.toFixed(0)}
            </div>
          </motion.div>
          
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className="glass-card p-4"
          >
            <div className="text-xs text-text-muted mb-1">24h Trades</div>
            <div className="text-2xl font-semibold text-text-primary">
              {totalTrades}
            </div>
          </motion.div>
        </div>
        
        {/* Strategy Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 md:gap-6">
          {strategies.map((strategy, i) => (
            <motion.div
              key={strategy.strategy}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
            >
              <StrategyCard strategy={strategy} />
            </motion.div>
          ))}
        </div>
        
        {/* Meta-Learning Info */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.6 }}
          className="mt-8 glass-card p-6"
        >
          <h3 className="text-sm font-medium text-text-primary mb-4">
            How Meta-Learning Works
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6 text-sm text-text-secondary">
            <div>
              <div className="text-accent-cyan font-medium mb-1">1. Regime Detection</div>
              <p>The system identifies the current market regime (low vol, normal, high vol, euphoria, panic) based on volatility and sentiment metrics.</p>
            </div>
            <div>
              <div className="text-accent-emerald font-medium mb-1">2. Weight Adjustment</div>
              <p>Strategies with high affinity for the current regime get higher weights. Weights are normalized so they sum to 100%.</p>
            </div>
            <div>
              <div className="text-accent-amber font-medium mb-1">3. Performance Learning</div>
              <p>After each trade, the Learner Agent adjusts affinity scores based on outcomes. Winning strategies in specific regimes get boosted.</p>
            </div>
          </div>
        </motion.div>
        </div>
      </main>
    </div>
  )
}

