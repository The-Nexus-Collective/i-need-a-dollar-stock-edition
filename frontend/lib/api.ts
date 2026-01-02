const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface FetchOptions extends RequestInit {
  token?: string
}

class ApiClient {
  private baseUrl: string
  private token: string | null = null

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  setToken(token: string) {
    this.token = token
  }

  clearToken() {
    this.token = null
  }

  private async fetch<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    }

    if (this.token || options.token) {
      headers['Authorization'] = `Bearer ${options.token || this.token}`
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers,
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
      throw new Error(error.detail || `HTTP ${response.status}`)
    }

    return response.json()
  }

  // Health
  async getHealth() {
    return this.fetch<{
      status: string
      timestamp: string
      version: string
      mode: string
    }>('/health')
  }

  // Auth
  async login(username: string, password: string) {
    const response = await this.fetch<{ access_token: string; token_type: string }>('/auth/token', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    this.setToken(response.access_token)
    return response
  }

  // Portfolio
  async getPortfolio() {
    return this.fetch<{
      total_equity: number
      cash: number
      positions_value: number
      unrealized_pnl: number
      realized_pnl: number
      daily_pnl: number
      daily_pnl_percent: number
      open_positions: number
      var_95: number | null
      max_drawdown: number | null
      win_rate: number | null
    }>('/api/portfolio')
  }

  async getPortfolioHistory(limit = 1000) {
    return this.fetch<Array<{
      timestamp: string
      total_equity: number
      cash: number
      positions_value: number
      unrealized_pnl: number
      realized_pnl: number
      daily_pnl: number
      daily_pnl_percent: number
      var_95: number | null
      max_drawdown: number | null
      win_rate: number | null
    }>>(`/api/portfolio/history?limit=${limit}`)
  }

  // Positions
  async getPositions(status = 'open') {
    return this.fetch<Array<{
      id: string
      coin: string
      side: string
      quantity: number
      entry_price: number
      current_price: number
      unrealized_pnl: number
      realized_pnl: number
      stop_loss: number
      take_profit: number
      status: string
      opened_at: string
      closed_at: string | null
    }>>(`/api/positions?status=${status}`)
  }

  // Trades
  async getTrades(limit = 100) {
    return this.fetch<Array<{
      id: string
      coin: string
      side: string
      order_type: string
      quantity: number
      price: number
      fee: number
      status: string
      is_paper: boolean
      executed_at: string
      created_at: string
    }>>(`/api/trades?limit=${limit}`)
  }

  // Signals
  async getSignals(limit = 100) {
    return this.fetch<Array<{
      id: string
      timestamp: string
      coin: string
      sentiment_score: number
      narrative_strength: number
      combined_score: number
      confidence: number
      recommended_action: string
      risk_approved: boolean
      executed: boolean
    }>>(`/api/signals?limit=${limit}`)
  }

  async getLatestSignals() {
    return this.fetch<Record<string, {
      id: string
      timestamp: string
      coin: string
      sentiment_score: number
      narrative_strength: number
      combined_score: number
      confidence: number
      recommended_action: string
    }>>('/api/signals/latest')
  }

  // Risk
  async getRiskEvents(severity?: string, limit = 100) {
    const params = new URLSearchParams()
    if (severity) params.set('severity', severity)
    params.set('limit', limit.toString())
    
    return this.fetch<Array<{
      id: string
      timestamp: string
      event_type: string
      severity: string
      trigger_value: number
      threshold_value: number
      action_taken: string
      details: any
      acknowledged: boolean
    }>>(`/api/risk/events?${params}`)
  }

  async acknowledgeRiskEvent(eventId: string) {
    return this.fetch<{ status: string; event_id: string }>(`/api/risk/acknowledge/${eventId}`, {
      method: 'POST',
    })
  }

  // Audit
  async getAuditLog(params: {
    event_type?: string
    entity_type?: string
    entity_id?: string
    limit?: number
  } = {}) {
    const searchParams = new URLSearchParams()
    if (params.event_type) searchParams.set('event_type', params.event_type)
    if (params.entity_type) searchParams.set('entity_type', params.entity_type)
    if (params.entity_id) searchParams.set('entity_id', params.entity_id)
    if (params.limit) searchParams.set('limit', params.limit.toString())
    
    return this.fetch<Array<{
      id: number
      timestamp: string
      event_type: string
      actor: string
      action: string
      entity_type: string
      entity_id: string
      reasoning: string
      hash: string
    }>>(`/api/audit?${searchParams}`)
  }

  async verifyAuditChain(limit = 1000) {
    return this.fetch<{
      valid: boolean
      checked: number
      errors: Array<{
        id: number
        type: string
        expected_prev?: string
        actual_prev?: string
        stored_hash?: string
        calculated_hash?: string
      }>
    }>(`/api/audit/verify?limit=${limit}`)
  }

  // System
  async getSystemStatus() {
    return this.fetch<{
      mode: string
      status: string
      timestamp: string
      websocket_connections: number
      event_streams: Record<string, any>
    }>('/api/system/status')
  }

  // Trading Decisions
  async getDecisions(limit = 24) {
    return this.fetch<Array<{
      id: string
      timestamp: string
      batch_id: string
      selected_coin: string | null
      selected_score: number | null
      decision: 'long' | 'short' | 'flat' | 'filtered'
      filter_reason: string | null
      position_size: number | null
      entry_price: number | null
      stop_loss: number | null
      take_profit: number | null
      equity_before: number | null
      risk_amount: number | null
      all_scores: Record<string, number> | null
      executed: boolean
    }>>(`/api/decisions?limit=${limit}`)
  }

  async getDecisionStats() {
    return this.fetch<{
      total_decisions: number
      long_decisions: number
      short_decisions: number
      flat_decisions: number
      filtered_decisions: number
      score_filtered: number
      volume_filtered: number
      executed_count: number
    }>('/api/decisions/stats')
  }
}

export const api = new ApiClient(API_URL)

// SWR fetcher
export const fetcher = (url: string) => fetch(`${API_URL}${url}`).then(res => res.json())
