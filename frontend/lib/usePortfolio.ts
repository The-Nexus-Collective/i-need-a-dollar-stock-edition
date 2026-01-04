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

const INITIAL_CAPITAL = 100000

const DEFAULT_PORTFOLIO: PortfolioData = {
  totalEquity: INITIAL_CAPITAL,
  initialCapital: INITIAL_CAPITAL,
  cash: INITIAL_CAPITAL,
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
        const totalEquity = data.total_equity ?? INITIAL_CAPITAL
        const totalPnl = totalEquity - INITIAL_CAPITAL
        const pnlPercent = (totalPnl / INITIAL_CAPITAL) * 100
        
        setPortfolio({
          totalEquity,
          initialCapital: INITIAL_CAPITAL,
          cash: data.cash ?? INITIAL_CAPITAL,
          positionsValue: data.positions_value ?? 0,
          unrealizedPnl: data.unrealized_pnl ?? 0,
          realizedPnl: data.realized_pnl ?? 0,
          totalPnl,
          pnlPercent,
          openPositions: data.open_positions ?? 0,
          // These fields may not be in the API response - use defaults
          totalTrades: 0,
          winningTrades: 0,
          losingTrades: 0,
          winRate: data.win_rate ?? 0,
          totalVolume: 0,
          totalFees: 0,
          totalSpread: 0,
          totalSlippage: 0,
          totalTradingCosts: 0,
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
