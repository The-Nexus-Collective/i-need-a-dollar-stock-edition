'use client'

import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { clsx } from 'clsx'
import {
  Clock,
  TrendingUp,
  Moon,
  Sunrise,
  Sunset,
  AlertTriangle,
  X,
} from 'lucide-react'
import { api } from '@/lib/api'

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

export interface MarketStatus {
  status: 'OPEN' | 'CLOSED' | 'PRE_MARKET' | 'AFTER_HOURS'
  description: string
  detail: string
  is_open: boolean
  trading_allowed: boolean
  seconds_until_open: number | null
  seconds_until_close: number | null
  next_open: string | null
  next_close: string | null
  next_open_display: string | null
  data_source?: 'polygon.io' | 'local'
  polygon_api_available?: boolean
}

interface MarketStatusBannerProps {
  className?: string
  onStatusChange?: (status: MarketStatus) => void
  compact?: boolean
}

// ═══════════════════════════════════════════════════════════════════════════════
// STATUS CONFIG
// ═══════════════════════════════════════════════════════════════════════════════

const statusConfig = {
  OPEN: {
    Icon: TrendingUp,
    label: 'Market Open',
    color: 'text-accent-emerald',
    bg: 'bg-accent-emerald/10',
    border: 'border-accent-emerald/30',
    dot: 'bg-accent-emerald animate-pulse',
    gradient: 'from-accent-emerald/20 to-transparent',
  },
  CLOSED: {
    Icon: Moon,
    label: 'Market Closed',
    color: 'text-slate-400',
    bg: 'bg-slate-500/10',
    border: 'border-slate-500/30',
    dot: 'bg-slate-400',
    gradient: 'from-slate-500/20 to-transparent',
  },
  PRE_MARKET: {
    Icon: Sunrise,
    label: 'Pre-Market',
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    dot: 'bg-amber-400 animate-pulse',
    gradient: 'from-amber-500/20 to-transparent',
  },
  AFTER_HOURS: {
    Icon: Sunset,
    label: 'After Hours',
    color: 'text-purple-400',
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/30',
    dot: 'bg-purple-400',
    gradient: 'from-purple-500/20 to-transparent',
  },
}

// ═══════════════════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════════════════

function formatCountdown(seconds: number): string {
  if (seconds <= 0) return '0m'
  
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  
  if (hours >= 24) {
    const days = Math.floor(hours / 24)
    const remainingHours = hours % 24
    return `${days}d ${remainingHours}h`
  }
  
  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  
  return `${minutes}m`
}

// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function MarketStatusBanner({ 
  className, 
  onStatusChange, 
  compact = false 
}: MarketStatusBannerProps) {
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(null)
  const [countdown, setCountdown] = useState<string>('')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [dismissed, setDismissed] = useState(false)

  // Fetch market status
  const fetchStatus = useCallback(async () => {
    try {
      const status = await api.getMarketStatus()
      setMarketStatus(status)
      setError(null)
      onStatusChange?.(status)
    } catch (e) {
      console.error('Failed to fetch market status:', e)
      setError('Failed to load market status')
    } finally {
      setIsLoading(false)
    }
  }, [onStatusChange])

  // Initial fetch and polling
  useEffect(() => {
    fetchStatus()
    // Poll every 30 seconds
    const interval = setInterval(fetchStatus, 30000)
    return () => clearInterval(interval)
  }, [fetchStatus])

  // Countdown timer
  useEffect(() => {
    if (!marketStatus) return

    const updateCountdown = () => {
      if (marketStatus.is_open && marketStatus.seconds_until_close) {
        setCountdown(formatCountdown(marketStatus.seconds_until_close))
      } else if (!marketStatus.is_open && marketStatus.seconds_until_open) {
        setCountdown(formatCountdown(marketStatus.seconds_until_open))
      } else {
        setCountdown('')
      }
    }

    updateCountdown()
    const interval = setInterval(() => {
      // Decrement locally for smoother countdown
      if (marketStatus.is_open && marketStatus.seconds_until_close) {
        marketStatus.seconds_until_close = Math.max(0, marketStatus.seconds_until_close - 1)
      } else if (!marketStatus.is_open && marketStatus.seconds_until_open) {
        marketStatus.seconds_until_open = Math.max(0, marketStatus.seconds_until_open - 1)
      }
      updateCountdown()
    }, 1000)

    return () => clearInterval(interval)
  }, [marketStatus])

  // Don't show if dismissed or loading
  if (dismissed || isLoading || !marketStatus) {
    return null
  }

  const config = statusConfig[marketStatus.status]
  const Icon = config.Icon

  // Show warning banner when market is closed
  if (!marketStatus.trading_allowed && !compact) {
    return (
      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          className={clsx(
            'relative overflow-hidden rounded-xl border',
            config.border,
            config.bg,
            className
          )}
        >
          {/* Background gradient */}
          <div className={clsx(
            'absolute inset-0 bg-gradient-to-r',
            config.gradient,
            'pointer-events-none'
          )} />
          
          <div className="relative flex items-center justify-between p-4">
            <div className="flex items-center gap-4">
              {/* Icon */}
              <div className={clsx(
                'w-12 h-12 rounded-xl flex items-center justify-center',
                config.bg,
                'border',
                config.border
              )}>
                <Icon className={clsx('w-6 h-6', config.color)} />
              </div>
              
              {/* Text */}
              <div>
                <div className="flex items-center gap-2">
                  <div className={clsx('w-2 h-2 rounded-full', config.dot)} />
                  <span className={clsx('font-semibold', config.color)}>
                    {config.label}
                  </span>
                  {countdown && (
                    <span className="text-text-muted text-sm font-mono">
                      ({marketStatus.is_open ? `${countdown} until close` : `${countdown} until open`})
                    </span>
                  )}
                </div>
                <p className="text-sm text-text-secondary mt-0.5">
                  {marketStatus.description}
                  {marketStatus.next_open_display && !marketStatus.is_open && (
                    <span className="text-text-muted"> • Opens {marketStatus.next_open_display}</span>
                  )}
                  {marketStatus.data_source && (
                    <span className="text-text-dim text-xs ml-2">
                      via {marketStatus.data_source === 'polygon.io' ? '🔷 Polygon.io' : '📅 Local'}
                    </span>
                  )}
                </p>
              </div>
            </div>

            {/* Warning & Dismiss */}
            <div className="flex items-center gap-3">
              {!marketStatus.trading_allowed && (
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-accent-amber/10 border border-accent-amber/30">
                  <AlertTriangle className="w-4 h-4 text-accent-amber" />
                  <span className="text-sm text-accent-amber font-medium">
                    Trading Paused
                  </span>
                </div>
              )}
              
              <button
                onClick={() => setDismissed(true)}
                className="p-2 rounded-lg hover:bg-white/5 transition-colors text-text-muted hover:text-text-secondary"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        </motion.div>
      </AnimatePresence>
    )
  }

  // Compact version (always show, just smaller)
  return (
    <div className={clsx(
      'flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm',
      config.bg,
      config.border,
      className
    )}>
      <div className={clsx('w-2 h-2 rounded-full', config.dot)} />
      <Icon className={clsx('w-4 h-4', config.color)} />
      <span className={clsx('font-medium', config.color)}>
        {marketStatus.status === 'OPEN' ? 'Open' : 'Closed'}
      </span>
      {countdown && (
        <span className="text-text-muted font-mono text-xs">
          {countdown}
        </span>
      )}
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// COMPACT INDICATOR (for headers)
// ═══════════════════════════════════════════════════════════════════════════════

export function MarketStatusIndicator({ className }: { className?: string }) {
  return <MarketStatusBanner compact className={className} />
}

