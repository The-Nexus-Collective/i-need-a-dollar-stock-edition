'use client'

import { useState, useEffect, useCallback } from 'react'
import { api } from './api'

export interface PortfolioData {
  totalEquity: number
  initialCapital: number
  cash: number
  positionsValue: number
  unrealizedPnl: number
  realizedPnl: number
  totalPnl: number
  pnlPercent: number
  openPositions: number
  totalTrades: number
  winningTrades: number
  losingTrades: number
  winRate: number
  totalVolume: number
  totalFees: number
  totalSpread: number
  totalSlippage: number
  totalTradingCosts: number
  maxDrawdown: number
}

const DEFAULT_PORTFOLIO: PortfolioData = {
  totalEquity: 100000,
  initialCapital: 100000,
  cash: 100000,
  positionsValue: 0,
  unrealizedPnl: 0,
  realizedPnl: 0,
  totalPnl: 0,
  pnlPercent: 0,
  openPositions: 0,
  totalTrades: 0,
  winningTrades: 0,
  losingTrades: 0,
  winRate: 0,
  totalVolume: 0,
  totalFees: 0,
  totalSpread: 0,
  totalSlippage: 0,
  totalTradingCosts: 0,
  maxDrawdown: 0,
}

/**
 * Hook to fetch and cache portfolio data from the backend.
 * All statistics are calculated server-side from all trades in the database.
 */
export function usePortfolio(refreshInterval = 5000) {
  const [portfolio, setPortfolio] = useState<PortfolioData>(DEFAULT_PORTFOLIO)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchPortfolio = useCallback(async () => {
    try {
      const data = await api.getPortfolio()
      
      if (data) {
        setPortfolio({
          totalEquity: data.total_equity ?? 100000,
          initialCapital: data.initial_capital ?? 100000,
          cash: data.cash ?? 100000,
          positionsValue: data.positions_value ?? 0,
          unrealizedPnl: data.unrealized_pnl ?? 0,
          realizedPnl: data.realized_pnl ?? 0,
          totalPnl: data.total_pnl ?? 0,
          pnlPercent: data.pnl_percent ?? 0,
          openPositions: data.open_positions ?? 0,
          totalTrades: data.total_trades ?? 0,
          winningTrades: data.winning_trades ?? 0,
          losingTrades: data.losing_trades ?? 0,
          winRate: data.win_rate ?? 0,
          totalVolume: data.total_volume ?? 0,
          totalFees: data.total_fees ?? 0,
          totalSpread: data.total_spread ?? 0,
          totalSlippage: data.total_slippage ?? 0,
          totalTradingCosts: data.total_trading_costs ?? 0,
          maxDrawdown: data.max_drawdown ?? 0,
        })
        setError(null)
      }
    } catch (err) {
      console.error('Failed to fetch portfolio:', err)
      setError('Failed to load portfolio data')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchPortfolio()
    const interval = setInterval(fetchPortfolio, refreshInterval)
    return () => clearInterval(interval)
  }, [fetchPortfolio, refreshInterval])

  return {
    portfolio,
    loading,
    error,
    refresh: fetchPortfolio,
  }
}

