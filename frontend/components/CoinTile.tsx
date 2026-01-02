'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { clsx } from 'clsx'
import { 
  TrendingUp, 
  TrendingDown, 
  AlertTriangle, 
  BarChart2,
  Check,
  X,
  Info
} from 'lucide-react'

interface CoinSignal {
  coin: string
  sentimentScore: number
  narrativeStrength: number
  combinedScore: number
  price?: number
  priceChange24h?: number
  filterScorePass: boolean
  filterVolumePass: boolean
  recommendedAction?: 'long' | 'short' | 'none'
}

interface CoinTileProps {
  signal: CoinSignal
  isSelected?: boolean
  onClick?: () => void
}

// Coin icons/logos (simplified colored circles)
const coinColors: Record<string, { primary: string; secondary: string }> = {
  BTC: { primary: '#f7931a', secondary: '#f7931a33' },
  ETH: { primary: '#627eea', secondary: '#627eea33' },
  SOL: { primary: '#00ffa3', secondary: '#00ffa333' },
  XRP: { primary: '#23292f', secondary: '#23292f33' },
  DOGE: { primary: '#c2a633', secondary: '#c2a63333' },
  BNB: { primary: '#f3ba2f', secondary: '#f3ba2f33' },
  ADA: { primary: '#0033ad', secondary: '#0033ad33' },
  AVAX: { primary: '#e84142', secondary: '#e8414233' },
  TRX: { primary: '#ff0013', secondary: '#ff001333' },
  LINK: { primary: '#2a5ada', secondary: '#2a5ada33' },
}

export function CoinTile({ signal, isSelected, onClick }: CoinTileProps) {
  const [showTooltip, setShowTooltip] = useState(false)
  
  const score = signal.combinedScore
  const isPositive = score > 0
  const intensity = Math.min(Math.abs(score) / 100, 1) // 0 to 1

  // Determine color based on score
  const getScoreColor = () => {
    if (score >= 50) return 'text-accent-emerald text-glow-emerald'
    if (score >= 15) return 'text-accent-emerald'
    if (score <= -50) return 'text-accent-red text-glow-red'
    if (score <= -15) return 'text-accent-red'
    return 'text-accent-amber'
  }

  const getBorderGlow = () => {
    if (!signal.filterScorePass || !signal.filterVolumePass) {
      return 'border-text-dim/30'
    }
    if (score >= 50) return 'border-glow-emerald'
    if (score >= 15) return 'border-accent-emerald/30'
    if (score <= -50) return 'border-glow-red'
    if (score <= -15) return 'border-accent-red/30'
    return 'border-accent-amber/30'
  }

  const getBackgroundGradient = () => {
    if (!signal.filterScorePass || !signal.filterVolumePass) {
      return 'bg-surface/50'
    }
    if (score >= 15) return 'gradient-bg-positive'
    if (score <= -15) return 'gradient-bg-negative'
    return 'gradient-bg-neutral'
  }

  const coinColor = coinColors[signal.coin] || { primary: '#00d4ff', secondary: '#00d4ff33' }
  const passedFilters = signal.filterScorePass && signal.filterVolumePass

  return (
    <motion.div
      whileHover={{ scale: 1.02, y: -4 }}
      whileTap={{ scale: 0.98 }}
      onClick={onClick}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
      className={clsx(
        'relative cursor-pointer rounded-2xl border p-4 transition-all duration-300',
        getBackgroundGradient(),
        getBorderGlow(),
        isSelected && 'ring-2 ring-accent-cyan ring-offset-2 ring-offset-void',
        !passedFilters && 'opacity-60'
      )}
      style={{
        boxShadow: passedFilters && Math.abs(score) >= 50
          ? `0 0 30px ${isPositive ? 'rgba(0,255,136,0.15)' : 'rgba(255,71,87,0.15)'}`
          : undefined,
      }}
    >
      {/* Coin header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {/* Coin icon */}
          <div 
            className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
            style={{ 
              background: coinColor.secondary,
              color: coinColor.primary,
              boxShadow: `0 0 10px ${coinColor.secondary}`,
            }}
          >
            {signal.coin.slice(0, 2)}
          </div>
          <div>
            <span className="font-semibold text-text-primary">{signal.coin}</span>
            {signal.price && (
              <p className="text-[10px] text-text-muted font-mono">
                ${signal.price.toLocaleString('en-US', { maximumFractionDigits: 2 })}
              </p>
            )}
          </div>
        </div>

        {/* Filter status */}
        <div className="flex gap-1">
          <div className={clsx(
            'w-5 h-5 rounded flex items-center justify-center',
            signal.filterScorePass 
              ? 'bg-accent-emerald/20 text-accent-emerald' 
              : 'bg-accent-red/20 text-accent-red'
          )}>
            {signal.filterScorePass ? <Check className="w-3 h-3" /> : <X className="w-3 h-3" />}
          </div>
          <div className={clsx(
            'w-5 h-5 rounded flex items-center justify-center',
            signal.filterVolumePass 
              ? 'bg-accent-emerald/20 text-accent-emerald' 
              : 'bg-accent-red/20 text-accent-red'
          )}>
            <BarChart2 className="w-3 h-3" />
          </div>
        </div>
      </div>

      {/* Score display */}
      <div className="text-center mb-3">
        <motion.span
          key={score}
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          className={clsx('text-3xl font-mono font-bold', getScoreColor())}
        >
          {score > 0 ? '+' : ''}{score.toFixed(0)}
        </motion.span>
      </div>

      {/* Sentiment breakdown */}
      <div className="grid grid-cols-2 gap-2 text-center">
        <div className="bg-void/30 rounded-lg p-2">
          <span className="text-[9px] text-text-muted uppercase tracking-wider block">Sentiment</span>
          <span className={clsx(
            'text-sm font-mono font-semibold',
            signal.sentimentScore > 0 ? 'text-accent-emerald' : signal.sentimentScore < 0 ? 'text-accent-red' : 'text-text-secondary'
          )}>
            {signal.sentimentScore > 0 ? '+' : ''}{signal.sentimentScore.toFixed(0)}
          </span>
        </div>
        <div className="bg-void/30 rounded-lg p-2">
          <span className="text-[9px] text-text-muted uppercase tracking-wider block">Strength</span>
          <span className="text-sm font-mono font-semibold text-accent-cyan">
            {signal.narrativeStrength.toFixed(0)}%
          </span>
        </div>
      </div>

      {/* Action badge */}
      {passedFilters && signal.recommendedAction && signal.recommendedAction !== 'none' && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className={clsx(
            'absolute -bottom-2 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-wider',
            signal.recommendedAction === 'long' 
              ? 'bg-accent-emerald text-void shadow-glow-emerald' 
              : 'bg-accent-red text-void shadow-glow-red'
          )}
        >
          {signal.recommendedAction === 'long' ? (
            <span className="flex items-center gap-1">
              <TrendingUp className="w-3 h-3" /> LONG
            </span>
          ) : (
            <span className="flex items-center gap-1">
              <TrendingDown className="w-3 h-3" /> SHORT
            </span>
          )}
        </motion.div>
      )}

      {/* Tooltip */}
      <AnimatePresence>
        {showTooltip && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 w-56"
          >
            <div className="glass-card p-3 text-xs">
              <div className="flex items-center gap-2 mb-2 text-text-primary font-medium">
                <Info className="w-3 h-3 text-accent-cyan" />
                Signal Details
              </div>
              <div className="space-y-1 text-text-secondary">
                <div className="flex justify-between">
                  <span>Combined Score</span>
                  <span className={getScoreColor()}>{score.toFixed(1)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Score Filter</span>
                  <span className={signal.filterScorePass ? 'text-accent-emerald' : 'text-accent-red'}>
                    {signal.filterScorePass ? 'Pass' : 'Fail'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Volume Filter</span>
                  <span className={signal.filterVolumePass ? 'text-accent-emerald' : 'text-accent-red'}>
                    {signal.filterVolumePass ? 'Pass' : 'Fail'}
                  </span>
                </div>
                {!passedFilters && (
                  <div className="mt-2 pt-2 border-t border-glass-border text-accent-amber flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    Filtered out - no trade
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// Grid wrapper for all coins
interface CoinGridProps {
  signals: CoinSignal[]
  selectedCoin?: string
  onSelectCoin?: (coin: string) => void
}

export function CoinGrid({ signals, selectedCoin, onSelectCoin }: CoinGridProps) {
  // Filter out signals with no data (all zeros)
  const validSignals = signals.filter(s => 
    s.sentimentScore !== 0 || s.narrativeStrength !== 0 || s.combinedScore !== 0
  )
  
  // Sort by absolute combined score
  const sortedSignals = [...validSignals].sort((a, b) => 
    Math.abs(b.combinedScore) - Math.abs(a.combinedScore)
  )

  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-4">
        <span className="text-label">10-Coin Sentiment Matrix</span>
        <span className="text-[10px] text-text-muted">
          {sortedSignals.length > 0 ? 'Sorted by score intensity' : 'Waiting for signals...'}
        </span>
      </div>
      
      {sortedSignals.length > 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
          {sortedSignals.map((signal, index) => (
            <motion.div
              key={signal.coin}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
            >
              <CoinTile
                signal={signal}
                isSelected={selectedCoin === signal.coin}
                onClick={() => onSelectCoin?.(signal.coin)}
              />
            </motion.div>
          ))}
        </div>
      ) : (
        <div className="text-center py-12">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-void/50 flex items-center justify-center">
            <BarChart2 className="w-8 h-8 text-text-dim" />
          </div>
          <p className="text-text-muted font-medium mb-1">Keine Sentiment-Signale</p>
          <p className="text-text-dim text-xs max-w-xs mx-auto">
            Signale werden angezeigt sobald der Bot die Grok API abfragt (stündlich).
          </p>
        </div>
      )}
    </div>
  )
}

