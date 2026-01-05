'use client'

import { useRef, useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { clsx } from 'clsx'
import {
  Activity,
  TrendingUp,
  TrendingDown,
  ShoppingCart,
  AlertTriangle,
  Shield,
  Radio,
  Wallet,
  Filter,
  Trash2,
  ChevronDown,
} from 'lucide-react'
import { useTradingStore, ActivityEntry, ActivityCategory } from '@/lib/websocket'

// ═══════════════════════════════════════════════════════════════════════════════
// CATEGORY CONFIG
// ═══════════════════════════════════════════════════════════════════════════════

const categoryConfig: Record<ActivityCategory, {
  icon: React.ComponentType<{ className?: string }>
  color: string
  bg: string
  border: string
  label: string
}> = {
  signal: {
    icon: TrendingUp,
    color: 'text-accent-cyan',
    bg: 'bg-accent-cyan/10',
    border: 'border-accent-cyan/30',
    label: 'Signal',
  },
  order: {
    icon: ShoppingCart,
    color: 'text-blue-400',
    bg: 'bg-blue-400/10',
    border: 'border-blue-400/30',
    label: 'Order',
  },
  position: {
    icon: TrendingDown,
    color: 'text-accent-emerald',
    bg: 'bg-accent-emerald/10',
    border: 'border-accent-emerald/30',
    label: 'Position',
  },
  risk: {
    icon: Shield,
    color: 'text-accent-red',
    bg: 'bg-accent-red/10',
    border: 'border-accent-red/30',
    label: 'Risiko',
  },
  portfolio: {
    icon: Wallet,
    color: 'text-purple-400',
    bg: 'bg-purple-400/10',
    border: 'border-purple-400/30',
    label: 'Portfolio',
  },
  system: {
    icon: Radio,
    color: 'text-text-muted',
    bg: 'bg-void/50',
    border: 'border-text-dim/30',
    label: 'System',
  },
}

// ═══════════════════════════════════════════════════════════════════════════════
// ACTIVITY ENTRY COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

interface ActivityItemProps {
  entry: ActivityEntry
  isNew?: boolean
}

function ActivityItem({ entry, isNew }: ActivityItemProps) {
  const config = categoryConfig[entry.category]
  const Icon = config.icon
  
  const time = new Date(entry.timestamp)
  const timeStr = time.toLocaleTimeString('de-DE', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
  
  return (
    <motion.div
      initial={isNew ? { opacity: 0, x: -20, height: 0 } : false}
      animate={{ opacity: 1, x: 0, height: 'auto' }}
      exit={{ opacity: 0, x: 20, height: 0 }}
      transition={{ duration: 0.2 }}
      className={clsx(
        'flex items-start gap-3 p-3 rounded-lg border transition-colors',
        config.bg,
        config.border,
        isNew && 'ring-1 ring-accent-cyan/50'
      )}
    >
      {/* Icon */}
      <div className={clsx('p-1.5 rounded-md flex-shrink-0', config.bg)}>
        <Icon className={clsx('w-3.5 h-3.5', config.color)} />
      </div>
      
      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className={clsx('text-xs font-semibold', config.color)}>
            {entry.title}
          </span>
          <span className="text-[10px] text-text-dim font-mono whitespace-nowrap">
            {timeStr}
          </span>
        </div>
        <p className="text-xs text-text-secondary mt-0.5 truncate">
          {entry.description}
        </p>
        {entry.coin && (
          <span className="inline-block mt-1 text-[10px] font-mono px-1.5 py-0.5 rounded bg-void/50 text-text-muted">
            {entry.coin}
          </span>
        )}
      </div>
    </motion.div>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// FILTER BUTTONS
// ═══════════════════════════════════════════════════════════════════════════════

interface FilterButtonProps {
  category: ActivityCategory | 'all'
  active: boolean
  count: number
  onClick: () => void
}

function FilterButton({ category, active, count, onClick }: FilterButtonProps) {
  const config = category === 'all' 
    ? { color: 'text-text-primary', bg: 'bg-surface-2', label: 'Alle' }
    : categoryConfig[category]
  
  return (
    <button
      onClick={onClick}
      className={clsx(
        'px-2 py-1 rounded-md text-xs font-medium transition-all flex items-center gap-1',
        active 
          ? `${config.bg} ${config.color} ring-1 ring-white/10`
          : 'text-text-muted hover:text-text-secondary hover:bg-void/50'
      )}
    >
      {config.label}
      {count > 0 && (
        <span className={clsx(
          'text-[10px] px-1 rounded',
          active ? 'bg-white/10' : 'bg-void/50'
        )}>
          {count}
        </span>
      )}
    </button>
  )
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

interface ActivityLogProps {
  maxHeight?: string
  showFilters?: boolean
  showClearButton?: boolean
}

export function ActivityLog({ 
  maxHeight = '400px',
  showFilters = true,
  showClearButton = true,
}: ActivityLogProps) {
  const { activityLog, clearActivityLog } = useTradingStore()
  const [filter, setFilter] = useState<ActivityCategory | 'all'>('all')
  const [autoScroll, setAutoScroll] = useState(true)
  const [newEntryIds, setNewEntryIds] = useState<Set<string>>(new Set())
  const scrollRef = useRef<HTMLDivElement>(null)
  const prevLengthRef = useRef(0)
  
  // Filter activities
  const filteredActivities = filter === 'all' 
    ? activityLog 
    : activityLog.filter(a => a.category === filter)
  
  // Count by category
  const counts = {
    all: activityLog.length,
    signal: activityLog.filter(a => a.category === 'signal').length,
    order: activityLog.filter(a => a.category === 'order').length,
    position: activityLog.filter(a => a.category === 'position').length,
    risk: activityLog.filter(a => a.category === 'risk').length,
    portfolio: activityLog.filter(a => a.category === 'portfolio').length,
    system: activityLog.filter(a => a.category === 'system').length,
  }
  
  // Track new entries for animation
  useEffect(() => {
    if (activityLog.length > prevLengthRef.current) {
      const newCount = activityLog.length - prevLengthRef.current
      const newIds = new Set(activityLog.slice(0, newCount).map(a => a.id))
      setNewEntryIds(newIds)
      
      // Clear "new" status after animation
      const timeout = setTimeout(() => {
        setNewEntryIds(new Set())
      }, 1000)
      
      return () => clearTimeout(timeout)
    }
    prevLengthRef.current = activityLog.length
  }, [activityLog.length])
  
  // Auto-scroll to top on new entries
  useEffect(() => {
    if (autoScroll && scrollRef.current && activityLog.length > 0) {
      scrollRef.current.scrollTop = 0
    }
  }, [activityLog.length, autoScroll])
  
  // Handle scroll - disable auto-scroll if user scrolls down
  const handleScroll = () => {
    if (scrollRef.current) {
      const { scrollTop } = scrollRef.current
      setAutoScroll(scrollTop < 50)
    }
  }
  
  return (
    <div className="glass-card p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-accent-cyan" />
          <span className="text-label">Activity Log</span>
          {activityLog.length > 0 && (
            <span className="text-xs text-text-dim font-mono">
              ({activityLog.length})
            </span>
          )}
        </div>
        
        <div className="flex items-center gap-2">
          {!autoScroll && activityLog.length > 0 && (
            <button
              onClick={() => {
                setAutoScroll(true)
                if (scrollRef.current) scrollRef.current.scrollTop = 0
              }}
              className="text-xs text-accent-cyan hover:underline"
            >
              Nach oben
            </button>
          )}
          {showClearButton && activityLog.length > 0 && (
            <button
              onClick={clearActivityLog}
              className="p-1.5 rounded-md hover:bg-void/50 text-text-muted hover:text-accent-red transition-colors"
              title="Log leeren"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
      
      {/* Filters */}
      {showFilters && activityLog.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-4">
          <FilterButton
            category="all"
            active={filter === 'all'}
            count={counts.all}
            onClick={() => setFilter('all')}
          />
          <FilterButton
            category="signal"
            active={filter === 'signal'}
            count={counts.signal}
            onClick={() => setFilter('signal')}
          />
          <FilterButton
            category="order"
            active={filter === 'order'}
            count={counts.order}
            onClick={() => setFilter('order')}
          />
          <FilterButton
            category="position"
            active={filter === 'position'}
            count={counts.position}
            onClick={() => setFilter('position')}
          />
          <FilterButton
            category="risk"
            active={filter === 'risk'}
            count={counts.risk}
            onClick={() => setFilter('risk')}
          />
        </div>
      )}
      
      {/* Activity List */}
      {filteredActivities.length > 0 ? (
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="space-y-2 overflow-y-auto pr-1 scrollbar-thin"
          style={{ maxHeight }}
        >
          <AnimatePresence mode="popLayout">
            {filteredActivities.map((entry) => (
              <ActivityItem
                key={entry.id}
                entry={entry}
                isNew={newEntryIds.has(entry.id)}
              />
            ))}
          </AnimatePresence>
        </div>
      ) : (
        <div className="text-center py-12">
          <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-void/50 flex items-center justify-center">
            <Activity className="w-7 h-7 text-text-dim" />
          </div>
          <p className="text-text-muted font-medium mb-1">No Activity</p>
          <p className="text-text-dim text-xs max-w-xs mx-auto">
            Bot activities will appear here in real-time as events occur.
          </p>
        </div>
      )}
      
      {/* Live indicator */}
      {activityLog.length > 0 && (
        <div className="mt-3 pt-3 border-t border-glass-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-accent-emerald animate-pulse" />
            <span className="text-[10px] text-text-dim">Live updates active</span>
          </div>
          <span className="text-[10px] text-text-dim font-mono">
            Max. 200 entries
          </span>
        </div>
      )}
    </div>
  )
}

