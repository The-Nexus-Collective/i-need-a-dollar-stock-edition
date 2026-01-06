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

const INITIAL_CAPITAL = 0

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
 * Hook to fetch and cache portfolio data from the Portfolio Manager.
 * Includes real-time WebSocket updates for equity.
 */
export function usePortfolio(refreshInterval = 5000) {
  const [portfolio, setPortfolio] = useState<PortfolioData>(DEFAULT_PORTFOLIO)
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
        // Build WebSocket URL for equity updates
        let wsUrl: string
        
        if (process.env.NEXT_PUBLIC_WS_URL) {
          // Explicit WebSocket URL configured
          const wsBase = process.env.NEXT_PUBLIC_WS_URL
          wsUrl = wsBase.endsWith('/equity') ? wsBase : `${wsBase}/equity`
        } else if (typeof window !== 'undefined' && window.location.hostname !== 'localhost') {
          // Production: use relative path (relies on Next.js rewrites or platform routing)
          const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
          wsUrl = `${protocol}//${window.location.host}/ws/equity`
        } else {
          // Development: connect directly to backend
          wsUrl = 'ws://localhost:8081/ws/equity'
        }
        
        console.log('Connecting to WebSocket:', wsUrl)
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
        
        ws.onopen = () => {
          console.log('Equity WebSocket connected')
        }
        
        ws.onclose = (event) => {
          console.log('Equity WebSocket disconnected', event.code, event.reason)
          // Reconnect after 3 seconds
          setTimeout(connectWebSocket, 3000)
        }
        
        ws.onerror = (error) => {
          console.error('Equity WebSocket error:', error)
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
    loading,
    error,
    refresh: fetchPortfolio,
  }
}
