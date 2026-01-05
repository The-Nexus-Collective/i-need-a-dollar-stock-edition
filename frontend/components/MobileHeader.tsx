'use client'

import { Menu, Zap, Activity } from 'lucide-react'
import { clsx } from 'clsx'

interface MobileHeaderProps {
  onMenuClick: () => void
  isConnected?: boolean
  title?: string
}

export function MobileHeader({ onMenuClick, isConnected = false, title }: MobileHeaderProps) {
  return (
    <header className="sticky top-0 z-30 md:hidden glass-sidebar border-b border-glass-border">
      <div className="flex items-center justify-between px-4 py-3">
        {/* Left: Hamburger + Branding */}
        <div className="flex items-center gap-3">
          <button
            onClick={onMenuClick}
            className="p-2 -ml-2 rounded-lg hover:bg-glass-bg active:bg-glass-bg transition-colors text-text-secondary min-h-[44px] min-w-[44px] flex items-center justify-center"
            aria-label="Open menu"
          >
            <Menu className="w-6 h-6" />
          </button>
          
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-cyan to-accent-emerald flex items-center justify-center shadow-glow-cyan">
              <Zap className="w-4 h-4 text-void" />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-semibold text-text-primary tracking-tight">
                {title || 'I Need A Dollar'}
              </span>
              <span className="text-[9px] text-text-muted uppercase tracking-widest">
                AI Trading
              </span>
            </div>
          </div>
        </div>

        {/* Right: Connection Status */}
        <div className="flex items-center gap-2">
          <div className={clsx(
            'flex items-center gap-1.5 px-2 py-1 rounded-full text-xs',
            isConnected 
              ? 'bg-accent-emerald/10 text-accent-emerald' 
              : 'bg-accent-red/10 text-accent-red'
          )}>
            <Activity className={clsx(
              'w-3 h-3',
              isConnected && 'animate-pulse'
            )} />
            <span className="hidden xs:inline">
              {isConnected ? 'Live' : 'Offline'}
            </span>
          </div>
        </div>
      </div>
    </header>
  )
}

