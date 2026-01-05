'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Target, TrendingUp, AlertTriangle, Search, Clock, Activity, HeartPulse } from 'lucide-react';
import { clsx } from 'clsx';

interface LearningStats {
  totalReflections: number;
  correctPreMortems: number;
  preMortemAccuracyPercent: number;
  winRateBeforeLearning: number;
  winRateWithLearning: number;
  avgPnlBeforeLearning: number;
  avgPnlWithLearning: number;
  totalWisdoms: number;
  warningSignals: number;
  blindSpots: number;
  timeLessons: number;
  winRateImprovement: number;
  avgPnlImprovement: number;
  learningEffective: boolean;
  // Mid-trade stats
  totalMidTradeEvaluations: number;
  midTradeDangerCount: number;
  midTradeWarningCount: number;
  midTradeHealthyCount: number;
  dangerWarningRate: number;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081';

export function LearningStats() {
  const [stats, setStats] = useState<LearningStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_URL}/api/learning/stats`);
      if (!response.ok) throw new Error('Failed to fetch stats');
      const data = await response.json();
      setStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card p-6 text-center text-accent-red">
        <p>{error}</p>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="space-y-6">
      {/* Pre-Mortem Accuracy */}
      <StatCard title="Pre-Mortem Accuracy" icon={Target}>
        <div className="flex items-end justify-between">
          <div>
            <p className="text-4xl font-mono font-bold text-text-primary">
              {stats.preMortemAccuracyPercent.toFixed(0)}%
            </p>
            <p className="text-sm text-text-muted mt-1">
              {stats.correctPreMortems} von {stats.totalReflections} korrekt
            </p>
          </div>
          <ProgressRing percent={stats.preMortemAccuracyPercent} />
        </div>
      </StatCard>

      {/* Learning Impact */}
      <StatCard title="Learning Impact" icon={TrendingUp}>
        <div className="grid grid-cols-2 gap-6">
          {/* Win Rate */}
          <div>
            <p className="text-xs text-text-dim mb-2">Win-Rate</p>
            <div className="flex items-baseline gap-2">
              <span className="text-text-muted text-sm">
                {stats.winRateBeforeLearning.toFixed(0)}%
              </span>
              <span className="text-text-dim">→</span>
              <span className="text-xl font-mono font-bold text-text-primary">
                {stats.winRateWithLearning.toFixed(0)}%
              </span>
              {stats.winRateImprovement > 0 && (
                <span className="text-accent-emerald text-sm font-medium">
                  +{stats.winRateImprovement.toFixed(0)}%
                </span>
              )}
              {stats.winRateImprovement < 0 && (
                <span className="text-accent-red text-sm font-medium">
                  {stats.winRateImprovement.toFixed(0)}%
                </span>
              )}
            </div>
          </div>

          {/* Avg PnL */}
          <div>
            <p className="text-xs text-text-dim mb-2">Avg PnL</p>
            <div className="flex items-baseline gap-2">
              <span className="text-text-muted text-sm">
                {stats.avgPnlBeforeLearning.toFixed(1)}%
              </span>
              <span className="text-text-dim">→</span>
              <span className="text-xl font-mono font-bold text-text-primary">
                {stats.avgPnlWithLearning.toFixed(1)}%
              </span>
              {stats.avgPnlImprovement > 0 && (
                <span className="text-accent-emerald text-sm font-medium">
                  +{stats.avgPnlImprovement.toFixed(1)}%
                </span>
              )}
              {stats.avgPnlImprovement < 0 && (
                <span className="text-accent-red text-sm font-medium">
                  {stats.avgPnlImprovement.toFixed(1)}%
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Effectiveness Banner */}
        {stats.learningEffective && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-4 p-3 bg-accent-emerald/10 border border-accent-emerald/30 rounded-lg"
          >
            <p className="text-sm text-accent-emerald flex items-center gap-2">
              <Activity className="w-4 h-4" />
              Learning funktioniert! 
              {stats.winRateImprovement > 0 && (
                <span>+{stats.winRateImprovement.toFixed(0)}% Win-Rate</span>
              )}
              {stats.avgPnlImprovement > 0 && (
                <span>+{stats.avgPnlImprovement.toFixed(1)}% Avg PnL</span>
              )}
              seit Aktivierung
            </p>
          </motion.div>
        )}

        {!stats.learningEffective && stats.totalReflections > 0 && (
          <div className="mt-4 p-3 bg-accent-amber/10 border border-accent-amber/30 rounded-lg">
            <p className="text-sm text-accent-amber">
              Learning noch nicht effektiv - mehr Daten erforderlich
            </p>
          </div>
        )}
      </StatCard>

      {/* Mid-Trade Health Checks */}
      {stats.totalMidTradeEvaluations > 0 && (
        <StatCard title="Mid-Trade Health Checks" icon={HeartPulse}>
          <div className="space-y-4">
            <div className="flex items-end justify-between">
              <div>
                <p className="text-3xl font-mono font-bold text-text-primary">
                  {stats.totalMidTradeEvaluations}
                </p>
                <p className="text-sm text-text-muted mt-1">
                  Evaluierungen offener Positionen
                </p>
              </div>
              <div className="text-right">
                <p className="text-sm text-text-dim">DANGER/WARNING Rate</p>
                <p className={clsx(
                  "text-xl font-mono font-bold",
                  stats.dangerWarningRate > 30 ? "text-accent-red" : 
                  stats.dangerWarningRate > 15 ? "text-accent-amber" : "text-accent-emerald"
                )}>
                  {stats.dangerWarningRate.toFixed(0)}%
                </p>
              </div>
            </div>
            
            {/* Health status breakdown */}
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-accent-red/10 rounded-lg p-3 text-center">
                <p className="text-xl font-mono font-bold text-accent-red">
                  {stats.midTradeDangerCount}
                </p>
                <p className="text-xs text-text-dim">🔴 DANGER</p>
              </div>
              <div className="bg-accent-amber/10 rounded-lg p-3 text-center">
                <p className="text-xl font-mono font-bold text-accent-amber">
                  {stats.midTradeWarningCount}
                </p>
                <p className="text-xs text-text-dim">🟡 WARNING</p>
              </div>
              <div className="bg-accent-emerald/10 rounded-lg p-3 text-center">
                <p className="text-xl font-mono font-bold text-accent-emerald">
                  {stats.midTradeHealthyCount}
                </p>
                <p className="text-xs text-text-dim">🟢 HEALTHY</p>
              </div>
            </div>

            <p className="text-xs text-text-dim">
              Diese Checks vergleichen offene Positionen mit deinen Pre-Mortem Vorhersagen während sie noch laufen.
            </p>
          </div>
        </StatCard>
      )}

      {/* Wisdom Summary */}
      <StatCard title="Akkumulierte Weisheit" icon={null}>
        <div className="grid grid-cols-3 gap-4 text-center">
          <WisdomCounter 
            value={stats.warningSignals} 
            label="Warnsignale" 
            color="amber"
            icon={AlertTriangle}
          />
          <WisdomCounter 
            value={stats.blindSpots} 
            label="Blinde Flecken" 
            color="red"
            icon={Search}
          />
          <WisdomCounter 
            value={stats.timeLessons} 
            label="Zeit-Learnings" 
            color="cyan"
            icon={Clock}
          />
        </div>
      </StatCard>
    </div>
  );
}

interface StatCardProps {
  title: string;
  icon: React.ElementType | null;
  children: React.ReactNode;
}

function StatCard({ title, icon: Icon, children }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-5"
    >
      <div className="flex items-center gap-2 mb-4">
        {Icon && <Icon className="w-4 h-4 text-purple-400" />}
        <h3 className="text-sm font-medium text-text-muted">{title}</h3>
      </div>
      {children}
    </motion.div>
  );
}

interface WisdomCounterProps {
  value: number;
  label: string;
  color: 'amber' | 'red' | 'cyan';
  icon: React.ElementType;
}

function WisdomCounter({ value, label, color, icon: Icon }: WisdomCounterProps) {
  const colorClass = {
    amber: 'text-accent-amber',
    red: 'text-accent-red',
    cyan: 'text-accent-cyan',
  }[color];

  const bgClass = {
    amber: 'bg-accent-amber/10',
    red: 'bg-accent-red/10',
    cyan: 'bg-accent-cyan/10',
  }[color];

  return (
    <div className={clsx('rounded-lg p-4', bgClass)}>
      <Icon className={clsx('w-5 h-5 mx-auto mb-2', colorClass)} />
      <p className={clsx('text-2xl font-mono font-bold', colorClass)}>
        {value}
      </p>
      <p className="text-xs text-text-dim mt-1">{label}</p>
    </div>
  );
}

interface ProgressRingProps {
  percent: number;
}

function ProgressRing({ percent }: ProgressRingProps) {
  const radius = 30;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percent / 100) * circumference;

  const getColor = (pct: number) => {
    if (pct >= 70) return '#00FF88'; // emerald
    if (pct >= 50) return '#FFAA33'; // amber
    return '#FF4757'; // red
  };

  return (
    <svg width="80" height="80" className="-rotate-90">
      {/* Background circle */}
      <circle
        cx="40"
        cy="40"
        r={radius}
        fill="none"
        stroke="#27272a"
        strokeWidth="6"
      />
      {/* Progress circle */}
      <motion.circle
        cx="40"
        cy="40"
        r={radius}
        fill="none"
        stroke={getColor(percent)}
        strokeWidth="6"
        strokeDasharray={circumference}
        strokeLinecap="round"
        initial={{ strokeDashoffset: circumference }}
        animate={{ strokeDashoffset: offset }}
        transition={{ duration: 1, ease: 'easeOut' }}
      />
    </svg>
  );
}

