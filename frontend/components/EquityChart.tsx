'use client'

import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown } from 'lucide-react'
import { clsx } from 'clsx'
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'

type TimeRange = '1H' | '24H' | '7D' | '30D' | 'ALL'

interface EquityDataPoint {
  time: number
  value: number
}

interface EquityChartProps {
  data: EquityDataPoint[]
  currentEquity: number
  previousEquity: number
  isLive?: boolean
  onTimeRangeChange?: (range: TimeRange) => void
}

const timeRanges: TimeRange[] = ['1H', '24H', '7D', '30D', 'ALL']


export function EquityChart({ 
  data, 
  currentEquity, 
  previousEquity, 
  isLive = false,
  onTimeRangeChange 
}: EquityChartProps) {
  const [activeRange, setActiveRange] = useState<TimeRange>('24H')
  const [hoveredValue, setHoveredValue] = useState<number | null>(null)

  const pnl = currentEquity - previousEquity
  const pnlPercent = previousEquity > 0 ? (pnl / previousEquity) * 100 : 0
  const isPositive = pnl >= 0

  const displayValue = hoveredValue ?? currentEquity

  // Only use real data from the database
  const chartData = useMemo(() => {
    if (data.length === 0) return []
    
    return data.map(d => ({
      time: new Date(d.time * 1000).toISOString(),
      displayTime: new Date(d.time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      value: d.value
    }))
  }, [data])

  // Calculate stats from chart data
  const stats = useMemo(() => {
    if (chartData.length === 0) return { high: 0, low: 0, avg: 0, count: 0 }
    const values = chartData.map(d => d.value)
    return {
      high: Math.max(...values),
      low: Math.min(...values),
      avg: values.reduce((a, b) => a + b, 0) / values.length,
      count: values.length
    }
  }, [chartData])

  const handleRangeChange = (range: TimeRange) => {
    setActiveRange(range)
    onTimeRangeChange?.(range)
  }

  const gradientId = isPositive ? 'colorPositive' : 'colorNegative'
  const lineColor = isPositive ? '#00ff88' : '#ff4757'
  const fillColor = isPositive ? 'rgba(0, 255, 136, 0.2)' : 'rgba(255, 71, 87, 0.2)'

  return (
    <div className="glass-card p-6">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-label">Portfolio Equity</span>
            {isLive && (
              <span className="badge badge-live flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan animate-pulse" />
                LIVE
              </span>
            )}
          </div>
          
          <motion.div
            key={displayValue}
            initial={{ opacity: 0.8, y: -2 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-baseline gap-3"
          >
            <span className="text-display font-mono text-text-primary">
              ${displayValue.toLocaleString('en-US', { minimumFractionDigits: 2 })}
            </span>
            <div className={clsx(
              'flex items-center gap-1 text-sm font-mono',
              isPositive ? 'text-accent-emerald' : 'text-accent-red'
            )}>
              {isPositive ? (
                <TrendingUp className="w-4 h-4" />
              ) : (
                <TrendingDown className="w-4 h-4" />
              )}
              <span>
                {isPositive ? '+' : ''}{pnl.toLocaleString('en-US', { minimumFractionDigits: 2 })}
              </span>
              <span className="text-text-muted">
                ({pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%)
              </span>
            </div>
          </motion.div>
        </div>

        {/* Time range selector */}
        <div className="flex gap-1 bg-void/50 p-1 rounded-lg">
          {timeRanges.map((range) => (
            <button
              key={range}
              onClick={() => handleRangeChange(range)}
              className={clsx(
                'px-3 py-1.5 text-xs font-medium rounded-md transition-all duration-200',
                activeRange === range
                  ? 'bg-accent-cyan/20 text-accent-cyan border border-accent-cyan/30'
                  : 'text-text-muted hover:text-text-secondary hover:bg-glass-bg'
              )}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div className="h-[300px] w-full">
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
              onMouseMove={(e) => {
                if (e.activePayload?.[0]?.value) {
                  setHoveredValue(e.activePayload[0].value as number)
                }
              }}
              onMouseLeave={() => setHoveredValue(null)}
            >
              <defs>
                <linearGradient id="colorPositive" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00ff88" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#00ff88" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorNegative" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ff4757" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#ff4757" stopOpacity={0} />
                </linearGradient>
              </defs>
              
              <CartesianGrid 
                strokeDasharray="3 3" 
                stroke="rgba(255,255,255,0.03)" 
                vertical={false}
              />
              
              <XAxis
                dataKey="displayTime"
                stroke="#606070"
                fontSize={10}
                tickLine={false}
                axisLine={{ stroke: 'rgba(255,255,255,0.05)' }}
                interval="preserveStartEnd"
                minTickGap={60}
              />
              
              <YAxis
                stroke="#606070"
                fontSize={10}
                tickLine={false}
                axisLine={false}
                tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
                domain={['dataMin - 500', 'dataMax + 500']}
                width={55}
              />
              
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(10, 10, 15, 0.95)',
                  border: '1px solid rgba(0, 212, 255, 0.2)',
                  borderRadius: '8px',
                  padding: '10px 14px',
                  boxShadow: '0 4px 20px rgba(0, 0, 0, 0.5)',
                }}
                labelStyle={{ color: '#606070', fontSize: '10px', marginBottom: '4px' }}
                itemStyle={{ color: lineColor, fontFamily: 'JetBrains Mono', fontWeight: 600 }}
                formatter={(value: number) => [`$${value.toLocaleString('en-US', { minimumFractionDigits: 2 })}`, 'Equity']}
              />
              
              <Line
                type="monotone"
                dataKey="value"
                stroke={lineColor}
                strokeWidth={2}
                dot={false}
                isAnimationActive={true}
                animationDuration={1000}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-center px-8">
            <div className="w-16 h-16 rounded-full bg-void/50 flex items-center justify-center mb-4">
              <TrendingUp className="w-8 h-8 text-text-dim" />
            </div>
            <p className="text-text-muted font-medium mb-1">No equity data available</p>
            <p className="text-text-dim text-xs max-w-xs">
              The chart will show real portfolio snapshots once the bot starts trading.
            </p>
          </div>
        )}
      </div>

      {/* Footer stats */}
      <div className="mt-4 pt-4 border-t border-glass-border grid grid-cols-4 gap-4">
        <div>
          <span className="text-label block mb-1">High</span>
          <span className="text-sm font-mono text-accent-emerald">
            ${stats.high > 0 ? stats.high.toLocaleString('en-US', { maximumFractionDigits: 0 }) : '—'}
          </span>
        </div>
        <div>
          <span className="text-label block mb-1">Low</span>
          <span className="text-sm font-mono text-accent-red">
            ${stats.low > 0 ? stats.low.toLocaleString('en-US', { maximumFractionDigits: 0 }) : '—'}
          </span>
        </div>
        <div>
          <span className="text-label block mb-1">Avg</span>
          <span className="text-sm font-mono text-text-secondary">
            ${stats.avg > 0 ? stats.avg.toLocaleString('en-US', { maximumFractionDigits: 0 }) : '—'}
          </span>
        </div>
        <div>
          <span className="text-label block mb-1">Data Points</span>
          <span className="text-sm font-mono text-text-secondary">
            {stats.count > 0 ? stats.count.toLocaleString() : '0'}
          </span>
        </div>
      </div>
    </div>
  )
}
