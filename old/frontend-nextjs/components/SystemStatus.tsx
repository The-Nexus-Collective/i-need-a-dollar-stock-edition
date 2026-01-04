'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  ChevronDown,
  ChevronUp,
  Database,
  Radio,
  Zap,
  Bot,
  Clock,
} from 'lucide-react'
import { clsx } from 'clsx'

// ═══════════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════════

export interface ServiceStatus {
  name: string
  status: 'healthy' | 'unhealthy' | 'unknown'
  error?: string
  latency_ms?: number
  last_check?: string
}

export interface LogEntry {
  timestamp: string
  level: 'ERROR' | 'WARNING'
  logger: string
  service: string
  message: string
  module: string
  line: number
}

export interface HealthData {
  overall: 'healthy' | 'degraded' | 'unhealthy'
  services: Record<string, ServiceStatus>
  error_count: number
  warning_count: number
  recent_errors: LogEntry[]
  last_check: string
}

interface SystemStatusProps {
  health: HealthData | null
  isLoading?: boolean
}

// ═══════════════════════════════════════════════════════════════════════════════
// SERVICE ICONS
// ═══════════════════════════════════════════════════════════════════════════════

const serviceIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  database: Database,
  redis: Radio,
  binance: Zap,
  grok: Bot,
}

// ═══════════════════════════════════════════════════════════════════════════════
// STATUS CONFIG
// ═══════════════════════════════════════════════════════════════════════════════

const overallConfig = {
  healthy: {
    label: 'All Systems Operational',
    color: 'text-accent-emerald',
    bg: 'bg-accent-emerald/10',
    border: 'border-accent-emerald/20',
    Icon: CheckCircle,
    dotClass: 'bg-accent-emerald animate-pulse',
  },
  degraded: {
    label: 'System Degraded',
    color: 'text-accent-amber',
    bg: 'bg-accent-amber/10',
    border: 'border-accent-amber/20',
    Icon: AlertTriangle,
    dotClass: 'bg-accent-amber',
  },
  unhealthy: {
    label: 'System Issues Detected',
    color: 'text-accent-red',
    bg: 'bg-accent-red/10',
    border: 'border-accent-red/20',
    Icon: XCircle,
    dotClass: 'bg-accent-red animate-pulse',
  },
}

const serviceStatusConfig = {
  healthy: {
    color: 'text-accent-emerald',
    bg: 'bg-accent-emerald/10',
    label: 'OK',
  },
  unhealthy: {
    color: 'text-accent-red',
    bg: 'bg-accent-red/10',
    label: 'Error',
  },
  unknown: {
    color: 'text-accent-amber',
    bg: 'bg-accent-amber/10',
    label: 'Unknown',
  },
}

// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export function SystemStatus({ health, isLoading }: SystemStatusProps) {
  const [expanded, setExpanded] = useState(false)

  // Default to healthy if no data
  const overall = health?.overall ?? 'healthy'
  const config = overallConfig[overall]
  const Icon = config.Icon

  const hasErrors = (health?.error_count ?? 0) > 0 || (health?.warning_count ?? 0) > 0
  const services = health?.services ?? {}
  const recentErrors = health?.recent_errors ?? []

  // Format timestamp for display
  const formatTime = (timestamp: string) => {
    try {
      const date = new Date(timestamp)
      return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false,
      })
    } catch {
      return timestamp
    }
  }

  return (
    <div className="glass-card p-5">
      {/* Header - Always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between group"
      >
        <div className="flex items-center gap-3">
          <div className={clsx('p-2 rounded-lg', config.bg, config.border, 'border')}>
            <Icon className={clsx('w-4 h-4', config.color)} />
          </div>
          <div className="text-left">
            <div className="flex items-center gap-2">
              <div className={clsx('w-2 h-2 rounded-full', config.dotClass)} />
              <span className={clsx('text-sm font-medium', config.color)}>
                {isLoading ? 'Checking...' : config.label}
              </span>
            </div>
            {hasErrors && !isLoading && (
              <div className="flex items-center gap-2 mt-1">
                {(health?.error_count ?? 0) > 0 && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-accent-red/10 text-accent-red">
                    {health?.error_count} errors
                  </span>
                )}
                {(health?.warning_count ?? 0) > 0 && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-accent-amber/10 text-accent-amber">
                    {health?.warning_count} warnings
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {health?.last_check && (
            <span className="text-xs text-text-dim flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {formatTime(health.last_check)}
            </span>
          )}
          {expanded ? (
            <ChevronUp className="w-4 h-4 text-text-muted group-hover:text-text-secondary transition-colors" />
          ) : (
            <ChevronDown className="w-4 h-4 text-text-muted group-hover:text-text-secondary transition-colors" />
          )}
        </div>
      </button>

      {/* Expanded Content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="mt-4 space-y-4">
              {/* Service Status Grid */}
              <div>
                <span className="text-xs text-text-dim block mb-2">Services</span>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(services).map(([key, service]) => {
                    const statusConfig = serviceStatusConfig[service.status]
                    const ServiceIcon = serviceIcons[key] ?? Database

                    return (
                      <div
                        key={key}
                        className={clsx(
                          'p-2 rounded-lg border flex items-center gap-2',
                          statusConfig.bg,
                          'border-white/5'
                        )}
                      >
                        <ServiceIcon className={clsx('w-4 h-4', statusConfig.color)} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-text-primary capitalize">
                              {key}
                            </span>
                            <span className={clsx('text-xs', statusConfig.color)}>
                              {statusConfig.label}
                            </span>
                          </div>
                          {service.latency_ms !== undefined && service.status === 'healthy' && (
                            <span className="text-xs text-text-dim">
                              {service.latency_ms}ms
                            </span>
                          )}
                          {service.error && (
                            <span className="text-xs text-accent-red truncate block">
                              {service.error}
                            </span>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Recent Errors */}
              {recentErrors.length > 0 && (
                <div>
                  <span className="text-xs text-text-dim block mb-2">Recent Logs</span>
                  <div className="max-h-48 overflow-y-auto space-y-1 rounded-lg bg-void/30 p-2">
                    {recentErrors.map((entry, idx) => (
                      <div
                        key={idx}
                        className={clsx(
                          'text-xs font-mono py-1 px-2 rounded',
                          entry.level === 'ERROR' 
                            ? 'bg-accent-red/5 border-l-2 border-accent-red' 
                            : 'bg-accent-amber/5 border-l-2 border-accent-amber'
                        )}
                      >
                        <div className="flex items-start gap-2">
                          <span className="text-text-dim whitespace-nowrap">
                            [{formatTime(entry.timestamp)}]
                          </span>
                          <span
                            className={clsx(
                              'font-semibold',
                              entry.level === 'ERROR' ? 'text-accent-red' : 'text-accent-amber'
                            )}
                          >
                            {entry.level}
                          </span>
                          <span className="text-text-muted">{entry.service}:</span>
                          <span className="text-text-secondary flex-1 break-words">
                            {entry.message}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Empty state */}
              {recentErrors.length === 0 && overall === 'healthy' && (
                <div className="text-center py-2 text-xs text-text-muted">
                  No recent errors or warnings
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

