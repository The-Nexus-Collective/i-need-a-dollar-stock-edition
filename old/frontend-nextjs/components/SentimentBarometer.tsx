'use client'

import { motion } from 'framer-motion'
import { clsx } from 'clsx'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface SentimentBarometerProps {
  value: number // -100 to +100
  label?: string
  showLabels?: boolean
  size?: 'sm' | 'md' | 'lg'
}

export function SentimentBarometer({ 
  value, 
  label = 'Market Sentiment',
  showLabels = true,
  size = 'md'
}: SentimentBarometerProps) {
  // Clamp value between -100 and 100
  const clampedValue = Math.max(-100, Math.min(100, value))
  
  // Calculate position (0% = -100, 50% = 0, 100% = +100)
  const position = ((clampedValue + 100) / 200) * 100
  
  // Determine sentiment category
  const getSentiment = () => {
    if (clampedValue >= 50) return { label: 'Bullish', color: 'emerald', icon: TrendingUp }
    if (clampedValue >= 15) return { label: 'Slightly Bullish', color: 'emerald', icon: TrendingUp }
    if (clampedValue <= -50) return { label: 'Bearish', color: 'red', icon: TrendingDown }
    if (clampedValue <= -15) return { label: 'Slightly Bearish', color: 'red', icon: TrendingDown }
    return { label: 'Neutral', color: 'amber', icon: Minus }
  }

  const sentiment = getSentiment()
  const Icon = sentiment.icon

  const sizeClasses = {
    sm: { bar: 'h-2', text: 'text-lg', indicator: 'w-3 h-3' },
    md: { bar: 'h-3', text: 'text-2xl', indicator: 'w-4 h-4' },
    lg: { bar: 'h-4', text: 'text-3xl', indicator: 'w-5 h-5' },
  }

  const colorClasses = {
    emerald: {
      glow: 'shadow-glow-emerald',
      text: 'text-accent-emerald text-glow-emerald',
      bg: 'bg-accent-emerald',
    },
    red: {
      glow: 'shadow-glow-red',
      text: 'text-accent-red text-glow-red',
      bg: 'bg-accent-red',
    },
    amber: {
      glow: 'shadow-glow-amber',
      text: 'text-accent-amber',
      bg: 'bg-accent-amber',
    },
  }

  const colors = colorClasses[sentiment.color as keyof typeof colorClasses]

  return (
    <div className="glass-card p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <span className="text-label">{label}</span>
        <div className={clsx(
          'flex items-center gap-2 px-3 py-1 rounded-full',
          `bg-accent-${sentiment.color}/10`,
          `border border-accent-${sentiment.color}/30`
        )}>
          <Icon className={clsx('w-4 h-4', colors.text)} />
          <span className={clsx('text-xs font-medium', colors.text)}>
            {sentiment.label}
          </span>
        </div>
      </div>

      {/* Value display */}
      <div className="flex items-center gap-3 mb-6">
        <motion.span
          key={clampedValue}
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className={clsx(
            'font-mono font-bold',
            sizeClasses[size].text,
            colors.text
          )}
        >
          {clampedValue > 0 ? '+' : ''}{clampedValue.toFixed(0)}
        </motion.span>
        <span className="text-text-muted text-sm">/ 100</span>
      </div>

      {/* Gauge bar */}
      <div className="relative">
        {/* Background gradient bar */}
        <div className={clsx(
          'w-full rounded-full overflow-hidden',
          sizeClasses[size].bar,
          'bg-gradient-to-r from-accent-red via-accent-amber to-accent-emerald opacity-20'
        )} />

        {/* Active portion */}
        <div className={clsx(
          'absolute top-0 left-0 rounded-full overflow-hidden',
          sizeClasses[size].bar,
          'w-full'
        )}>
          <motion.div
            initial={{ width: '50%' }}
            animate={{ width: `${position}%` }}
            transition={{ duration: 0.8, ease: [0.4, 0, 0.2, 1] }}
            className="h-full bg-gradient-to-r from-accent-red via-accent-amber to-accent-emerald"
            style={{
              maskImage: 'linear-gradient(to right, black, black)',
              WebkitMaskImage: 'linear-gradient(to right, black, black)',
            }}
          />
        </div>

        {/* Indicator */}
        <motion.div
          initial={{ left: '50%' }}
          animate={{ left: `${position}%` }}
          transition={{ duration: 0.8, ease: [0.4, 0, 0.2, 1] }}
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2"
        >
          <div className={clsx(
            'rounded-full border-2 border-white',
            sizeClasses[size].indicator,
            colors.bg,
            colors.glow
          )} />
        </motion.div>

        {/* Labels */}
        {showLabels && (
          <div className="flex justify-between mt-2">
            <span className="text-[10px] text-accent-red font-medium">BEARISH</span>
            <span className="text-[10px] text-accent-amber font-medium">NEUTRAL</span>
            <span className="text-[10px] text-accent-emerald font-medium">BULLISH</span>
          </div>
        )}
      </div>

      {/* Scale markers */}
      <div className="flex justify-between mt-1 px-1">
        <span className="text-[9px] text-text-dim font-mono">-100</span>
        <span className="text-[9px] text-text-dim font-mono">-50</span>
        <span className="text-[9px] text-text-dim font-mono">0</span>
        <span className="text-[9px] text-text-dim font-mono">+50</span>
        <span className="text-[9px] text-text-dim font-mono">+100</span>
      </div>
    </div>
  )
}

// Circular gauge variant
export function SentimentGauge({ value, size = 120 }: { value: number; size?: number }) {
  const clampedValue = Math.max(-100, Math.min(100, value))
  const rotation = ((clampedValue + 100) / 200) * 180 - 90 // -90 to +90 degrees

  const getColor = () => {
    if (clampedValue >= 15) return '#00ff88'
    if (clampedValue <= -15) return '#ff4757'
    return '#ffbe0b'
  }

  const strokeWidth = size * 0.08
  const radius = (size - strokeWidth) / 2
  const circumference = Math.PI * radius // Half circle

  return (
    <div className="relative" style={{ width: size, height: size / 2 + 20 }}>
      <svg 
        viewBox={`0 0 ${size} ${size / 2 + 10}`} 
        className="w-full h-full"
      >
        {/* Background arc */}
        <path
          d={`M ${strokeWidth / 2} ${size / 2} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${size / 2}`}
          fill="none"
          stroke="rgba(255,255,255,0.05)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        
        {/* Gradient arc */}
        <defs>
          <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#ff4757" />
            <stop offset="50%" stopColor="#ffbe0b" />
            <stop offset="100%" stopColor="#00ff88" />
          </linearGradient>
        </defs>
        
        <path
          d={`M ${strokeWidth / 2} ${size / 2} A ${radius} ${radius} 0 0 1 ${size - strokeWidth / 2} ${size / 2}`}
          fill="none"
          stroke="url(#gaugeGradient)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          opacity={0.3}
        />
      </svg>

      {/* Needle */}
      <motion.div
        initial={{ rotate: 0 }}
        animate={{ rotate: rotation }}
        transition={{ duration: 0.8, ease: [0.4, 0, 0.2, 1] }}
        className="absolute bottom-[10px] left-1/2 origin-bottom"
        style={{
          width: 4,
          height: radius - 10,
          marginLeft: -2,
          background: `linear-gradient(to top, ${getColor()}, ${getColor()}88)`,
          borderRadius: 2,
          boxShadow: `0 0 10px ${getColor()}`,
        }}
      />

      {/* Center dot */}
      <div 
        className="absolute bottom-[6px] left-1/2 -translate-x-1/2 w-4 h-4 rounded-full bg-surface border-2"
        style={{ borderColor: getColor(), boxShadow: `0 0 15px ${getColor()}` }}
      />

      {/* Value */}
      <div className="absolute bottom-0 left-1/2 -translate-x-1/2 text-center">
        <span className="text-lg font-mono font-bold" style={{ color: getColor() }}>
          {clampedValue > 0 ? '+' : ''}{clampedValue.toFixed(0)}
        </span>
      </div>
    </div>
  )
}

