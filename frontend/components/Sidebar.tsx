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
  AlertTriangle,
  BookOpen,
} from 'lucide-react'
import { clsx } from 'clsx'
import { usePortfolio } from '@/lib/usePortfolio'

interface SidebarProps {
  isConnected: boolean
}

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', href: '/' },
  { icon: TrendingUp, label: 'Positions', href: '/positions' },
  { icon: BookOpen, label: 'Logbook', href: '/logbook' },
  { icon: History, label: 'History', href: '/history' },
  { icon: Shield, label: 'Risk', href: '/risk' },
  { icon: Settings, label: 'Settings', href: '/settings' },
]

export function Sidebar({ isConnected }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false)
  const { portfolio, marginHealth } = usePortfolio(3000) // Faster refresh for sidebar
  const pathname = usePathname()

  const pnl = isNaN(portfolio?.totalPnl) ? 0 : (portfolio?.totalPnl ?? 0)
  const pnlPercent = isNaN(portfolio?.pnlPercent) ? 0 : (portfolio?.pnlPercent ?? 0)
  const winRate = isNaN(portfolio?.winRate) ? 0 : (portfolio?.winRate ?? 0)
  const totalEquity = isNaN(portfolio?.totalEquity) ? 100000 : (portfolio?.totalEquity ?? 100000)
  const totalTrades = portfolio?.totalTrades ?? 0
  const totalFees = isNaN(portfolio?.totalFees) ? 0 : (portfolio?.totalFees ?? 0)
  const totalSpread = isNaN(portfolio?.totalSpread) ? 0 : (portfolio?.totalSpread ?? 0)
  const totalSlippage = isNaN(portfolio?.totalSlippage) ? 0 : (portfolio?.totalSlippage ?? 0)

  // Margin status display config
  const marginStatusConfig = {
    safe: {
      dotClass: 'bg-accent-emerald shadow-[0_0_8px_rgba(0,255,136,0.5)]',
      textClass: 'text-accent-emerald',
      label: 'Margin OK',
    },
    warning: {
      dotClass: 'bg-accent-amber shadow-[0_0_8px_rgba(255,170,51,0.5)] animate-pulse',
      textClass: 'text-accent-amber',
      label: 'Margin Warning',
    },
    danger: {
      dotClass: 'bg-accent-red shadow-[0_0_8px_rgba(255,71,87,0.5)] animate-pulse',
      textClass: 'text-accent-red',
      label: 'Margin Risk',
    },
    critical: {
      dotClass: 'bg-accent-red shadow-[0_0_12px_rgba(255,71,87,0.7)] animate-pulse',
      textClass: 'text-accent-red',
      label: 'MARGIN CRITICAL',
    },
  }
  
  const marginStatus = marginHealth?.overall_status ?? 'safe'
  const marginConfig = marginStatusConfig[marginStatus]
  const atRiskCount = (marginHealth?.positions_warning ?? 0) + (marginHealth?.positions_danger ?? 0)
  const totalPositions = marginHealth?.total_positions ?? 0

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
            <h1 className="font-semibold text-text-primary tracking-tight text-sm whitespace-nowrap">I Need A Dollar</h1>
            <p className="text-[10px] text-text-muted uppercase tracking-widest">AI Trading Terminal</p>
            <span className="px-1.5 py-0.5 text-[8px] font-bold uppercase tracking-wide bg-gradient-to-r from-purple-500/20 to-violet-500/20 text-purple-400 border border-purple-500/40 rounded inline-block mt-0.5">
              Crypto-Edition
            </span>
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
        {/* Paper mode indicator */}
        <div className="flex items-center gap-2 mb-3">
          <div className="w-2 h-2 rounded-full bg-accent-amber shadow-[0_0_8px_rgba(255,170,51,0.5)]" />
          <AnimatePresence mode="wait">
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                className="text-xs font-medium uppercase tracking-wider text-accent-amber"
              >
                Paper Mode
              </motion.span>
            )}
          </AnimatePresence>
        </div>
        
        {/* Margin health indicator */}
        <Link href="/risk" className="block">
          <div className={clsx(
            'flex items-center gap-2 transition-opacity',
            totalPositions === 0 && 'opacity-50'
          )}>
            <div className={clsx('w-2 h-2 rounded-full', marginConfig.dotClass)} />
            <AnimatePresence mode="wait">
              {!collapsed && (
                <motion.div
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                  className="flex items-center gap-1.5"
                >
                  <span className={clsx('text-xs font-medium uppercase tracking-wider', marginConfig.textClass)}>
                    {totalPositions === 0 ? 'No Positions' : `${totalPositions} Position${totalPositions > 1 ? 's' : ''}`}
                  </span>
                  {atRiskCount > 0 && (
                    <span className={clsx(
                      'px-1.5 py-0.5 text-[10px] font-bold rounded',
                      marginStatus === 'warning' 
                        ? 'bg-accent-amber/20 text-accent-amber'
                        : 'bg-accent-red/20 text-accent-red'
                    )}>
                      {atRiskCount}
                    </span>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
            {collapsed && atRiskCount > 0 && (
              <AlertTriangle className={clsx(
                'w-3 h-3 absolute right-2',
                marginStatus === 'warning' ? 'text-accent-amber' : 'text-accent-red'
              )} />
            )}
          </div>
        </Link>
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
              <p className={clsx(
                'text-xl font-mono font-semibold',
                pnl >= 0 ? 'text-text-primary' : 'text-accent-red'
              )}>
                ${totalEquity.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </p>
              <p className={clsx(
                'text-xs font-mono mt-1',
                pnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'
              )}>
                {pnl >= 0 ? '+' : '-'}${Math.abs(pnl).toLocaleString('en-US', { minimumFractionDigits: 2 })} ({pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%)
              </p>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-2 gap-2">
              <div className="glass-card p-3">
                <span className="text-label block mb-1">Win Rate</span>
                <p className={clsx(
                  'text-sm font-mono font-semibold',
                  winRate >= 50 ? 'text-accent-emerald' : 'text-text-primary'
                )}>
                  {winRate.toFixed(1)}%
                </p>
              </div>
              <div className="glass-card p-3">
                <span className="text-label block mb-1">Trades</span>
                <p className="text-sm font-mono font-semibold text-text-primary">
                  {totalTrades}
                </p>
              </div>
              <div className="glass-card p-3">
                <span className="text-label block mb-1">Fees</span>
                <p className="text-sm font-mono font-semibold text-accent-amber">
                  ${totalFees.toFixed(2)}
                </p>
              </div>
              <div className="glass-card p-3">
                <span className="text-label block mb-1">Slippage</span>
                <p className="text-sm font-mono font-semibold text-accent-amber">
                  ${(totalSpread + totalSlippage).toFixed(2)}
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

