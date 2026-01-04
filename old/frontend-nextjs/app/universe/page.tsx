'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { 
  Globe, 
  TrendingUp,
  TrendingDown,
  Sparkles,
  CheckCircle,
  XCircle,
  Clock,
  Search,
  Twitter,
  BarChart3,
} from 'lucide-react'
import { clsx } from 'clsx'

import { Sidebar } from '@/components/Sidebar'
import { useWebSocket } from '@/lib/websocket'

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface UniverseCoin {
  coin: string
  name: string
  volume_24h: number
  market_cap: number
  price_usd: number
  price_change_24h: number
  hype_score: number
  sentiment_score: number
  narrative_strength: number
  discovery_source: string
  discovered_at: string
}

interface UniverseStats {
  approved_count: number
  pending_count: number
  rejected_count: number
  coingecko_count: number
  x_discovery_count: number
  total_volume: number
  avg_hype_score: number
}

interface XDiscovery {
  id: string
  coin: string
  tweet_text: string
  author: string
  engagement: {
    likes: number
    retweets: number
    score: number
  }
  narrative: string
  discovered_at: string
  added_to_universe: boolean
}

// ═══════════════════════════════════════════════════════════════════════════════
// COIN CARD COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

function CoinCard({ coin }: { coin: UniverseCoin }) {
  const isPositive = coin.price_change_24h >= 0
  
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="glass-card p-4 hover:border-accent-cyan/30 transition-all"
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-text-primary">{coin.coin}</h3>
          <p className="text-xs text-text-muted">{coin.name}</p>
        </div>
        <div className={clsx(
          'flex items-center gap-1 text-sm font-medium',
          isPositive ? 'text-accent-emerald' : 'text-accent-red'
        )}>
          {isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
          {coin.price_change_24h.toFixed(1)}%
        </div>
      </div>
      
      <div className="text-lg font-mono font-semibold text-text-primary mb-3">
        ${coin.price_usd < 1 ? coin.price_usd.toFixed(6) : coin.price_usd.toFixed(2)}
      </div>
      
      {/* Scores */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        <div className="text-center">
          <div className="text-xs text-text-muted mb-1">Hype</div>
          <div className={clsx(
            'text-sm font-medium',
            coin.hype_score > 70 ? 'text-accent-amber' :
            coin.hype_score > 40 ? 'text-text-primary' : 'text-text-muted'
          )}>
            {coin.hype_score.toFixed(0)}
          </div>
        </div>
        <div className="text-center">
          <div className="text-xs text-text-muted mb-1">Sentiment</div>
          <div className={clsx(
            'text-sm font-medium',
            coin.sentiment_score > 50 ? 'text-accent-emerald' :
            coin.sentiment_score < -50 ? 'text-accent-red' : 'text-text-primary'
          )}>
            {coin.sentiment_score > 0 ? '+' : ''}{coin.sentiment_score.toFixed(0)}
          </div>
        </div>
        <div className="text-center">
          <div className="text-xs text-text-muted mb-1">Narrative</div>
          <div className="text-sm font-medium text-text-primary">
            {coin.narrative_strength.toFixed(0)}
          </div>
        </div>
      </div>
      
      {/* Volume */}
      <div className="flex items-center justify-between text-xs text-text-muted">
        <span>Vol: ${(coin.volume_24h / 1e6).toFixed(1)}M</span>
        <span className={clsx(
          'px-2 py-0.5 rounded',
          coin.discovery_source === 'coingecko' ? 'bg-emerald-500/10 text-emerald-400' :
          coin.discovery_source.startsWith('x_') ? 'bg-blue-500/10 text-blue-400' :
          'bg-gray-500/10 text-gray-400'
        )}>
          {coin.discovery_source === 'coingecko' ? 'CoinGecko' : 'X Discovery'}
        </span>
      </div>
    </motion.div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// X DISCOVERY CARD
// ═══════════════════════════════════════════════════════════════════════════════

function XDiscoveryCard({ discovery }: { discovery: XDiscovery }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      className="p-4 border-b border-white/5 last:border-0"
    >
      <div className="flex items-start gap-3">
        <div className="p-2 bg-blue-500/10 rounded-lg">
          <Twitter className="w-4 h-4 text-blue-400" />
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-semibold text-accent-cyan">${discovery.coin}</span>
            {discovery.added_to_universe ? (
              <CheckCircle className="w-3 h-3 text-accent-emerald" />
            ) : (
              <Clock className="w-3 h-3 text-accent-amber" />
            )}
            <span className="text-xs text-text-muted ml-auto">
              {new Date(discovery.discovered_at).toLocaleTimeString()}
            </span>
          </div>
          
          <p className="text-sm text-text-secondary line-clamp-2 mb-2">
            {discovery.tweet_text}
          </p>
          
          <div className="flex items-center gap-4 text-xs text-text-muted">
            <span>❤️ {discovery.engagement.likes}</span>
            <span>🔁 {discovery.engagement.retweets}</span>
            {discovery.narrative && (
              <span className="px-2 py-0.5 bg-purple-500/10 text-purple-400 rounded">
                {discovery.narrative}
              </span>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════════════════════

export default function UniversePage() {
  const [universe, setUniverse] = useState<UniverseCoin[]>([])
  const [stats, setStats] = useState<UniverseStats | null>(null)
  const [discoveries, setDiscoveries] = useState<XDiscovery[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  
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
  
  // Fetch data
  useEffect(() => {
    const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    async function fetchData() {
      try {
        const [universeData, statsData, discoveriesData] = await Promise.all([
          fetch(`${API_URL}/api/universe?limit=100`).then(r => r.json()).catch(() => []),
          fetch(`${API_URL}/api/universe/stats`).then(r => r.json()).catch(() => null),
          fetch(`${API_URL}/api/x/discoveries?limit=20`).then(r => r.json()).catch(() => []),
        ])
        
        setUniverse(Array.isArray(universeData) ? universeData : [])
        setStats(statsData)
        setDiscoveries(Array.isArray(discoveriesData) ? discoveriesData : [])
      } catch (error) {
        console.error('Failed to fetch universe data:', error)
      } finally {
        setLoading(false)
      }
    }
    
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])
  
  // Filter universe
  const filteredUniverse = universe.filter(coin =>
    coin.coin.toLowerCase().includes(searchQuery.toLowerCase()) ||
    coin.name?.toLowerCase().includes(searchQuery.toLowerCase())
  )
  
  if (loading) {
    return (
      <div className="flex min-h-screen">
        <Sidebar isConnected={isConnected} />
        <main className="flex-1 ml-[280px] p-8 flex items-center justify-center">
          <div className="text-center">
            <Globe className="w-12 h-12 mx-auto mb-4 text-cyan-400 animate-spin" />
            <p className="text-text-muted">Loading Dynamic Universe...</p>
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
              <Globe className="w-7 h-7 text-cyan-400" />
              Dynamic Universe
            </motion.h1>
            <p className="text-xs text-text-muted mt-1">
              Auto-discovered tradable assets from CoinGecko and X
            </p>
          </div>
          
          {/* Search */}
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
            <input
              type="text"
              placeholder="Search coins..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 pr-4 py-2 bg-surface-2 border border-white/10 rounded-lg text-sm text-text-primary placeholder:text-text-muted focus:border-accent-cyan/50 focus:outline-none"
            />
          </div>
        </header>
        
        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-5 gap-4 mb-8">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-card p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <CheckCircle className="w-4 h-4 text-accent-emerald" />
                <span className="text-xs text-text-muted">Approved</span>
              </div>
              <div className="text-2xl font-semibold text-text-primary">
                {stats.approved_count}
              </div>
            </motion.div>
            
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 }}
              className="glass-card p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <Clock className="w-4 h-4 text-accent-amber" />
                <span className="text-xs text-text-muted">Pending</span>
              </div>
              <div className="text-2xl font-semibold text-text-primary">
                {stats.pending_count}
              </div>
            </motion.div>
            
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="glass-card p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <Twitter className="w-4 h-4 text-blue-400" />
                <span className="text-xs text-text-muted">X Discoveries</span>
              </div>
              <div className="text-2xl font-semibold text-text-primary">
                {stats.x_discovery_count}
              </div>
            </motion.div>
            
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15 }}
              className="glass-card p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <BarChart3 className="w-4 h-4 text-accent-cyan" />
                <span className="text-xs text-text-muted">Total Volume</span>
              </div>
              <div className="text-2xl font-semibold text-text-primary">
                ${(stats.total_volume / 1e9).toFixed(1)}B
              </div>
            </motion.div>
            
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="glass-card p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <Sparkles className="w-4 h-4 text-accent-amber" />
                <span className="text-xs text-text-muted">Avg Hype</span>
              </div>
              <div className="text-2xl font-semibold text-text-primary">
                {stats.avg_hype_score.toFixed(0)}
              </div>
            </motion.div>
          </div>
        )}
        
        <div className="grid grid-cols-12 gap-6">
          {/* Left - Coin Grid */}
          <div className="col-span-8">
            <div className="glass-card p-6">
              <h3 className="text-sm font-medium text-text-primary mb-4">
                Tradable Universe ({filteredUniverse.length} coins)
              </h3>
              
              <div className="grid grid-cols-3 gap-4 max-h-[600px] overflow-y-auto">
                {filteredUniverse.map((coin, i) => (
                  <motion.div
                    key={coin.coin}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.02 }}
                  >
                    <CoinCard coin={coin} />
                  </motion.div>
                ))}
              </div>
            </div>
          </div>
          
          {/* Right - X Discoveries */}
          <div className="col-span-4">
            <div className="glass-card p-6">
              <h3 className="text-sm font-medium text-text-primary mb-4 flex items-center gap-2">
                <Twitter className="w-4 h-4 text-blue-400" />
                X Discoveries
              </h3>
              
              <div className="max-h-[600px] overflow-y-auto">
                {discoveries.length === 0 ? (
                  <div className="text-center py-8 text-text-muted">
                    <Twitter className="w-8 h-8 mx-auto mb-2 opacity-30" />
                    <p className="text-sm">No X discoveries yet</p>
                  </div>
                ) : (
                  discoveries.map(discovery => (
                    <XDiscoveryCard key={discovery.id} discovery={discovery} />
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

