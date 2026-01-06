'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { 
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  Key,
  Database,
  Wifi,
  Server,
  Trash2,
  RotateCcw,
  Activity,
  Clock,
  Layers,
  TrendingUp,
  Settings,
} from 'lucide-react'
import { clsx } from 'clsx'

import { Sidebar } from '@/components/Sidebar'
import { MobileHeader } from '@/components/MobileHeader'
import { api } from '@/lib/api'
import { useWebSocket } from '@/lib/websocket'

interface SystemStatus {
  mode: string
  status: string
  timestamp: string
  websocket_connections: number
  event_streams: Record<string, any>
}

interface PortfolioManagerStatus {
  running: boolean
  phase: string
  cycle_count: number
  cycle_interval_seconds: number
  mode: string
  portfolio: {
    statistics: {
      starting_capital: number
      current_capital: number
      total_equity: number
      open_positions: number
      // Position count is determined dynamically by Grok AI
      deployment: {
        deployment_percent: number
        below_minimum: boolean
      }
    }
  }
  snapshot_service: {
    running: boolean
    snapshot_count: number
    interval_seconds: number
  }
  db_restored: boolean
}

export default function SettingsPage() {
  const [loading, setLoading] = useState(true)
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const [pmStatus, setPmStatus] = useState<PortfolioManagerStatus | null>(null)
  const [resetting, setResetting] = useState(false)
  const [resetSuccess, setResetSuccess] = useState(false)
  const [resetError, setResetError] = useState<string | null>(null)
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const { isConnected } = useWebSocket({ channel: 'all' })

  async function fetchStatus() {
    try {
      const [sysStatus, portfolioStatus] = await Promise.all([
        api.getSystemStatus().catch(() => null),
        api.getPortfolioManagerStatus().catch(() => null),
      ])
      setSystemStatus(sysStatus)
      setPmStatus(portfolioStatus as PortfolioManagerStatus | null)
    } catch (error) {
      console.error('Failed to fetch status:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 30000)
    return () => clearInterval(interval)
  }, [])

  const handleResetPaperTrades = async () => {
    setResetting(true)
    setResetError(null)
    setResetSuccess(false)
    
    try {
      const result = await api.resetPaperTrades()
      console.log('Reset result:', result)
      setResetSuccess(true)
      setShowResetConfirm(false)
      
      // Refresh status after reset
      await fetchStatus()
      
      // Clear success message after 5 seconds
      setTimeout(() => setResetSuccess(false), 5000)
    } catch (error) {
      console.error('Failed to reset paper trades:', error)
      setResetError(error instanceof Error ? error.message : 'Failed to reset trades')
    } finally {
      setResetting(false)
    }
  }

  const formatPhase = (phase: string) => {
    const phaseMap: Record<string, { label: string; color: string }> = {
      idle: { label: 'Idle', color: 'text-text-muted' },
      validating: { label: 'Validating Symbols', color: 'text-accent-amber' },
      updating_prices: { label: 'Updating Prices', color: 'text-accent-cyan' },
      analyzing: { label: 'AI Analysis', color: 'text-accent-purple' },
      trading: { label: 'Executing Trades', color: 'text-accent-emerald' },
      logging: { label: 'Logging', color: 'text-accent-cyan' },
      error: { label: 'Error', color: 'text-accent-red' },
    }
    return phaseMap[phase] || { label: phase, color: 'text-text-muted' }
  }

  const formatSeconds = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`
    const minutes = Math.floor(seconds / 60)
    const remaining = seconds % 60
    return remaining > 0 ? `${minutes}m ${remaining}s` : `${minutes}m`
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
          title="Settings"
        />

        <div className="p-4 md:p-6 lg:p-8">
        {/* Header */}
        <header className="mb-6">
          <motion.h1 
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="text-xl sm:text-2xl font-semibold text-text-primary tracking-tight"
          >
            System Configuration
          </motion.h1>
          <p className="text-xs text-text-muted mt-1">
            View system status and configuration. Settings are managed via environment variables.
          </p>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Portfolio Manager Status */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card p-6"
          >
            <div className="flex items-center gap-2 mb-6">
              <Activity className="w-5 h-5 text-accent-cyan" />
              <h2 className="text-lg font-semibold text-text-primary">Portfolio Manager</h2>
            </div>

            {loading ? (
              <div className="text-center py-8">
                <RefreshCw className="w-6 h-6 text-accent-cyan animate-spin mx-auto mb-2" />
                <p className="text-sm text-text-muted">Loading status...</p>
              </div>
            ) : pmStatus ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between p-3 rounded-lg bg-void/30">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-text-dim" />
                    <span className="text-sm text-text-secondary">Status</span>
                  </div>
                  <span className={clsx(
                    'px-2 py-0.5 rounded-full text-xs font-medium',
                    pmStatus.running 
                      ? 'bg-accent-emerald/20 text-accent-emerald' 
                      : 'bg-accent-red/20 text-accent-red'
                  )}>
                    {pmStatus.running ? 'Running' : 'Stopped'}
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-void/30">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-text-dim" />
                    <span className="text-sm text-text-secondary">Current Phase</span>
                  </div>
                  <span className={clsx('text-sm font-medium', formatPhase(pmStatus.phase).color)}>
                    {formatPhase(pmStatus.phase).label}
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-void/30">
                  <div className="flex items-center gap-2">
                    <RefreshCw className="w-4 h-4 text-text-dim" />
                    <span className="text-sm text-text-secondary">Cycles Completed</span>
                  </div>
                  <span className="text-sm font-mono text-text-primary">
                    {pmStatus.cycle_count}
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-void/30">
                  <div className="flex items-center gap-2">
                    <Layers className="w-4 h-4 text-text-dim" />
                    <span className="text-sm text-text-secondary">Open Positions</span>
                  </div>
                  <span className="text-sm font-mono text-text-primary">
                    {pmStatus.portfolio?.statistics?.open_positions || 0}
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-void/30">
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-text-dim" />
                    <span className="text-sm text-text-secondary">DB State Restored</span>
                  </div>
                  <span className={clsx(
                    'text-sm font-medium',
                    pmStatus.db_restored ? 'text-accent-emerald' : 'text-text-muted'
                  )}>
                    {pmStatus.db_restored ? 'Yes' : 'No'}
                  </span>
                </div>
              </div>
            ) : (
              <div className="text-center py-8">
                <AlertTriangle className="w-6 h-6 text-accent-amber mx-auto mb-2" />
                <p className="text-sm text-text-muted">Portfolio Manager not available</p>
              </div>
            )}
          </motion.div>

          {/* Current Configuration */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card p-6"
          >
            <div className="flex items-center gap-2 mb-6">
              <Settings className="w-5 h-5 text-accent-amber" />
              <h2 className="text-lg font-semibold text-text-primary">Current Configuration</h2>
            </div>

            {loading ? (
              <div className="text-center py-8">
                <RefreshCw className="w-6 h-6 text-accent-cyan animate-spin mx-auto mb-2" />
                <p className="text-sm text-text-muted">Loading configuration...</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between p-3 rounded-lg bg-void/30">
                  <div className="flex items-center gap-2">
                    <Server className="w-4 h-4 text-text-dim" />
                    <span className="text-sm text-text-secondary">Mode</span>
                  </div>
                  <span className="badge badge-paper">
                    {pmStatus?.mode?.toUpperCase() || systemStatus?.mode?.toUpperCase() || 'PAPER'}
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-void/30">
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4 text-text-dim" />
                    <span className="text-sm text-text-secondary">Cycle Interval</span>
                  </div>
                  <span className="text-sm font-mono text-text-primary">
                    {formatSeconds(pmStatus?.cycle_interval_seconds || 600)}
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-void/30">
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-text-dim" />
                    <span className="text-sm text-text-secondary">Deployment</span>
                  </div>
                  <span className={clsx(
                    'text-sm font-mono',
                    pmStatus?.portfolio?.statistics?.deployment?.below_minimum 
                      ? 'text-accent-amber' 
                      : 'text-text-primary'
                  )}>
                    {(pmStatus?.portfolio?.statistics?.deployment?.deployment_percent || 0).toFixed(1)}%
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-void/30">
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-text-dim" />
                    <span className="text-sm text-text-secondary">Starting Capital</span>
                  </div>
                  <span className="text-sm font-mono text-text-primary">
                    ${(pmStatus?.portfolio?.statistics?.starting_capital || 0).toLocaleString()}
                  </span>
                </div>

                <div className="p-4 rounded-lg bg-accent-amber/10 border border-accent-amber/30">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-accent-amber flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm text-accent-amber font-medium">Configuration Note</p>
                      <p className="text-xs text-text-muted mt-1">
                        Configuration is managed via environment variables. 
                        Modify the .env file and restart the system to change settings.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </motion.div>

          {/* System Status */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card p-6"
          >
            <div className="flex items-center gap-2 mb-6">
              <Wifi className="w-5 h-5 text-accent-cyan" />
              <h2 className="text-lg font-semibold text-text-primary">System Status</h2>
            </div>

            {loading ? (
              <div className="text-center py-8">
                <RefreshCw className="w-6 h-6 text-accent-cyan animate-spin mx-auto mb-2" />
                <p className="text-sm text-text-muted">Loading status...</p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between p-3 rounded-lg bg-void/30">
                  <div className="flex items-center gap-2">
                    <Wifi className="w-4 h-4 text-text-dim" />
                    <span className="text-sm text-text-secondary">WebSocket</span>
                  </div>
                  <span className={clsx(
                    'text-sm font-medium',
                    isConnected ? 'text-accent-emerald' : 'text-accent-red'
                  )}>
                    {isConnected ? 'Connected' : 'Disconnected'}
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-void/30">
                  <div className="flex items-center gap-2">
                    <Database className="w-4 h-4 text-text-dim" />
                    <span className="text-sm text-text-secondary">Database</span>
                  </div>
                  <span className="text-sm font-medium text-accent-emerald">
                    {systemStatus?.status === 'running' ? 'Connected' : 'Connected'}
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-void/30">
                  <div className="flex items-center gap-2">
                    <Key className="w-4 h-4 text-text-dim" />
                    <span className="text-sm text-text-secondary">xAI API</span>
                  </div>
                  <span className="text-sm font-medium text-accent-emerald">Configured</span>
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-void/30">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-text-dim" />
                    <span className="text-sm text-text-secondary">Snapshot Service</span>
                  </div>
                  <span className={clsx(
                    'text-sm font-medium',
                    pmStatus?.snapshot_service?.running ? 'text-accent-emerald' : 'text-text-muted'
                  )}>
                    {pmStatus?.snapshot_service?.running ? 'Running' : 'Stopped'}
                  </span>
                </div>

                <div className="mt-4 p-4 rounded-lg bg-accent-emerald/10 border border-accent-emerald/30">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-accent-emerald" />
                    <span className="text-sm text-accent-emerald font-medium">
                      All Systems Operational
                    </span>
                  </div>
                  {systemStatus?.timestamp && (
                    <p className="text-xs text-text-muted mt-1">
                      Last checked: {new Date(systemStatus.timestamp).toLocaleString()}
                    </p>
                  )}
                </div>
              </div>
            )}
          </motion.div>

          {/* API Keys Info */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="glass-card p-6"
          >
            <div className="flex items-center gap-2 mb-6">
              <Key className="w-5 h-5 text-accent-cyan" />
              <h2 className="text-lg font-semibold text-text-primary">API Keys</h2>
            </div>

            <div className="space-y-4">
              <div className="p-4 rounded-lg bg-void/30 border border-glass-border">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-text-primary">xAI API Key</span>
                  <span className="px-2 py-0.5 rounded-full text-xs bg-accent-emerald/20 text-accent-emerald">
                    Configured
                  </span>
                </div>
                <p className="text-xs text-text-muted">
                  Used for Grok sentiment analysis. Set via XAI_API_KEY in .env
                </p>
              </div>

              <div className="p-4 rounded-lg bg-void/30 border border-glass-border">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-text-primary">CapTrader/IBKR API</span>
                  <span className="px-2 py-0.5 rounded-full text-xs bg-accent-amber/20 text-accent-amber">
                    Future Feature
                  </span>
                </div>
                <p className="text-xs text-text-muted">
                  For live stock trading. Paper mode uses Yahoo Finance for prices.
                </p>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Danger Zone */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="glass-card p-6 mt-6 border-accent-red/30"
        >
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="w-5 h-5 text-accent-red" />
            <h2 className="text-lg font-semibold text-accent-red">Danger Zone</h2>
          </div>

          <div className="p-4 rounded-lg bg-accent-red/5 border border-accent-red/20">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                  <RotateCcw className="w-4 h-4 text-accent-red" />
                  Reset Paper Trading
                </h3>
                <p className="text-xs text-text-muted mt-1">
                  Delete all paper trades, positions, and trading history. 
                  The system will restart with initial capital of $1,000,000 USD.
                  This action cannot be undone.
                </p>
                
                {/* Success Message */}
                {resetSuccess && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-3 p-2 rounded-lg bg-accent-emerald/10 border border-accent-emerald/30"
                  >
                    <div className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-accent-emerald" />
                      <span className="text-sm text-accent-emerald font-medium">
                        Paper trades reset successfully! Starting fresh with $100,000.
                      </span>
                    </div>
                  </motion.div>
                )}
                
                {/* Error Message */}
                {resetError && (
                  <motion.div
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="mt-3 p-2 rounded-lg bg-accent-red/10 border border-accent-red/30"
                  >
                    <div className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-accent-red" />
                      <span className="text-sm text-accent-red">{resetError}</span>
                    </div>
                  </motion.div>
                )}
              </div>
              
              <div className="flex-shrink-0">
                {!showResetConfirm ? (
                  <button
                    onClick={() => setShowResetConfirm(true)}
                    disabled={resetting}
                    className={clsx(
                      'flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all',
                      'bg-accent-red/10 text-accent-red border border-accent-red/30',
                      'hover:bg-accent-red/20',
                      resetting && 'opacity-50 cursor-not-allowed'
                    )}
                  >
                    <Trash2 className="w-4 h-4" />
                    Reset All Trades
                  </button>
                ) : (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setShowResetConfirm(false)}
                      disabled={resetting}
                      className="px-3 py-2 rounded-lg text-sm font-medium text-text-muted hover:text-text-secondary transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleResetPaperTrades}
                      disabled={resetting}
                      className={clsx(
                        'flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-all',
                        'bg-accent-red text-white',
                        'hover:bg-accent-red/80',
                        resetting && 'opacity-50 cursor-not-allowed'
                      )}
                    >
                      {resetting ? (
                        <>
                          <RefreshCw className="w-4 h-4 animate-spin" />
                          Resetting...
                        </>
                      ) : (
                        <>
                          <AlertTriangle className="w-4 h-4" />
                          Confirm Reset
                        </>
                      )}
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </motion.div>
        </div>
      </main>
    </div>
  )
}
