'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { 
  Globe, 
  TrendingUp,
  TrendingDown,
  Search,
  BarChart3,
  Building2,
  Shield,
  Cpu,
} from 'lucide-react'
import { clsx } from 'clsx'

import { Sidebar } from '@/components/Sidebar'
import { MobileHeader } from '@/components/MobileHeader'
import { useWebSocket } from '@/lib/websocket'
import { api } from '@/lib/api'

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

interface UniverseStock {
  symbol: string
  name: string
  sector: string
  exchange: string
  price_usd: number
  price_change_24h: number
  volume_24h: number
  market_cap: number
  sentiment_score: number
  narrative_strength: number
}

interface UniverseStats {
  tech_count: number
  defense_count: number
  total_count: number
  total_market_cap: number
  avg_sentiment_score: number
}

// ═══════════════════════════════════════════════════════════════════════════════
// STOCK CARD COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

function StockCard({ stock }: { stock: UniverseStock }) {
  const isPositive = stock.price_change_24h >= 0
  const isTech = stock.sector === 'TECHNOLOGY'
  
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="glass-card p-4 hover:border-accent-cyan/30 transition-all"
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-text-primary">{stock.symbol}</h3>
            {isTech ? (
              <Cpu className="w-3 h-3 text-accent-cyan" />
            ) : (
              <Shield className="w-3 h-3 text-accent-emerald" />
            )}
          </div>
          <p className="text-xs text-text-muted">{stock.name}</p>
        </div>
        <div className={clsx(
          'flex items-center gap-1 text-sm font-medium',
          isPositive ? 'text-accent-emerald' : 'text-accent-red'
        )}>
          {isPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
          {stock.price_change_24h.toFixed(1)}%
        </div>
      </div>
      
      <div className="text-lg font-mono font-semibold text-text-primary mb-3">
        ${stock.price_usd.toFixed(2)}
      </div>
      
      {/* Scores */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="text-center">
          <div className="text-xs text-text-muted mb-1">Sentiment</div>
          <div className={clsx(
            'text-sm font-medium',
            stock.sentiment_score > 50 ? 'text-accent-emerald' :
            stock.sentiment_score < -50 ? 'text-accent-red' : 'text-text-primary'
          )}>
            {stock.sentiment_score > 0 ? '+' : ''}{stock.sentiment_score.toFixed(0)}
          </div>
        </div>
        <div className="text-center">
          <div className="text-xs text-text-muted mb-1">Narrative</div>
          <div className="text-sm font-medium text-text-primary">
            {stock.narrative_strength.toFixed(0)}
          </div>
        </div>
      </div>
      
      {/* Footer */}
      <div className="flex items-center justify-between text-xs text-text-muted">
        <span>Vol: ${(stock.volume_24h / 1e6).toFixed(1)}M</span>
        <span className={clsx(
          'px-2 py-0.5 rounded',
          isTech ? 'bg-cyan-500/10 text-cyan-400' : 'bg-emerald-500/10 text-emerald-400'
        )}>
          {stock.sector === 'TECHNOLOGY' ? 'Tech' : 'Defense'}
        </span>
      </div>
    </motion.div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════════════════════════════════════════

export default function UniversePage() {
  const [loading, setLoading] = useState(true)
  const [universe, setUniverse] = useState<UniverseStock[]>([])
  const [stats, setStats] = useState<UniverseStats | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [sectorFilter, setSectorFilter] = useState<'all' | 'tech' | 'defense'>('all')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  
  const { isConnected } = useWebSocket({ channel: 'trading' })
  
  useEffect(() => {
    async function fetchData() {
      try {
        const [universeData, statsData] = await Promise.all([
          api.getUniverse('approved', 100).catch(() => []),
          api.getUniverseStats().catch(() => null),
        ])
        
        setUniverse(universeData as UniverseStock[])
        setStats(statsData as UniverseStats | null)
      } catch (error) {
        console.error('Failed to fetch universe data:', error)
      } finally {
        setLoading(false)
      }
    }
    
    fetchData()
    const interval = setInterval(fetchData, 60000) // Refresh every minute
    return () => clearInterval(interval)
  }, [])
  
  // Filter universe
  const filteredUniverse = universe.filter(stock => {
    const matchesSearch = stock.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
      stock.name?.toLowerCase().includes(searchQuery.toLowerCase())
    
    const matchesSector = sectorFilter === 'all' ||
      (sectorFilter === 'tech' && stock.sector === 'TECHNOLOGY') ||
      (sectorFilter === 'defense' && stock.sector === 'DEFENSE')
    
    return matchesSearch && matchesSector
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
          title="Stock Universe"
        />

        <div className="p-4 md:p-6 lg:p-8">
          {/* Header */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
            <div>
              <motion.h1 
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                className="text-xl md:text-2xl font-semibold text-text-primary tracking-tight flex items-center gap-3"
              >
                <Globe className="w-6 h-6 md:w-7 md:h-7 text-accent-cyan" />
                Stock Universe
              </motion.h1>
              <p className="text-xs text-text-muted mt-1">
                Tech and Defense stocks tracked for trading opportunities
              </p>
            </div>
            
            {/* Search */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
              <div className="relative flex-1 sm:flex-initial">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input
                  type="text"
                  placeholder="Search stocks..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full sm:w-64 pl-10 pr-4 py-2 bg-surface-2 border border-glass-border rounded-lg text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent-cyan/50"
                />
              </div>
              
              {/* Sector Filter */}
              <div className="flex gap-2">
                {(['all', 'tech', 'defense'] as const).map((sector) => (
                  <button
                    key={sector}
                    onClick={() => setSectorFilter(sector)}
                    className={clsx(
                      'flex-1 sm:flex-initial px-3 py-2 rounded-lg text-xs font-medium transition-all',
                      sectorFilter === sector
                        ? 'bg-accent-cyan/20 text-accent-cyan border border-accent-cyan/40'
                        : 'bg-surface-2 text-text-muted border border-glass-border hover:border-accent-cyan/30'
                    )}
                  >
                    {sector === 'all' ? 'All' : sector === 'tech' ? 'Tech' : 'Defense'}
                  </button>
                ))}
              </div>
            </div>
          </div>
          
          {/* Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 mb-6">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="glass-card p-3 md:p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <Building2 className="w-4 h-4 text-accent-cyan" />
                <span className="text-label">Total Stocks</span>
              </div>
              <div className="text-xl md:text-2xl font-mono font-semibold text-text-primary">
                {stats?.total_count || universe.length}
              </div>
            </motion.div>
            
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="glass-card p-3 md:p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <Cpu className="w-4 h-4 text-accent-cyan" />
                <span className="text-label">Tech</span>
              </div>
              <div className="text-xl md:text-2xl font-mono font-semibold text-accent-cyan">
                {stats?.tech_count || universe.filter(s => s.sector === 'TECHNOLOGY').length}
              </div>
            </motion.div>
            
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="glass-card p-3 md:p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <Shield className="w-4 h-4 text-accent-emerald" />
                <span className="text-label">Defense</span>
              </div>
              <div className="text-xl md:text-2xl font-mono font-semibold text-accent-emerald">
                {stats?.defense_count || universe.filter(s => s.sector === 'DEFENSE').length}
              </div>
            </motion.div>
            
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="glass-card p-3 md:p-4"
            >
              <div className="flex items-center gap-2 mb-2">
                <BarChart3 className="w-4 h-4 text-accent-amber" />
                <span className="text-label">Avg Sentiment</span>
              </div>
              <div className="text-xl md:text-2xl font-mono font-semibold text-accent-amber">
                {stats?.avg_sentiment_score?.toFixed(0) || '0'}
              </div>
            </motion.div>
          </div>
          
          {/* Stock Grid */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="glass-card p-4"
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-text-primary">
                Tracked Stocks ({filteredUniverse.length})
              </h2>
            </div>
            
            {loading ? (
              <div className="text-center py-12">
                <div className="w-8 h-8 border-2 border-accent-cyan border-t-transparent rounded-full animate-spin mx-auto mb-4" />
                <p className="text-text-muted">Loading stock universe...</p>
              </div>
            ) : filteredUniverse.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3 md:gap-4 max-h-[600px] overflow-y-auto">
                {filteredUniverse.map((stock, i) => (
                  <motion.div
                    key={stock.symbol}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.02 }}
                  >
                    <StockCard stock={stock} />
                  </motion.div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-text-muted">
                <Globe className="w-12 h-12 mx-auto mb-4 opacity-20" />
                <p>No stocks match your search criteria</p>
              </div>
            )}
          </motion.div>
        </div>
      </main>
    </div>
  )
}
