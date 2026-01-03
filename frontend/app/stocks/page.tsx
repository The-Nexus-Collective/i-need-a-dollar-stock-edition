'use client'

import { useState, useEffect } from 'react'
import { api } from '@/lib/api'
import clsx from 'clsx'

interface MarketStatus {
  is_open: boolean
  status_text: string
  next_event: string
  should_flatten: boolean
  time_to_close_seconds: number | null
}

interface StockRegime {
  vix_value: number
  regime: string
  regime_display: string
  score_threshold: number
  should_trade: boolean
}

interface PortfolioData {
  crypto: {
    equity: number
    currency: string
    positions: number
    pnl: number
    pnl_pct: number
  }
  stock: {
    equity: number
    currency: string
    positions: number
    pnl: number
    pnl_pct: number
  }
  total: {
    equity_usd: number
    pnl_usd: number
  }
}

interface HypeScore {
  symbol: string
  score: number
  tweet_count: number
  sentiment_score: number
  top_tweets: Array<{ text: string; engagement: number }>
}

export default function StocksPage() {
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(null)
  const [regime, setRegime] = useState<StockRegime | null>(null)
  const [portfolio, setPortfolio] = useState<PortfolioData | null>(null)
  const [hypeScores, setHypeScores] = useState<Record<string, HypeScore>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchData() {
      try {
        const [marketData, regimeData, portfolioData, hypeData] = await Promise.all([
          api.getMarketStatus().catch(() => null),
          api.getStockRegime().catch(() => null),
          api.getMultiPortfolio().catch(() => null),
          api.getStockHype('PLTR,RTX,LMT,NOC,BA').catch(() => ({})),
        ])

        if (marketData) setMarketStatus(marketData)
        if (regimeData) setRegime(regimeData)
        if (portfolioData) setPortfolio(portfolioData)
        if (hypeData) setHypeScores(hypeData)
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
      <div className="min-h-screen bg-bg-primary flex items-center justify-center">
        <div className="text-text-muted">Loading stock data...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-bg-primary p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-text-primary">Stock Trading</h1>
          <div className="flex items-center gap-4">
            {/* Market Status Badge */}
            <div className={clsx(
              'px-4 py-2 rounded-lg font-medium',
              marketStatus?.is_open
                ? 'bg-accent-emerald/10 text-accent-emerald'
                : 'bg-accent-amber/10 text-accent-amber'
            )}>
              {marketStatus?.is_open ? '🟢 Market Open' : '🔴 Market Closed'}
            </div>
          </div>
        </div>

        {/* Top Row - Market Status & VIX */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Market Hours Card */}
          <div className="bg-bg-secondary rounded-xl p-6 border border-border-primary">
            <h2 className="text-lg font-semibold text-text-primary mb-4">Market Hours</h2>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-text-secondary">Status</span>
                <span className="font-medium text-text-primary">
                  {marketStatus?.status_text || 'Unknown'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Next Event</span>
                <span className="font-mono text-text-muted">
                  {marketStatus?.next_event || '-'}
                </span>
              </div>
              {marketStatus?.should_flatten && (
                <div className="mt-4 p-3 bg-accent-amber/10 rounded-lg">
                  <span className="text-accent-amber font-medium">
                    ⚠️ Flatten Signal Active
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* VIX Regime Card */}
          <div className="bg-bg-secondary rounded-xl p-6 border border-border-primary">
            <h2 className="text-lg font-semibold text-text-primary mb-4">Volatility Regime</h2>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-text-secondary">VIX</span>
                <span className={clsx(
                  'text-2xl font-bold',
                  regime?.vix_value && regime.vix_value < 15 && 'text-accent-emerald',
                  regime?.vix_value && regime.vix_value >= 15 && regime.vix_value < 25 && 'text-text-primary',
                  regime?.vix_value && regime.vix_value >= 25 && regime.vix_value < 35 && 'text-accent-amber',
                  regime?.vix_value && regime.vix_value >= 35 && 'text-accent-red'
                )}>
                  {regime?.vix_value?.toFixed(1) || '-'}
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
              <div className="flex justify-between">
                <span className="text-text-secondary">Score Threshold</span>
                <span className="font-mono text-text-muted">
                  {regime?.score_threshold || 70}
                </span>
              </div>
              {regime && !regime.should_trade && (
                <div className="mt-4 p-3 bg-accent-red/10 rounded-lg">
                  <span className="text-accent-red font-medium">
                    🛑 Trading Paused
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Combined Portfolio Card */}
          <div className="bg-bg-secondary rounded-xl p-6 border border-border-primary">
            <h2 className="text-lg font-semibold text-text-primary mb-4">Portfolio Summary</h2>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-text-secondary">Total Equity</span>
                <span className="text-xl font-bold text-text-primary">
                  ${portfolio?.total.equity_usd?.toLocaleString(undefined, { maximumFractionDigits: 0 }) || '200,000'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Total P&L</span>
                <span className={clsx(
                  'font-medium',
                  portfolio?.total.pnl_usd && portfolio.total.pnl_usd >= 0 ? 'text-accent-emerald' : 'text-accent-red'
                )}>
                  {portfolio?.total.pnl_usd && portfolio.total.pnl_usd >= 0 ? '+' : ''}
                  ${portfolio?.total.pnl_usd?.toLocaleString(undefined, { maximumFractionDigits: 2 }) || '0'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Portfolio Breakdown */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Crypto Portfolio */}
          <div className="bg-bg-secondary rounded-xl p-6 border border-border-primary">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-2xl">₿</span>
              <h2 className="text-lg font-semibold text-text-primary">Crypto Portfolio</h2>
            </div>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-text-secondary">Equity</span>
                <span className="font-mono text-text-primary">
                  {portfolio?.crypto.equity?.toLocaleString() || '100,000'} {portfolio?.crypto.currency || 'USDT'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Open Positions</span>
                <span className="font-mono text-text-muted">
                  {portfolio?.crypto.positions || 0}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">P&L</span>
                <span className={clsx(
                  'font-medium',
                  portfolio?.crypto.pnl && portfolio.crypto.pnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'
                )}>
                  {portfolio?.crypto.pnl && portfolio.crypto.pnl >= 0 ? '+' : ''}
                  {portfolio?.crypto.pnl?.toFixed(2) || '0'} ({portfolio?.crypto.pnl_pct?.toFixed(2) || '0'}%)
                </span>
              </div>
            </div>
          </div>

          {/* Stock Portfolio */}
          <div className="bg-bg-secondary rounded-xl p-6 border border-border-primary">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-2xl">📈</span>
              <h2 className="text-lg font-semibold text-text-primary">Stock Portfolio</h2>
            </div>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-text-secondary">Equity</span>
                <span className="font-mono text-text-primary">
                  ${portfolio?.stock.equity?.toLocaleString() || '100,000'} {portfolio?.stock.currency || 'USD'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Open Positions</span>
                <span className="font-mono text-text-muted">
                  {portfolio?.stock.positions || 0}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">P&L</span>
                <span className={clsx(
                  'font-medium',
                  portfolio?.stock.pnl && portfolio.stock.pnl >= 0 ? 'text-accent-emerald' : 'text-accent-red'
                )}>
                  {portfolio?.stock.pnl && portfolio.stock.pnl >= 0 ? '+' : ''}
                  ${portfolio?.stock.pnl?.toFixed(2) || '0'} ({portfolio?.stock.pnl_pct?.toFixed(2) || '0'}%)
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* X Hype Detection */}
        <div className="bg-bg-secondary rounded-xl p-6 border border-border-primary">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-2xl">𝕏</span>
            <h2 className="text-lg font-semibold text-text-primary">X Hype Detection</h2>
            <span className="text-xs text-text-muted">(Reserved Stocks)</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            {Object.entries(hypeScores).map(([symbol, data]) => (
              <div
                key={symbol}
                className={clsx(
                  'p-4 rounded-lg border',
                  data.score >= 50 ? 'border-accent-emerald/30 bg-accent-emerald/5' :
                  data.score >= 30 ? 'border-accent-amber/30 bg-accent-amber/5' :
                  'border-border-primary bg-bg-tertiary'
                )}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-text-primary">{symbol}</span>
                  <span className={clsx(
                    'text-lg font-bold',
                    data.score >= 50 ? 'text-accent-emerald' :
                    data.score >= 30 ? 'text-accent-amber' :
                    'text-text-muted'
                  )}>
                    {data.score.toFixed(0)}
                  </span>
                </div>
                <div className="text-xs text-text-muted">
                  {data.tweet_count} tweets
                </div>
                {data.top_tweets?.[0] && (
                  <div className="mt-2 text-xs text-text-secondary line-clamp-2">
                    &ldquo;{data.top_tweets[0].text}&rdquo;
                  </div>
                )}
              </div>
            ))}

            {Object.keys(hypeScores).length === 0 && (
              <div className="col-span-5 text-center py-8 text-text-muted">
                No X hype data available. Set X_BEARER_TOKEN to enable.
              </div>
            )}
          </div>
        </div>

        {/* Stock Watchlist */}
        <div className="bg-bg-secondary rounded-xl p-6 border border-border-primary">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Core Stock Watchlist</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {['AAPL', 'NVDA', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'AVGO', 'NFLX', 'ADBE'].map(symbol => (
              <div
                key={symbol}
                className="p-3 rounded-lg bg-bg-tertiary border border-border-primary text-center"
              >
                <span className="font-mono font-medium text-text-primary">{symbol}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Info Footer */}
        <div className="text-center text-sm text-text-muted">
          <p>Stock trading operates during US market hours (9:30 AM - 4:00 PM ET)</p>
          <p>Paper trading mode • 3-5x leverage via CFDs • Flatten at close</p>
        </div>
      </div>
    </div>
  )
}

