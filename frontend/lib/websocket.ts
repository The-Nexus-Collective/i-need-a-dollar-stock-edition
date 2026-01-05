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
  const reconnectCountRef = useRef(0)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    // Compute WebSocket URL - derive from current location in production
    let wsBase: string
    if (process.env.NEXT_PUBLIC_WS_URL) {
      wsBase = process.env.NEXT_PUBLIC_WS_URL
    } else if (typeof window !== 'undefined' && window.location.hostname !== 'localhost') {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      wsBase = `${protocol}//${window.location.host}/ws`
    } else {
      wsBase = 'ws://localhost:8081/ws'
    }
    const url = `${wsBase}?channel=${channel}`

    try {
      wsRef.current = new WebSocket(url)

      wsRef.current.onopen = () => {
        console.log('[WS] Connected to', url)
        reconnectCountRef.current = 0
        setState(prev => ({
          ...prev,
          isConnected: true,
          error: null,
          reconnectCount: 0,
        }))
        onConnect?.()

        // Start ping interval - 15 seconds for aggressive keepalive
        pingIntervalRef.current = setInterval(() => {
          if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send('ping')
          }
        }, 15000)
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

        // Attempt reconnect using ref to avoid stale closure
        if (reconnectCountRef.current < maxReconnectAttempts) {
          reconnectCountRef.current += 1
          reconnectTimeoutRef.current = setTimeout(() => {
            setState(prev => ({
              ...prev,
              reconnectCount: reconnectCountRef.current,
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
  }, [channel, onConnect, onDisconnect, onMessage, reconnectInterval, maxReconnectAttempts])

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

// ═══════════════════════════════════════════════════════════════════════════════
// ACTIVITY LOG TYPES
// ═══════════════════════════════════════════════════════════════════════════════

export type ActivityCategory = 'signal' | 'order' | 'position' | 'risk' | 'system' | 'portfolio'

export interface ActivityEntry {
  id: string
  timestamp: string
  category: ActivityCategory
  eventType: string
  title: string
  description: string
  coin?: string
  details?: Record<string, any>
}

// Map event types to activity categories
function getActivityCategory(eventType: string): ActivityCategory {
  if (eventType.includes('signal')) return 'signal'
  if (eventType.includes('order')) return 'order'
  if (eventType.includes('position')) return 'position'
  if (eventType.includes('risk')) return 'risk'
  if (eventType.includes('portfolio')) return 'portfolio'
  return 'system'
}

// Format event into readable activity entry
function formatActivityEntry(event: any): ActivityEntry | null {
  const eventType = event.event_type || event.type
  if (!eventType) return null
  
  // Skip heartbeats and pings
  if (eventType.includes('heartbeat') || eventType === 'ping' || eventType === 'pong') {
    return null
  }
  
  const category = getActivityCategory(eventType)
  const timestamp = event.timestamp || new Date().toISOString()
  const data = event.data || {}
  
  let title = ''
  let description = ''
  let coin = data.coin || data.symbol
  
  switch (eventType) {
    case 'signal.generated':
      title = `Signal: ${data.recommended_action?.toUpperCase() || 'ANALYSE'}`
      description = `${coin} Score: ${data.combined_score?.toFixed(1) || '?'}`
      break
    case 'order.submitted':
      title = `Order Submitted`
      description = `${data.side?.toUpperCase()} ${coin} @ ${data.price?.toLocaleString() || 'Market'}`
      break
    case 'order.filled':
      title = `Order Filled`
      description = `${data.side?.toUpperCase()} ${data.quantity} ${coin} @ $${data.fill_price?.toLocaleString()}`
      break
    case 'order.rejected':
      title = `Order Rejected`
      description = `${coin}: ${data.reason || 'Unknown reason'}`
      break
    case 'position.opened':
      title = `Position Opened`
      description = `${data.side?.toUpperCase()} ${coin} @ $${data.entry_price?.toLocaleString()}`
      break
    case 'position.closed':
      const pnl = data.realized_pnl
      const pnlStr = pnl >= 0 ? `+$${pnl?.toFixed(2)}` : `-$${Math.abs(pnl)?.toFixed(2)}`
      title = `Position Closed`
      description = `${coin}: ${pnlStr} (${data.close_reason || 'manual'})`
      break
    case 'position.updated':
      title = `Position Update`
      description = `${coin} PnL: ${data.unrealized_pnl_percent?.toFixed(2)}%`
      break
    case 'risk.approved':
      title = `Risk Approved`
      description = `${coin} ${data.action?.toUpperCase()}`
      break
    case 'risk.rejected':
      title = `Risk Rejected`
      description = `${coin}: ${data.rejection_reasons?.join(', ') || 'Limit exceeded'}`
      break
    case 'risk.limit_breach':
      title = `Risk Limit Breached`
      description = `${data.limit_type}: ${data.current_value?.toFixed(2)} > ${data.threshold_value?.toFixed(2)}`
      break
    case 'portfolio.snapshot':
      title = `Portfolio Update`
      description = `Equity: $${data.total_equity?.toLocaleString()}`
      break
    case 'system.circuit_breaker':
      title = `Circuit Breaker!`
      description = `Level ${data.level}: ${data.action_taken}`
      break
    default:
      title = eventType.split('.').pop()?.replace(/_/g, ' ') || 'Event'
      description = JSON.stringify(data).slice(0, 50)
  }
  
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
    timestamp,
    category,
    eventType,
    title,
    description,
    coin,
    details: data,
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// TRADING STATE STORE
// ═══════════════════════════════════════════════════════════════════════════════

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
  
  // Activity Log
  activityLog: ActivityEntry[]
  
  // Actions
  setPortfolio: (portfolio: any) => void
  setPositions: (positions: any[]) => void
  setSignals: (signals: Record<string, any>) => void
  addTrade: (trade: any) => void
  addRiskEvent: (event: any) => void
  setConnected: (connected: boolean) => void
  updateFromEvent: (event: any) => void
  addActivity: (entry: ActivityEntry) => void
  clearActivityLog: () => void
}

export const useTradingStore = create<TradingState>((set, get) => ({
  portfolio: null,
  positions: [],
  signals: {},
  trades: [],
  riskEvents: [],
  isConnected: false,
  lastUpdate: null,
  activityLog: [],

  setPortfolio: (portfolio) => set({ portfolio, lastUpdate: new Date().toISOString() }),
  setPositions: (positions) => set({ positions }),
  setSignals: (signals) => set({ signals }),
  addTrade: (trade) => set(state => ({ trades: [trade, ...state.trades].slice(0, 100) })),
  addRiskEvent: (event) => set(state => ({ riskEvents: [event, ...state.riskEvents].slice(0, 50) })),
  setConnected: (isConnected) => set({ isConnected }),
  
  // Activity Log actions
  addActivity: (entry) => set(state => ({
    activityLog: [entry, ...state.activityLog].slice(0, 200)
  })),
  clearActivityLog: () => set({ activityLog: [] }),
  
  updateFromEvent: (event) => {
    const eventType = event.event_type || event.type
    
    // Add to activity log
    const activityEntry = formatActivityEntry(event)
    if (activityEntry) {
      set(state => ({
        activityLog: [activityEntry, ...state.activityLog].slice(0, 200)
      }))
    }
    
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
