'use client'

import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import clsx from 'clsx'
import { Sidebar } from '@/components/Sidebar'
import { MobileHeader } from '@/components/MobileHeader'

interface MarketStatus {
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
}

interface MarketRegime {
  is_open: boolean
  regime: string
  regime_display: string
  vix_level: number | null
  next_open: string | null
  next_close: string | null
}

export default function StocksPage() {
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(null)
  const [regime, setRegime] = useState<MarketRegime | null>(null)
  const [loading, setLoading] = useState(true)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  useEffect(() => {
    async function fetchData() {
      try {
        const [marketData, regimeData] = await Promise.all([
          api.getMarketStatus().catch(() => null),
          api.getMarketRegime().catch(() => null),
        ])

        if (marketData) setMarketStatus(marketData)
        if (regimeData) setRegime(regimeData)
      } catch (error) {
        console.error('Failed to fetch stock data:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 60000) // Refresh every minute
    return () => clearInterval(interval)
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen bg-void flex items-center justify-center">
        <div className="text-text-muted">Loading stock data...</div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-void">
      <Sidebar 
        isConnected={true} 
        mobileOpen={mobileMenuOpen}
        onMobileClose={() => setMobileMenuOpen(false)}
      />

      <main className="flex-1 md:ml-[280px] min-w-0">
        {/* Mobile Header */}
        <MobileHeader 
          onMenuClick={() => setMobileMenuOpen(true)}
          isConnected={true}
          title="Stock Universe"
        />

        <div className="p-4 md:p-6 lg:p-8">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <h1 className="text-2xl font-bold text-text-primary">Stock Universe</h1>
            <div className="flex items-center gap-4">
              {/* Market Status Badge */}
              <div className={clsx(
                'px-4 py-2 rounded-lg font-medium',
                marketStatus?.is_open || regime?.is_open
                  ? 'bg-accent-emerald/10 text-accent-emerald'
                  : 'bg-accent-amber/10 text-accent-amber'
              )}>
                {marketStatus?.is_open || regime?.is_open ? '🟢 Market Open' : '🔴 Market Closed'}
              </div>
            </div>
          </div>

          {/* Top Row - Market Status & VIX */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
            {/* Market Hours Card */}
            <div className="glass-card p-6">
              <h2 className="text-lg font-semibold text-text-primary mb-4">Market Hours</h2>
              <div className="space-y-3">
                <div className="flex justify-between">
                  <span className="text-text-secondary">Status</span>
                  <span className="font-medium text-text-primary">
                    {marketStatus?.description || (regime?.is_open ? 'Market Open' : 'Market Closed')}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Next Event</span>
                  <span className="font-mono text-text-muted">
                    {marketStatus?.next_open_display || (regime?.next_open ? `Opens: ${regime.next_open}` : '-')}
                  </span>
                </div>
                {regime?.next_close && regime.is_open && (
                  <div className="flex justify-between">
                    <span className="text-text-secondary">Closes At</span>
                    <span className="font-mono text-text-muted">{regime.next_close}</span>
                  </div>
                )}
              </div>
            </div>

            {/* VIX Regime Card */}
            <div className="glass-card p-6">
              <h2 className="text-lg font-semibold text-text-primary mb-4">Market Regime</h2>
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-text-secondary">VIX Level</span>
                  <span className={clsx(
                    'text-2xl font-bold',
                    regime?.vix_level && regime.vix_level < 15 && 'text-accent-emerald',
                    regime?.vix_level && regime.vix_level >= 15 && regime.vix_level < 25 && 'text-text-primary',
                    regime?.vix_level && regime.vix_level >= 25 && regime.vix_level < 35 && 'text-accent-amber',
                    regime?.vix_level && regime.vix_level >= 35 && 'text-accent-red'
                  )}>
                    {regime?.vix_level?.toFixed(1) || 'N/A'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-secondary">Regime</span>
                  <span className={clsx(
                    'px-2 py-0.5 rounded-full text-xs font-medium',
                    regime?.regime === 'low_vol' && 'bg-accent-emerald/10 text-accent-emerald',
                    regime?.regime === 'normal' && 'bg-accent-cyan/10 text-accent-cyan',
                    regime?.regime === 'high_vol' && 'bg-accent-amber/10 text-accent-amber',
                    regime?.regime === 'crisis' && 'bg-accent-red/10 text-accent-red'
                  )}>
                    {regime?.regime_display || 'Unknown'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Tech Stocks Watchlist */}
          <div className="glass-card p-6 mb-6">
            <h2 className="text-lg font-semibold text-text-primary mb-4">Tech Stocks</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 lg:grid-cols-10 gap-3">
              {['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'ADBE', 'CRM', 'INTC', 
                'CSCO', 'IBM', 'ORCL', 'SAP', 'ASML', 'TXN', 'QCOM', 'AMD', 'AVGO', 'MU'].map(symbol => (
                <div
                  key={symbol}
                  className="p-3 rounded-lg bg-surface-2 border border-glass-border text-center hover:bg-surface-3 transition-colors"
                >
                  <span className="font-mono font-medium text-accent-cyan">{symbol}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Defense Stocks Watchlist */}
          <div className="glass-card p-6 mb-6">
            <h2 className="text-lg font-semibold text-text-primary mb-4">Defense Stocks</h2>
            <div className="grid grid-cols-2 md:grid-cols-5 lg:grid-cols-10 gap-3">
              {['LMT', 'RTX', 'BA', 'GD', 'NOC', 'LHX', 'HII', 'TDY', 'TXT', 'KBR',
                'FLIR', 'OSK', 'VEC', 'AJRD', 'HEI', 'CW', 'ESMC', 'SRDX', 'IRDM', 'MAXR'].map(symbol => (
                <div
                  key={symbol}
                  className="p-3 rounded-lg bg-surface-2 border border-glass-border text-center hover:bg-surface-3 transition-colors"
                >
                  <span className="font-mono font-medium text-accent-emerald">{symbol}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Info Footer */}
          <div className="text-center text-sm text-text-muted">
            <p>Stock trading operates during US market hours (9:30 AM - 4:00 PM ET)</p>
            <p>Paper trading mode • Focus on highly liquid Tech & Defense stocks</p>
          </div>
        </div>
      </main>
    </div>
  )
}
