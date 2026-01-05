const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080'

interface FetchOptions extends RequestInit {
  token?: string
}

// Ledger entry for expandable transaction detail
interface LedgerEntry {
  id: number
  transactionId: string
  timestamp: string
  transactionType: 'OPEN' | 'CLOSE' | 'EXTEND' | 'REDUCE' | 'RESET' | 'FEE' | 'MARGIN_CALL'
  positionId: string | null
  account: 'CASH' | 'POSITIONS' | 'REALIZED_PNL' | 'TRADING_COSTS' | 'STARTING_CAPITAL'
  debit: number
  credit: number
  runningBalance: number | null
  description: string | null
  isDebit: boolean
  accountDisplay: string
  netEffect: number
}

// Transaction DTO from backend
interface Transaction {
  transactionId: string
  timestamp: string
  transactionType: 'OPEN' | 'CLOSE' | 'EXTEND' | 'REDUCE' | 'RESET' | 'MARGIN_CALL'
  transactionTypeDisplay: string
  positionId: string | null
  symbol: string | null
  direction: string | null
  price: number | null
  quantity: number | null
  sizeUsdt: number | null
  leverage: number | null
  conviction: number | null
  reason: string | null
  fee: number
  spread: number
  slippage: number
  totalCosts: number
  grossPnl: number
  netPnl: number
  pnlPercent: number
  positionSizeBefore: number | null
  positionSizeAfter: number | null
  avgEntryBefore: number | null
  avgEntryAfter: number | null
  ledgerEntries: LedgerEntry[] | null
  ledgerEntryCount: number
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
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
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
      symbol: string
      direction: string
      quantity: number
      entry_price: number
      size_usdt: number
      leverage: number
      stop_loss_price: number | null
      take_profit_price: number | null
      status: string
      entry_time: string
      exit_time: string | null
      exit_price: number | null
      realized_pnl: number
      conviction: number
      reasoning: string | null
    }>>(`/api/positions?status=${status}`)
  }

  // Trades (legacy - use getTransactions instead)
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

  // ═══════════════════════════════════════════════════════════════════════════
  // TRANSACTIONS - Unified history from accounting ledger
  // ═══════════════════════════════════════════════════════════════════════════

  // Get transactions for history page
  async getTransactions(limit = 100, transactionType?: string, includeLedger = false) {
    const params = new URLSearchParams({ limit: String(limit) })
    if (transactionType) {
      params.append('type', transactionType)
    }
    if (includeLedger) {
      params.append('include_ledger', 'true')
    }
    return this.fetch<Transaction[]>(`/api/transactions?${params.toString()}`)
  }

  // Get single transaction with full ledger detail
  async getTransactionDetail(transactionId: string) {
    return this.fetch<Transaction>(`/api/transactions/${transactionId}`)
  }

  // Get transactions for a specific position (lifecycle view)
  async getPositionTransactions(positionId: string, includeLedger = false) {
    const params = new URLSearchParams()
    if (includeLedger) {
      params.append('include_ledger', 'true')
    }
    return this.fetch<Transaction[]>(`/api/transactions/position/${positionId}?${params.toString()}`)
  }

  // Get transaction summary statistics
  async getTransactionSummary() {
    return this.fetch<{
      totalTransactions: number
      openCount: number
      closeCount: number
      extendCount: number
      reduceCount: number
      totalFees: number
      totalPnl: number
    }>('/api/transactions/summary')
  }

  // Export transactions to CSV
  async exportTransactions(limit = 0, transactionType?: string) {
    const params = new URLSearchParams({ format: 'csv' })
    if (limit > 0) {
      params.append('limit', String(limit))
    }
    if (transactionType) {
      params.append('type', transactionType)
    }
    const response = await fetch(`${this.baseUrl}/api/transactions/export?${params.toString()}`)
    if (!response.ok) {
      throw new Error(`Export failed: ${response.status}`)
    }
    return response.blob()
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // ACCOUNTING - Account balances and reconciliation
  // ═══════════════════════════════════════════════════════════════════════════

  // Get account balances from accounting ledger
  async getAccountBalances() {
    return this.fetch<{
      cash: number
      positions: number
      realizedPnl: number
      tradingCosts: number
      startingCapital: number
      bookEquity: number
      initialized: boolean
    }>('/api/accounting/balances')
  }

  // Get reconciliation report
  async getReconciliation() {
    return this.fetch<{
      balanced: boolean
      timestamp: string
      totalDebits: number
      totalCredits: number
      imbalance: number
      accountBalances: Record<string, number>
      calculatedEquity: number
      expectedEquity: number
      discrepancies: string[]
      totalEntries: number
      totalTransactions: number
    }>('/api/accounting/reconcile')
  }

  // Get accounting health check
  async getAccountingHealth() {
    return this.fetch<{
      status: 'HEALTHY' | 'UNHEALTHY'
      initialized: boolean
      balanced: boolean
      totalEntries: number
      cash: number
      positions: number
      discrepancies?: string[]
    }>('/api/accounting/health')
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

  async getMarginHealth() {
    return this.fetch<{
      overall_status: 'safe' | 'warning' | 'danger' | 'critical'
      summary: {
        total_positions: number
        positions_safe: number
        positions_warning: number
        positions_danger: number
        total_margin_used: number
        margin_utilization_pct: number
        closest_to_liq_pct: number | null
      }
      positions: Array<{
        coin: string
        side: string
        leverage: number
        entry_price: number
        current_price: number
        liquidation_price: number
        distance_to_liq_pct: number
        price_change_pct: number
        margin_used: number
        status: 'safe' | 'warning' | 'danger' | 'liquidated'
      }>
      error?: string
    }>('/api/risk/margin-health')
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
      volatility_regime: {
        regime: string
        regime_display: string
        threshold: number
        btc_atr_percent: number
      }
    }>('/api/system/status')
  }

  async getVolatilityRegime() {
    return this.fetch<{
      regime: string
      regime_display: string
      threshold: number
      btc_atr_percent: number
      thresholds: {
        high_vol: number
        normal: number
        low_vol: number
      }
    }>('/api/system/regime')
  }

  // Health Check
  async getSystemHealth() {
    return this.fetch<{
      overall: 'healthy' | 'degraded' | 'unhealthy'
      services: Record<string, {
        name: string
        status: 'healthy' | 'unhealthy' | 'unknown'
        error?: string
        latency_ms?: number
        last_check?: string
      }>
      error_count: number
      warning_count: number
      recent_errors: Array<{
        timestamp: string
        level: 'ERROR' | 'WARNING'
        logger: string
        service: string
        message: string
        module: string
        line: number
      }>
      last_check: string
    }>('/api/system/health')
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

  // ═══════════════════════════════════════════════════════════════════════════
  // AGGRESSIVE MODE: VELOCITY METRICS
  // ═══════════════════════════════════════════════════════════════════════════

  async getVelocityMetrics() {
    return this.fetch<{
      trades_last_hour: number
      trades_today: number
      trades_24h: number
      rebalances_today: number
      avg_trades_per_hour: number
      velocity_status: 'ON_TARGET' | 'MODERATE' | 'BELOW_TARGET'
      deployment_percent: number
      positions_count: number
      target_deployment: number
      deployment_status: 'ON_TARGET' | 'MODERATE' | 'LOW'
      force_trade_enabled: boolean
    }>('/api/velocity')
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // STOCK TRADING ENDPOINTS
  // ═══════════════════════════════════════════════════════════════════════════

  async getMarketStatus() {
    return this.fetch<{
      is_open: boolean
      current_time: string
      timezone: string
      time_to_open_seconds: number | null
      time_to_close_seconds: number | null
      should_flatten: boolean
      flatten_reason: string | null
      status_text: string
      next_event: string
    }>('/api/stocks/market-status')
  }

  async getStockRegime() {
    return this.fetch<{
      vix_value: number
      regime: string
      regime_display: string
      score_threshold: number
      should_trade: boolean
      timestamp: string
    }>('/api/stocks/regime')
  }

  async getUnifiedRegime() {
    return this.fetch<{
      crypto: {
        regime: string
        regime_display: string
        threshold: number
        btc_atr_percent: number
      }
      stock: {
        vix_value: number
        regime: string
        regime_display: string
        score_threshold: number
        should_trade: boolean
      }
      timestamp: string
    }>('/api/stocks/unified-regime')
  }

  async getMultiPortfolio() {
    return this.fetch<{
      timestamp: string
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
    }>('/api/stocks/portfolio')
  }

  async getStockHype(symbols: string = 'PLTR,RTX,LMT') {
    return this.fetch<Record<string, {
      symbol: string
      score: number
      tweet_count: number
      total_engagement: number
      avg_engagement: number
      sentiment_score: number
      analyzed_at: string
      top_tweets: Array<{
        id: string
        text: string
        engagement: number
      }>
    }>>(`/api/stocks/hype?symbols=${encodeURIComponent(symbols)}`)
  }

  async getUniverse(status: string = 'approved', limit: number = 100) {
    return this.fetch<Array<{
      coin: string
      name: string
      volume_24h: number
      market_cap: number
      price_usd: number
      price_change_24h: number
      hype_score: number
      sentiment_score: number
      narrative_strength: number
      discovery_source: string
      discovered_at: string | null
    }>>(`/api/universe?status=${status}&limit=${limit}`)
  }

  async getUniverseStats() {
    return this.fetch<{
      approved_count: number
      pending_count: number
      rejected_count: number
      coingecko_count: number
      x_discovery_count: number
      total_volume: number
      avg_hype_score: number
    }>('/api/universe/stats')
  }

  async getStrategies() {
    return this.fetch<Array<{
      strategy: string
      weight: number
      win_rate_24h: number | null
      pnl_24h: number
      trades_24h: number
      affinity: {
        low_vol: number
        normal: number
        high_vol: number
      }
    }>>('/api/strategies')
  }

  async getMemories(params: {
    memory_type?: string
    category?: string
    limit?: number
  } = {}) {
    const searchParams = new URLSearchParams()
    if (params.memory_type) searchParams.set('memory_type', params.memory_type)
    if (params.category) searchParams.set('category', params.category)
    if (params.limit) searchParams.set('limit', params.limit.toString())
    
    return this.fetch<Array<{
      id: string
      title: string
      content: string
      category: string
      memory_type: string
      importance: number
      recall_count: number
      created_at: string
      coins: string[]
    }>>(`/api/memories?${searchParams}`)
  }

  async getXDiscoveries(processed?: boolean, limit: number = 50) {
    const searchParams = new URLSearchParams()
    if (processed !== undefined) searchParams.set('processed', processed.toString())
    searchParams.set('limit', limit.toString())
    
    return this.fetch<Array<{
      id: string
      coin: string
      tweet_id: string
      tweet_text: string
      author: string
      engagement: {
        likes: number
        retweets: number
        score: number
      }
      narrative: string
      sentiment: number | null
      discovered_at: string
      processed: boolean
      added_to_universe: boolean
    }>>(`/api/x/discoveries?${searchParams}`)
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // SIMPLE PREDICTION TRADER ENDPOINTS
  // ═══════════════════════════════════════════════════════════════════════════

  async getTraderStatus() {
    return this.fetch<{
      running: boolean
      cycle_count: number
      executor: {
        capital: number
        starting_capital: number
        total_pnl: number
        total_pnl_pct: number
        open_positions: number
        total_cycles: number
        total_trades: number
        positions: Array<{
          position_id: string
          symbol: string
          direction: string
          entry_price: number
          quantity: number
          size_usdt: number
          leverage: number
          conviction: number
          opened_at: string
        }>
      }
      top_coins_count: number
      cycle_interval_seconds: number
      mode: string
    }>('/api/trader/status')
  }

  async getPredictions(limit: number = 100) {
    return this.fetch<Array<{
      id: string
      cycle_id: string
      cycle_number: number
      coin: string
      direction: string
      conviction: number
      leverage: number
      reason: string
      created_at: string
    }>>(`/api/trader/predictions?limit=${limit}`)
  }

  async getPredictionCycles(limit: number = 50) {
    return this.fetch<Array<{
      id: string
      cycle_number: number
      started_at: string
      completed_at: string | null
      capital_before: number
      capital_after: number
      total_pnl: number
      coins_traded: string[]
      status: string
      prediction_count: number
      avg_conviction: number
    }>>(`/api/trader/cycles?limit=${limit}`)
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // PAPER TRADE RESET
  // ═══════════════════════════════════════════════════════════════════════════

  async resetPaperTrades() {
    return this.fetch<{
      status: string
      message: string
      deleted_counts: Record<string, number>
      total_deleted: number
      initial_capital: number
      timestamp: string
    }>('/api/paper-trades/reset', {
      method: 'DELETE',
    })
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // LEARNING - Self-Learning System
  // ═══════════════════════════════════════════════════════════════════════════

  async getLearningWisdom() {
    return this.fetch<Array<{
      id: string
      type: 'WARNING_SIGNAL' | 'BLIND_SPOT' | 'TIME_LESSON'
      description: string
      occurrences: number
      firstOccurred: string
      lastOccurred: string
      symbolPattern: string | null
      directionPattern: string | null
    }>>('/api/learning/wisdom')
  }

  async getLearningTimeline(limit = 20) {
    return this.fetch<Array<{
      id: string
      positionId: string
      symbol: string
      direction: string
      entryPrice: number
      exitPrice: number
      pnlPercent: number
      holdHours: number
      preMortem: string
      whatHappened: string
      preMortemWasCorrect: boolean
      lessonType: string | null
      lessonLearned: string | null
      reflectedAt: string
    }>>(`/api/learning/timeline?limit=${limit}`)
  }

  async getLearningStats() {
    return this.fetch<{
      totalReflections: number
      correctPreMortems: number
      preMortemAccuracyPercent: number
      winRateBeforeLearning: number
      winRateWithLearning: number
      avgPnlBeforeLearning: number
      avgPnlWithLearning: number
      totalWisdoms: number
      warningSignals: number
      blindSpots: number
      timeLessons: number
      winRateImprovement: number
      avgPnlImprovement: number
      learningEffective: boolean
    }>('/api/learning/stats')
  }

  async getPreMortemStatus() {
    return this.fetch<Array<{
      positionId: string
      symbol: string
      direction: string
      entryPrice: number
      currentPrice: number
      currentPnlPercent: number
      holdHours: number
      preMortem: string | null
      bullCase: string | null
      bearCase: string | null
      expectedHoldHoursMin: number | null
      expectedHoldHoursMax: number | null
      status: 'OK' | 'WARNING' | 'TRIGGERED'
      signals: string[]
    }>>('/api/learning/positions/premortem-status')
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // PORTFOLIO MANAGER
  // ═══════════════════════════════════════════════════════════════════════════

  async triggerCycle() {
    return this.fetch<{
      status: string
      message: string
      cycle_number: number
    }>('/api/portfolio-manager/cycle', { method: 'POST' })
  }

  async getPortfolioManagerStatus() {
    return this.fetch<{
      running: boolean
      phase: string
      cycle_count: number
      cycle_interval_seconds: number
      mode: string
      portfolio: {
        positions: Array<{
          id: string
          symbol: string
          direction: string
          entry_price: number
          current_price: number
          quantity: number
          size_usdt: number
          leverage: number
          conviction: number
          unrealized_pnl: number
          pnl_percent: number         // Backend sends pnl_percent
          liquidation_price: number
          margin_risk_pct: number
          entry_time: string          // Backend sends entry_time
          reasoning: string | null    // Backend sends reasoning
        }>
        statistics: {
          starting_capital: number
          current_capital: number
          total_equity: number
          unrealized_pnl: number
          realized_pnl: number
          total_pnl: number
          open_positions: number
          max_positions: number
          available_slots: number
          total_trades: number
          winning_trades: number
          losing_trades: number
          win_rate: number
          total_fees: number
          total_spread: number
          total_slippage: number
          transactions: {
            total: number
            open: number
            close: number
            extend: number
            reduce: number
          }
          deployment: {
            total_deployed: number
            deployment_ratio: number
            deployment_percent: number
            below_minimum: boolean
            capital_to_deploy: number
          }
        }
      }
      logbook: {
        total_entries: number
        total_cycles: number
        total_tokens_used: number
        total_positions_closed: number
        total_positions_opened: number
        oldest_entry: string
        newest_entry: string
      }
      snapshot_service: {
        running: boolean
        snapshot_count: number
        interval_seconds: number
      }
      db_restored: boolean
    }>('/api/portfolio-manager/status')
  }
}

export const api = new ApiClient(API_URL)

// SWR fetcher
export const fetcher = (url: string) => fetch(`${API_URL}${url}`).then(res => res.json())
