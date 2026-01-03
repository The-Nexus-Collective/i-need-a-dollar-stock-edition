'use client'

import { useState } from 'react'
import { usePathname } from 'next/navigation'
import Link from 'next/link'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard,
  TrendingUp,
  History,
  Shield,
  Settings,
  ChevronLeft,
  ChevronRight,
  Wallet,
  Activity,
  Zap,
  BarChart3,
} from 'lucide-react'
import { clsx } from 'clsx'

interface AccountData {
  balance: number
  initialBalance: number
  totalFees: number
  slippageCost: number
  totalTrades: number
  winningTrades: number
  mode: 'paper' | 'live'
}

interface SidebarProps {
  accountData: AccountData
  isConnected: boolean
}

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', href: '/' },
  { icon: BarChart3, label: 'Stocks', href: '/stocks' },
  { icon: TrendingUp, label: 'Positions', href: '/positions' },
  { icon: History, label: 'History', href: '/history' },
  { icon: Shield, label: 'Risk', href: '/risk' },
  { icon: Settings, label: 'Settings', href: '/settings' },
]

export function Sidebar({ accountData, isConnected }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false)
  const pathname = usePathname()

  const pnl = accountData.balance - accountData.initialBalance
  const pnlPercent = (pnl / accountData.initialBalance) * 100
  const winRate = accountData.totalTrades > 0 
    ? (accountData.winningTrades / accountData.totalTrades) * 100 
    : 0

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 72 : 280 }}
      transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
      className="fixed left-0 top-0 h-screen glass-sidebar z-50 flex flex-col"
    >
      {/* Logo */}
      <div className="p-5 flex items-center justify-between border-b border-glass-border">
        <motion.div
          initial={false}
          animate={{ opacity: collapsed ? 0 : 1, width: collapsed ? 0 : 'auto' }}
          className="flex items-center gap-3 overflow-hidden"
        >
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent-cyan to-accent-emerald flex items-center justify-center shadow-glow-cyan">
            <Zap className="w-5 h-5 text-void" />
          </div>
          <div>
            <h1 className="font-semibold text-text-primary tracking-tight text-sm">I Need A Dollar</h1>
            <p className="text-[10px] text-text-muted uppercase tracking-widest">AI Trading Terminal</p>
          </div>
        </motion.div>
        
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-2 rounded-lg hover:bg-glass-bg transition-colors text-text-muted hover:text-accent-cyan"
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Status */}
      <div className="px-5 py-4 border-b border-glass-border">
        <div className="flex items-center gap-2">
          <div className={clsx('status-dot', isConnected ? 'live' : 'offline')} />
          <AnimatePresence mode="wait">
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                className={clsx(
                  'text-xs font-medium uppercase tracking-wider',
                  accountData.mode === 'paper' ? 'text-accent-amber' : 'text-accent-emerald'
                )}
              >
                {accountData.mode === 'paper' ? 'Paper Mode' : 'Live Trading'}
              </motion.span>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-3">
        <ul className="space-y-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href
            const Icon = item.icon
            
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  className={clsx(
                    'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-200',
                    isActive
                      ? 'bg-accent-cyan/10 text-accent-cyan border-glow-cyan'
                      : 'text-text-secondary hover:text-text-primary hover:bg-glass-bg'
                  )}
                >
                  <Icon className={clsx('w-5 h-5 flex-shrink-0', isActive && 'drop-shadow-[0_0_8px_rgba(0,212,255,0.5)]')} />
                  <AnimatePresence mode="wait">
                    {!collapsed && (
                      <motion.span
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -10 }}
                        className="text-sm font-medium"
                      >
                        {item.label}
                      </motion.span>
                    )}
                  </AnimatePresence>
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>

      {/* Account Summary */}
      <AnimatePresence mode="wait">
        {!collapsed && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="p-4 border-t border-glass-border"
          >
            {/* Equity */}
            <div className="glass-card p-4 mb-3">
              <div className="flex items-center gap-2 mb-2">
                <Wallet className="w-4 h-4 text-accent-cyan" />
                <span className="text-label">Portfolio Value</span>
              </div>
              <p className="text-xl font-mono font-semibold text-text-primary">
                ${accountData.balance.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </p>
              <p className={clsx(
                'text-xs font-mono mt-1',
                pnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'
              )}>
                {pnl >= 0 ? '+' : ''}{pnl.toLocaleString('en-US', { minimumFractionDigits: 2 })} ({pnlPercent.toFixed(2)}%)
              </p>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 gap-2">
              <div className="glass-card p-3">
                <span className="text-label block mb-1">Win Rate</span>
                <p className="text-sm font-mono font-semibold text-text-primary">
                  {winRate.toFixed(1)}%
                </p>
              </div>
              <div className="glass-card p-3">
                <span className="text-label block mb-1">Trades</span>
                <p className="text-sm font-mono font-semibold text-text-primary">
                  {accountData.totalTrades}
                </p>
              </div>
              <div className="glass-card p-3">
                <span className="text-label block mb-1">Fees</span>
                <p className="text-sm font-mono font-semibold text-accent-amber">
                  ${accountData.totalFees.toFixed(2)}
                </p>
              </div>
              <div className="glass-card p-3">
                <span className="text-label block mb-1">Slippage</span>
                <p className="text-sm font-mono font-semibold text-accent-amber">
                  ${accountData.slippageCost.toFixed(2)}
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Connection indicator - always visible */}
      <div className="p-4 border-t border-glass-border">
        <div className="flex items-center justify-center gap-2">
          <Activity className={clsx(
            'w-4 h-4',
            isConnected ? 'text-accent-emerald animate-pulse' : 'text-accent-red'
          )} />
          {!collapsed && (
            <span className="text-xs text-text-muted">
              {isConnected ? 'WebSocket Connected' : 'Disconnected'}
            </span>
          )}
        </div>
      </div>
    </motion.aside>
  )
}

