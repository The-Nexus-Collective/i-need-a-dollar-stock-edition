'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { 
  Settings, 
  Save,
  RefreshCw,
  Shield,
  Zap,
  Clock,
  DollarSign,
  Percent,
  AlertTriangle,
  CheckCircle,
  Key,
  Database,
  Wifi,
  Server,
  Trash2,
  RotateCcw,
} from 'lucide-react'
import { clsx } from 'clsx'

import { Sidebar } from '@/components/Sidebar'
import { api } from '@/lib/api'
import { useWebSocket } from '@/lib/websocket'

interface SystemStatus {
  mode: string
  status: string
  timestamp: string
  websocket_connections: number
  event_streams: Record<string, any>
}

export default function SettingsPage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const [resetting, setResetting] = useState(false)
  const [resetSuccess, setResetSuccess] = useState(false)
  const [resetError, setResetError] = useState<string | null>(null)
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const [accountData, setAccountData] = useState({
    balance: 108000,
    initialBalance: 108000,
    totalFees: 0,
    slippageCost: 0,
    totalTrades: 0,
    winningTrades: 0,
    mode: 'paper' as const,
  })

  // Settings state (these would be saved to backend in a real implementation)
  const [settings, setSettings] = useState({
    // Trading Parameters
    riskPerTrade: 2.0,
    scoreThreshold: 65,
    volumeFilterRatio: 80,
    stopLossAtrMult: 1.5,
    takeProfitAtrMult: 4.0,
    flattenTime: '23:55',
    
    // Risk Limits
    maxPositionSize: 10,
    maxDrawdown: 15,
    dailyLossLimit: 5,
    maxOpenPositions: 3,
    
    // API Configuration
    grokMaxRetries: 3,
    tradingInterval: 60, // minutes
    
    // Notifications
    enableDiscord: false,
    enableEmail: false,
    discordWebhook: '',
    emailAddress: '',
  })

  const { isConnected } = useWebSocket({ channel: 'all' })

  async function fetchSystemStatus() {
    try {
      const status = await api.getSystemStatus().catch(() => null)
      setSystemStatus(status)
    } catch (error) {
      console.error('Failed to fetch system status:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchSystemStatus()
    const interval = setInterval(fetchSystemStatus, 30000)
    return () => clearInterval(interval)
  }, [])

  const handleSave = async () => {
    setSaving(true)
    // In a real implementation, this would save to the backend
    await new Promise(resolve => setTimeout(resolve, 1000))
    setSaving(false)
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  const handleChange = (key: keyof typeof settings, value: any) => {
    setSettings(prev => ({ ...prev, [key]: value }))
  }

  const handleResetPaperTrades = async () => {
    setResetting(true)
    setResetError(null)
    setResetSuccess(false)
    
    try {
      const result = await api.resetPaperTrades()
      console.log('Reset result:', result)
      setResetSuccess(true)
      setShowResetConfirm(false)
      
      // Clear success message after 5 seconds
      setTimeout(() => setResetSuccess(false), 5000)
    } catch (error) {
      console.error('Failed to reset paper trades:', error)
      setResetError(error instanceof Error ? error.message : 'Failed to reset trades')
    } finally {
      setResetting(false)
    }
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
              className="text-2xl font-semibold text-text-primary tracking-tight"
            >
              Settings
            </motion.h1>
            <p className="text-xs text-text-muted mt-1">
              Configure trading parameters and system settings
            </p>
          </div>

          <div className="flex items-center gap-3">
            {saved && (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-accent-emerald/10 text-accent-emerald text-sm"
              >
                <CheckCircle className="w-4 h-4" />
                Saved
              </motion.div>
            )}
            <button
              onClick={handleSave}
              disabled={saving}
              className={clsx(
                'flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all',
                'bg-accent-cyan/20 text-accent-cyan border border-accent-cyan/30',
                'hover:bg-accent-cyan/30',
                saving && 'opacity-50 cursor-not-allowed'
              )}
            >
              {saving ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              Save Changes
            </button>
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Trading Parameters */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass-card p-6"
          >
            <div className="flex items-center gap-2 mb-6">
              <Zap className="w-5 h-5 text-accent-cyan" />
              <h2 className="text-lg font-semibold text-text-primary">Trading Parameters</h2>
            </div>

            <div className="space-y-5">
              <div>
                <label className="flex items-center justify-between mb-2">
                  <span className="text-sm text-text-secondary">Risk Per Trade</span>
                  <span className="text-xs font-mono text-accent-cyan">{settings.riskPerTrade}%</span>
                </label>
                <input
                  type="range"
                  min="0.5"
                  max="5"
                  step="0.5"
                  value={settings.riskPerTrade}
                  onChange={(e) => handleChange('riskPerTrade', parseFloat(e.target.value))}
                  className="w-full h-2 bg-void rounded-lg appearance-none cursor-pointer accent-accent-cyan"
                />
                <div className="flex justify-between text-xs text-text-dim mt-1">
                  <span>0.5%</span>
                  <span>5%</span>
                </div>
              </div>

              <div>
                <label className="flex items-center justify-between mb-2">
                  <span className="text-sm text-text-secondary">Score Threshold</span>
                  <span className="text-xs font-mono text-accent-cyan">{settings.scoreThreshold}</span>
                </label>
                <input
                  type="range"
                  min="30"
                  max="90"
                  step="5"
                  value={settings.scoreThreshold}
                  onChange={(e) => handleChange('scoreThreshold', parseInt(e.target.value))}
                  className="w-full h-2 bg-void rounded-lg appearance-none cursor-pointer accent-accent-cyan"
                />
                <div className="flex justify-between text-xs text-text-dim mt-1">
                  <span>30 (aggressive)</span>
                  <span>90 (conservative)</span>
                </div>
              </div>

              <div>
                <label className="flex items-center justify-between mb-2">
                  <span className="text-sm text-text-secondary">Volume Filter Ratio</span>
                  <span className="text-xs font-mono text-accent-cyan">{settings.volumeFilterRatio}%</span>
                </label>
                <input
                  type="range"
                  min="50"
                  max="100"
                  step="5"
                  value={settings.volumeFilterRatio}
                  onChange={(e) => handleChange('volumeFilterRatio', parseInt(e.target.value))}
                  className="w-full h-2 bg-void rounded-lg appearance-none cursor-pointer accent-accent-cyan"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-text-secondary block mb-2">Stop Loss (ATR ×)</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0.5"
                    max="5"
                    value={settings.stopLossAtrMult}
                    onChange={(e) => handleChange('stopLossAtrMult', parseFloat(e.target.value))}
                    className="w-full px-3 py-2 bg-void/50 border border-glass-border rounded-lg text-sm font-mono text-text-primary focus:outline-none focus:border-accent-cyan/50"
                  />
                </div>
                <div>
                  <label className="text-sm text-text-secondary block mb-2">Take Profit (ATR ×)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="1"
                    max="10"
                    value={settings.takeProfitAtrMult}
                    onChange={(e) => handleChange('takeProfitAtrMult', parseFloat(e.target.value))}
                    className="w-full px-3 py-2 bg-void/50 border border-glass-border rounded-lg text-sm font-mono text-text-primary focus:outline-none focus:border-accent-cyan/50"
                  />
                </div>
              </div>

              <div>
                <label className="text-sm text-text-secondary block mb-2">
                  <Clock className="w-4 h-4 inline mr-1" />
                  Daily Flatten Time (CET)
                </label>
                <input
                  type="time"
                  value={settings.flattenTime}
                  onChange={(e) => handleChange('flattenTime', e.target.value)}
                  className="w-full px-3 py-2 bg-void/50 border border-glass-border rounded-lg text-sm font-mono text-text-primary focus:outline-none focus:border-accent-cyan/50"
                />
              </div>
            </div>
          </motion.div>

          {/* Risk Limits */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="glass-card p-6"
          >
            <div className="flex items-center gap-2 mb-6">
              <Shield className="w-5 h-5 text-accent-emerald" />
              <h2 className="text-lg font-semibold text-text-primary">Risk Limits</h2>
            </div>

            <div className="space-y-5">
              <div>
                <label className="flex items-center justify-between mb-2">
                  <span className="text-sm text-text-secondary">Max Position Size</span>
                  <span className="text-xs font-mono text-accent-emerald">{settings.maxPositionSize}%</span>
                </label>
                <input
                  type="range"
                  min="5"
                  max="25"
                  step="1"
                  value={settings.maxPositionSize}
                  onChange={(e) => handleChange('maxPositionSize', parseInt(e.target.value))}
                  className="w-full h-2 bg-void rounded-lg appearance-none cursor-pointer accent-accent-emerald"
                />
              </div>

              <div>
                <label className="flex items-center justify-between mb-2">
                  <span className="text-sm text-text-secondary">Max Drawdown Limit</span>
                  <span className="text-xs font-mono text-accent-red">{settings.maxDrawdown}%</span>
                </label>
                <input
                  type="range"
                  min="5"
                  max="30"
                  step="1"
                  value={settings.maxDrawdown}
                  onChange={(e) => handleChange('maxDrawdown', parseInt(e.target.value))}
                  className="w-full h-2 bg-void rounded-lg appearance-none cursor-pointer accent-accent-red"
                />
                <p className="text-xs text-text-dim mt-1">Trading stops if drawdown exceeds this limit</p>
              </div>

              <div>
                <label className="flex items-center justify-between mb-2">
                  <span className="text-sm text-text-secondary">Daily Loss Limit</span>
                  <span className="text-xs font-mono text-accent-amber">{settings.dailyLossLimit}%</span>
                </label>
                <input
                  type="range"
                  min="1"
                  max="10"
                  step="0.5"
                  value={settings.dailyLossLimit}
                  onChange={(e) => handleChange('dailyLossLimit', parseFloat(e.target.value))}
                  className="w-full h-2 bg-void rounded-lg appearance-none cursor-pointer accent-accent-amber"
                />
              </div>

              <div>
                <label className="text-sm text-text-secondary block mb-2">Max Open Positions</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={settings.maxOpenPositions}
                  onChange={(e) => handleChange('maxOpenPositions', parseInt(e.target.value))}
                  className="w-full px-3 py-2 bg-void/50 border border-glass-border rounded-lg text-sm font-mono text-text-primary focus:outline-none focus:border-accent-cyan/50"
                />
              </div>
            </div>
          </motion.div>

          {/* System Configuration */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card p-6"
          >
            <div className="flex items-center gap-2 mb-6">
              <Server className="w-5 h-5 text-accent-amber" />
              <h2 className="text-lg font-semibold text-text-primary">System Configuration</h2>
            </div>

            <div className="space-y-5">
              <div>
                <label className="text-sm text-text-secondary block mb-2">Grok API Max Retries</label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={settings.grokMaxRetries}
                  onChange={(e) => handleChange('grokMaxRetries', parseInt(e.target.value))}
                  className="w-full px-3 py-2 bg-void/50 border border-glass-border rounded-lg text-sm font-mono text-text-primary focus:outline-none focus:border-accent-cyan/50"
                />
              </div>

              <div>
                <label className="text-sm text-text-secondary block mb-2">Trading Interval (minutes)</label>
                <select
                  value={settings.tradingInterval}
                  onChange={(e) => handleChange('tradingInterval', parseInt(e.target.value))}
                  className="w-full px-3 py-2 bg-void/50 border border-glass-border rounded-lg text-sm text-text-primary focus:outline-none focus:border-accent-cyan/50"
                >
                  <option value={15}>15 minutes</option>
                  <option value={30}>30 minutes</option>
                  <option value={60}>1 hour</option>
                  <option value={240}>4 hours</option>
                </select>
              </div>

              <div className="p-4 rounded-lg bg-accent-amber/10 border border-accent-amber/30">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-accent-amber flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm text-accent-amber font-medium">Configuration Note</p>
                    <p className="text-xs text-text-muted mt-1">
                      Changes to system configuration require a bot restart to take effect. 
                      Modify the .env file and rebuild the container for production changes.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>

          {/* System Status */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
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
                    <Server className="w-4 h-4 text-text-dim" />
                    <span className="text-sm text-text-secondary">Mode</span>
                  </div>
                  <span className="badge badge-paper">
                    {systemStatus?.mode?.toUpperCase() || 'PAPER'}
                  </span>
                </div>

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
                    {systemStatus?.status === 'healthy' ? 'Connected' : 'Unknown'}
                  </span>
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-void/30">
                  <div className="flex items-center gap-2">
                    <Key className="w-4 h-4 text-text-dim" />
                    <span className="text-sm text-text-secondary">xAI API</span>
                  </div>
                  <span className="text-sm font-medium text-accent-emerald">Configured</span>
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
        </div>

        {/* API Keys Info */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="glass-card p-6 mt-6"
        >
          <div className="flex items-center gap-2 mb-4">
            <Key className="w-5 h-5 text-accent-cyan" />
            <h2 className="text-lg font-semibold text-text-primary">API Keys</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                <span className="text-sm font-medium text-text-primary">Binance API Key</span>
                <span className="px-2 py-0.5 rounded-full text-xs bg-accent-amber/20 text-accent-amber">
                  Optional (Live Mode)
                </span>
              </div>
              <p className="text-xs text-text-muted">
                Only required for live trading. Paper mode uses public API.
              </p>
            </div>
          </div>
        </motion.div>

        {/* Danger Zone */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.5 }}
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
                  The system will restart with initial capital of $100,000 USDT.
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
      </main>
    </div>
  )
}

