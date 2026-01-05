'use client'

import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { clsx } from 'clsx'
import { 
  TrendingUp, 
  TrendingDown, 
  Target, 
  ShieldAlert,
  Clock,
  DollarSign,
  Percent,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'

interface Position {
  id: string
  symbol: string
  side: 'long' | 'short'
  quantity: number
  entryPrice: number
  currentPrice: number
  stopLoss: number
  takeProfit: number
  unrealizedPnl: number
  openedAt: string
  fee?: number
}

interface PositionCardProps {
  position: Position
}

export function PositionCard({ position }: PositionCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [prevPnl, setPrevPnl] = useState(position.unrealizedPnl)
  const [pnlFlash, setPnlFlash] = useState<'up' | 'down' | null>(null)

  const isLong = position.side === 'long'
  const pnl = position.unrealizedPnl ?? 0
  const isProfitable = pnl >= 0
  const positionValue = (position.quantity ?? 0) * (position.entryPrice ?? 0)
  const pnlPercent = positionValue > 0 && !isNaN(pnl) ? (pnl / positionValue) * 100 : 0

  // Calculate progress to SL/TP
  const priceRange = position.takeProfit - position.stopLoss
  const currentProgress = ((position.currentPrice - position.stopLoss) / priceRange) * 100
  const entryProgress = ((position.entryPrice - position.stopLoss) / priceRange) * 100

  // Flash effect on PnL change
  useEffect(() => {
    if (pnl !== prevPnl) {
      setPnlFlash(pnl > prevPnl ? 'up' : 'down')
      setPrevPnl(pnl)
      const timer = setTimeout(() => setPnlFlash(null), 500)
      return () => clearTimeout(timer)
    }
  }, [pnl, prevPnl])

  // Time since opened
  const openedDate = position.openedAt ? new Date(position.openedAt) : null
  const isValidDate = openedDate && !isNaN(openedDate.getTime())
  const now = new Date()
  const hoursOpen = isValidDate ? Math.floor((now.getTime() - openedDate.getTime()) / (1000 * 60 * 60)) : 0
  const minutesOpen = isValidDate ? Math.floor(((now.getTime() - openedDate.getTime()) / (1000 * 60)) % 60) : 0

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className={clsx(
        'glass-card overflow-hidden transition-all duration-300',
        isProfitable ? 'border-glow-emerald' : 'border-glow-red'
      )}
    >
      {/* Main content */}
      <div className="p-5">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            {/* Side indicator */}
            <div className={clsx(
              'w-10 h-10 rounded-xl flex items-center justify-center',
              isLong 
                ? 'bg-accent-emerald/20 text-accent-emerald' 
                : 'bg-accent-red/20 text-accent-red'
            )}>
              {isLong ? (
                <TrendingUp className="w-5 h-5" />
              ) : (
                <TrendingDown className="w-5 h-5" />
              )}
            </div>

            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-semibold text-text-primary">{position.symbol}</span>
                <span className={clsx(
                  'badge',
                  isLong ? 'badge-long' : 'badge-short'
                )}>
                  {position.side.toUpperCase()}
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs text-text-muted">
                <Clock className="w-3 h-3" />
                <span>{isValidDate ? `${hoursOpen}h ${minutesOpen}m` : 'Unknown'}</span>
              </div>
            </div>
          </div>

          {/* PnL */}
          <motion.div
            key={pnl}
            initial={{ scale: pnlFlash ? 1.1 : 1 }}
            animate={{ scale: 1 }}
            className="text-right"
          >
            <div className={clsx(
              'text-xl font-mono font-bold transition-colors',
              isProfitable ? 'text-accent-emerald' : 'text-accent-red',
              pnlFlash === 'up' && 'text-glow-emerald',
              pnlFlash === 'down' && 'text-glow-red'
            )}>
              {isProfitable ? '+' : ''}{pnl.toLocaleString('en-US', { 
                style: 'currency', 
                currency: 'USD',
                minimumFractionDigits: 2 
              })}
            </div>
            <div className={clsx(
              'text-xs font-mono',
              isProfitable ? 'text-accent-emerald/70' : 'text-accent-red/70'
            )}>
              {isProfitable ? '+' : ''}{pnlPercent.toFixed(2)}%
            </div>
          </motion.div>
        </div>

        {/* SL/TP Progress bar */}
        <div className="mb-4">
          <div className="flex justify-between text-[10px] text-text-muted mb-1">
            <span className="flex items-center gap-1">
              <ShieldAlert className="w-3 h-3 text-accent-red" />
              SL: ${position.stopLoss.toLocaleString()}
            </span>
            <span className="flex items-center gap-1">
              <Target className="w-3 h-3 text-accent-emerald" />
              TP: ${position.takeProfit.toLocaleString()}
            </span>
          </div>
          
          <div className="relative h-3 bg-void/50 rounded-full overflow-hidden">
            {/* Gradient background */}
            <div className="absolute inset-0 bg-gradient-to-r from-accent-red/30 via-accent-amber/20 to-accent-emerald/30" />
            
            {/* Entry marker */}
            <motion.div
              className="absolute top-0 bottom-0 w-0.5 bg-text-muted z-10"
              style={{ left: `${Math.max(0, Math.min(100, entryProgress))}%` }}
            />

            {/* Current price indicator */}
            <motion.div
              initial={{ left: `${entryProgress}%` }}
              animate={{ left: `${Math.max(0, Math.min(100, currentProgress))}%` }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 z-20"
            >
              <div className={clsx(
                'w-4 h-4 rounded-full border-2 border-white',
                isProfitable ? 'bg-accent-emerald shadow-glow-emerald' : 'bg-accent-red shadow-glow-red'
              )} />
            </motion.div>

            {/* Fill to current */}
            <motion.div
              initial={{ width: '0%' }}
              animate={{ width: `${Math.max(0, Math.min(100, currentProgress))}%` }}
              className={clsx(
                'absolute top-0 bottom-0 left-0',
                isProfitable ? 'bg-accent-emerald/20' : 'bg-accent-red/20'
              )}
            />
          </div>

          {/* Current price */}
          <div className="text-center mt-1">
            <span className="text-xs text-text-muted">Current: </span>
            <span className={clsx(
              'text-xs font-mono font-medium',
              isProfitable ? 'text-accent-emerald' : 'text-accent-red'
            )}>
              ${position.currentPrice.toLocaleString()}
            </span>
          </div>
        </div>

        {/* Key stats row */}
        <div className="grid grid-cols-4 gap-3">
          <div className="text-center">
            <span className="text-label block mb-1">Entry</span>
            <span className="text-sm font-mono text-text-primary">
              ${position.entryPrice.toLocaleString()}
            </span>
          </div>
          <div className="text-center">
            <span className="text-label block mb-1">Quantity</span>
            <span className="text-sm font-mono text-text-primary">
              {position.quantity.toFixed(4)}
            </span>
          </div>
          <div className="text-center">
            <span className="text-label block mb-1">Value</span>
            <span className="text-sm font-mono text-text-primary">
              ${positionValue.toLocaleString('en-US', { maximumFractionDigits: 0 })}
            </span>
          </div>
          <div className="text-center">
            <span className="text-label block mb-1">Risk</span>
            <span className="text-sm font-mono text-accent-amber">
              2.0%
            </span>
          </div>
        </div>
      </div>

      {/* Expandable details */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full py-2 border-t border-glass-border flex items-center justify-center gap-1 text-xs text-text-muted hover:text-text-secondary transition-colors"
      >
        {expanded ? (
          <>
            <ChevronUp className="w-4 h-4" />
            Hide Details
          </>
        ) : (
          <>
            <ChevronDown className="w-4 h-4" />
            Show Details
          </>
        )}
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="p-5 pt-0 space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-void/30 rounded-lg p-3">
                  <span className="text-label block mb-1">Fees Paid</span>
                  <span className="text-sm font-mono text-accent-amber">
                    ${(position.fee || 0).toFixed(4)}
                  </span>
                </div>
              </div>
              
              <div className="bg-void/30 rounded-lg p-3">
                <span className="text-label block mb-1">Position ID</span>
                <span className="text-xs font-mono text-text-muted break-all">
                  {position.id}
                </span>
              </div>
              
              <div className="bg-void/30 rounded-lg p-3">
                <span className="text-label block mb-1">Opened At</span>
                <span className="text-xs font-mono text-text-secondary">
                  {isValidDate ? openedDate.toLocaleString() : 'Unknown'}
                </span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// Positions container
interface PositionsListProps {
  positions: Position[]
  title?: string
}

export function PositionsList({ positions, title = 'Open Positions' }: PositionsListProps) {
  if (positions.length === 0) {
    return (
      <div className="glass-card p-8 text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-void/50 flex items-center justify-center">
          <Target className="w-8 h-8 text-text-dim" />
        </div>
        <p className="text-text-muted">No open positions</p>
        <p className="text-xs text-text-dim mt-1">Waiting for trading signals...</p>
      </div>
    )
  }

  const totalPnl = positions.reduce((sum, p) => sum + p.unrealizedPnl, 0)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-label">{title}</span>
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">{positions.length} position{positions.length !== 1 ? 's' : ''}</span>
          <span className={clsx(
            'text-sm font-mono font-semibold',
            totalPnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'
          )}>
            {totalPnl >= 0 ? '+' : ''}{totalPnl.toLocaleString('en-US', { 
              style: 'currency', 
              currency: 'USD',
              minimumFractionDigits: 2 
            })}
          </span>
        </div>
      </div>

      <div className="space-y-3">
        <AnimatePresence mode="popLayout">
          {positions.map((position) => (
            <PositionCard key={position.id} position={position} />
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}

