'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
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

export interface MarginHealthData {
  overall_status: 'safe' | 'warning' | 'danger' | 'critical'
  total_positions: number
  positions_safe: number
  positions_warning: number
  positions_danger: number
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

const DEFAULT_MARGIN_HEALTH: MarginHealthData = {
  overall_status: 'safe',
  total_positions: 0,
  positions_safe: 0,
  positions_warning: 0,
  positions_danger: 0,
}

/**
 * Hook to fetch and cache portfolio data from the Portfolio Manager.
 * Includes real-time WebSocket updates for equity.
 */
export function usePortfolio(refreshInterval = 5000) {
  const [portfolio, setPortfolio] = useState<PortfolioData>(DEFAULT_PORTFOLIO)
  const [marginHealth, setMarginHealth] = useState<MarginHealthData>(DEFAULT_MARGIN_HEALTH)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const fetchPortfolio = useCallback(async () => {
    try {
      // Fetch from Portfolio Manager which has the real live data
      const pmStatus = await api.getPortfolioManagerStatus().catch(() => null)
      
      if (pmStatus && pmStatus.portfolio) {
        const stats = pmStatus.portfolio.statistics
        const positions = pmStatus.portfolio.positions || []
        
        const totalEquity = stats.total_equity ?? INITIAL_CAPITAL
        const startingCapital = stats.starting_capital ?? INITIAL_CAPITAL
        const totalPnl = stats.total_pnl ?? 0
        const pnlPercent = startingCapital > 0 ? (totalPnl / startingCapital) * 100 : 0
        const positionsValue = positions.reduce((sum: number, p: any) => sum + (p.size_usdt ?? 0), 0)
        
        // Calculate margin health from positions
        const marginPositions = positions.map((p: any) => {
          const distanceToLiq = Math.abs((p.current_price - p.liquidation_price) / p.current_price) * 100
          return { distanceToLiq }
        })
        
        const positionsSafe = marginPositions.filter((p: any) => p.distanceToLiq >= 15).length
        const positionsWarning = marginPositions.filter((p: any) => p.distanceToLiq >= 5 && p.distanceToLiq < 15).length
        const positionsDanger = marginPositions.filter((p: any) => p.distanceToLiq < 5).length
        
        const overallStatus: 'safe' | 'warning' | 'danger' | 'critical' = 
          positionsDanger > 0 ? 'danger' :
          positionsWarning > 0 ? 'warning' : 'safe'
        
        setMarginHealth({
          overall_status: overallStatus,
          total_positions: positions.length,
          positions_safe: positionsSafe,
          positions_warning: positionsWarning,
          positions_danger: positionsDanger,
        })
        
        setPortfolio({
          totalEquity,
          initialCapital: startingCapital,
          cash: stats.current_capital ?? INITIAL_CAPITAL,
          positionsValue,
          unrealizedPnl: stats.unrealized_pnl ?? 0,
          realizedPnl: stats.realized_pnl ?? 0,
          totalPnl: isNaN(totalPnl) ? 0 : totalPnl,
          pnlPercent: isNaN(pnlPercent) ? 0 : pnlPercent,
          openPositions: stats.open_positions ?? positions.length ?? 0,
          totalTrades: stats.total_trades ?? 0,
          winningTrades: stats.winning_trades ?? 0,
          losingTrades: stats.losing_trades ?? 0,
          winRate: stats.win_rate ?? 0,
          totalVolume: 0,
          totalFees: stats.total_fees ?? 0,
          totalSpread: (stats as any).total_spread ?? 0,
          totalSlippage: (stats as any).total_slippage ?? 0,
          totalTradingCosts: (stats.total_fees ?? 0) + ((stats as any).total_spread ?? 0) + ((stats as any).total_slippage ?? 0),
          maxDrawdown: 0,
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

  // WebSocket for real-time equity updates
  useEffect(() => {
    const connectWebSocket = () => {
      try {
        // Build WebSocket URL - append /equity to base URL if needed
        const wsBase = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8081/ws'
        const wsUrl = wsBase.endsWith('/equity') ? wsBase : `${wsBase}/equity`
        const ws = new WebSocket(wsUrl)
        wsRef.current = ws
        
        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data)
            
            if (message.type === 'equity_update' && message.data) {
              const data = message.data
              // WebSocket sends total_equity, not equity
              const equity = data.total_equity ?? data.equity
              const unrealizedPnl = data.unrealized_pnl ?? 0
              
              if (equity && !isNaN(equity)) {
                setPortfolio(prev => {
                  const totalPnl = equity - prev.initialCapital
                  const pnlPercent = prev.initialCapital > 0 
                    ? ((equity - prev.initialCapital) / prev.initialCapital) * 100 
                    : 0
                  
                  return {
                    ...prev,
                    totalEquity: equity,
                    unrealizedPnl: isNaN(unrealizedPnl) ? prev.unrealizedPnl : unrealizedPnl,
                    totalPnl: isNaN(totalPnl) ? prev.totalPnl : totalPnl,
                    pnlPercent: isNaN(pnlPercent) ? prev.pnlPercent : pnlPercent,
                  }
                })
              }
            }
          } catch (e) {
            // Ignore parse errors
          }
        }
        
        ws.onclose = () => {
          // Reconnect after 3 seconds
          setTimeout(connectWebSocket, 3000)
        }
        
        ws.onerror = () => {
          ws.close()
        }
      } catch (e) {
        console.error('WebSocket connection error:', e)
      }
    }
    
    connectWebSocket()
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  useEffect(() => {
    fetchPortfolio()
    const interval = setInterval(fetchPortfolio, refreshInterval)
    return () => clearInterval(interval)
  }, [fetchPortfolio, refreshInterval])

  return {
    portfolio,
    marginHealth,
    loading,
    error,
    refresh: fetchPortfolio,
  }
}
