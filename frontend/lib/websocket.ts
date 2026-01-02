'use client'

import { useEffect, useRef, useState, useCallback } from 'react'

interface WebSocketMessage {
  type: string
  event_type?: string
  data?: any
  timestamp?: string
}

interface UseWebSocketOptions {
  channel?: string
  onMessage?: (message: WebSocketMessage) => void
  onConnect?: () => void
  onDisconnect?: () => void
  reconnectInterval?: number
  maxReconnectAttempts?: number
}

interface WebSocketState {
  isConnected: boolean
  lastMessage: WebSocketMessage | null
  error: Error | null
  reconnectCount: number
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    channel = 'all',
    onMessage,
    onConnect,
    onDisconnect,
    reconnectInterval = 3000,
    maxReconnectAttempts = 10,
  } = options

  const [state, setState] = useState<WebSocketState>({
    isConnected: false,
    lastMessage: null,
    error: null,
    reconnectCount: 0,
  })

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws'
    const url = `${wsUrl}?channel=${channel}`

    try {
      wsRef.current = new WebSocket(url)

      wsRef.current.onopen = () => {
        console.log('[WS] Connected to', url)
        setState(prev => ({
          ...prev,
          isConnected: true,
          error: null,
          reconnectCount: 0,
        }))
        onConnect?.()

        // Start ping interval
        pingIntervalRef.current = setInterval(() => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send('ping')
          }
        }, 25000)
      }

      wsRef.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)
          setState(prev => ({ ...prev, lastMessage: message }))
          onMessage?.(message)
        } catch (e) {
          // Handle non-JSON messages (like "pong")
          if (event.data !== 'pong') {
            console.warn('[WS] Non-JSON message:', event.data)
          }
        }
      }

      wsRef.current.onclose = () => {
        console.log('[WS] Disconnected')
        setState(prev => ({ ...prev, isConnected: false }))
        onDisconnect?.()

        // Clear ping interval
        if (pingIntervalRef.current) {
          clearInterval(pingIntervalRef.current)
        }

        // Attempt reconnect
        if (state.reconnectCount < maxReconnectAttempts) {
          reconnectTimeoutRef.current = setTimeout(() => {
            setState(prev => ({
              ...prev,
              reconnectCount: prev.reconnectCount + 1,
            }))
            connect()
          }, reconnectInterval)
        }
      }

      wsRef.current.onerror = (error) => {
        console.error('[WS] Error:', error)
        setState(prev => ({
          ...prev,
          error: new Error('WebSocket connection failed'),
        }))
      }
    } catch (error) {
      console.error('[WS] Failed to create connection:', error)
      setState(prev => ({
        ...prev,
        error: error as Error,
      }))
    }
  }, [channel, onConnect, onDisconnect, onMessage, reconnectInterval, maxReconnectAttempts, state.reconnectCount])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current)
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message))
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      disconnect()
    }
  }, []) // Only run on mount/unmount

  return {
    ...state,
    connect,
    disconnect,
    sendMessage,
  }
}

// Store for global state management
import { create } from 'zustand'

interface TradingState {
  portfolio: {
    total_equity: number
    cash: number
    positions_value: number
    unrealized_pnl: number
    realized_pnl: number
    daily_pnl: number
    daily_pnl_percent: number
  } | null
  positions: any[]
  signals: Record<string, any>
  trades: any[]
  riskEvents: any[]
  isConnected: boolean
  lastUpdate: string | null
  
  // Actions
  setPortfolio: (portfolio: any) => void
  setPositions: (positions: any[]) => void
  setSignals: (signals: Record<string, any>) => void
  addTrade: (trade: any) => void
  addRiskEvent: (event: any) => void
  setConnected: (connected: boolean) => void
  updateFromEvent: (event: any) => void
}

export const useTradingStore = create<TradingState>((set, get) => ({
  portfolio: null,
  positions: [],
  signals: {},
  trades: [],
  riskEvents: [],
  isConnected: false,
  lastUpdate: null,

  setPortfolio: (portfolio) => set({ portfolio, lastUpdate: new Date().toISOString() }),
  setPositions: (positions) => set({ positions }),
  setSignals: (signals) => set({ signals }),
  addTrade: (trade) => set(state => ({ trades: [trade, ...state.trades].slice(0, 100) })),
  addRiskEvent: (event) => set(state => ({ riskEvents: [event, ...state.riskEvents].slice(0, 50) })),
  setConnected: (isConnected) => set({ isConnected }),
  
  updateFromEvent: (event) => {
    const eventType = event.event_type || event.type
    
    if (eventType?.includes('portfolio')) {
      set({ portfolio: event.data, lastUpdate: new Date().toISOString() })
    } else if (eventType?.includes('position')) {
      // Refresh positions on position events
      // This would typically trigger a refetch
    } else if (eventType?.includes('signal')) {
      const signals = get().signals
      if (event.data?.coin) {
        set({ signals: { ...signals, [event.data.coin]: event.data } })
      }
    } else if (eventType?.includes('order.filled')) {
      set(state => ({ trades: [event.data, ...state.trades].slice(0, 100) }))
    } else if (eventType?.includes('risk')) {
      set(state => ({ riskEvents: [event.data, ...state.riskEvents].slice(0, 50) }))
    }
  },
}))
