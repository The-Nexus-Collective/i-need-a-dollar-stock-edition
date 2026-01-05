'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { AlertTriangle, Search, Clock, Brain } from 'lucide-react';
import { clsx } from 'clsx';

interface TradeWisdom {
  id: string;
  type: 'WARNING_SIGNAL' | 'BLIND_SPOT' | 'TIME_LESSON';
  description: string;
  occurrences: number;
  firstOccurred: string;
  lastOccurred: string;
  symbolPattern: string | null;
  directionPattern: string | null;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081';

export function WisdomList() {
  const [wisdoms, setWisdoms] = useState<TradeWisdom[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchWisdoms();
  }, []);

  const fetchWisdoms = async () => {
    try {
      const response = await fetch(`${API_URL}/api/learning/wisdom`);
      if (!response.ok) throw new Error('Failed to fetch wisdom');
      const data = await response.json();
      setWisdoms(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  const warnings = wisdoms.filter(w => w.type === 'WARNING_SIGNAL');
  const blindSpots = wisdoms.filter(w => w.type === 'BLIND_SPOT');
  const timeLessons = wisdoms.filter(w => w.type === 'TIME_LESSON');

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

  if (wisdoms.length === 0) {
    return (
      <div className="glass-card p-12 text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-purple-500/10 flex items-center justify-center">
          <Brain className="w-8 h-8 text-purple-400/50" />
        </div>
        <p className="text-text-muted text-lg">Noch keine Learnings akkumuliert</p>
        <p className="text-text-dim text-sm mt-2">
          Learnings werden nach geschlossenen Trades generiert
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Warning Signals */}
      {warnings.length > 0 && (
        <WisdomSection
          title="Warnsignale"
          subtitle="Pre-Mortems die eingetreten sind"
          items={warnings}
          colorScheme="amber"
          icon={AlertTriangle}
        />
      )}

      {/* Blind Spots */}
      {blindSpots.length > 0 && (
        <WisdomSection
          title="Blinde Flecken"
          subtitle="Risiken die übersehen wurden"
          items={blindSpots}
          colorScheme="red"
          icon={Search}
        />
      )}

      {/* Time Lessons */}
      {timeLessons.length > 0 && (
        <WisdomSection
          title="Zeit-Learnings"
          subtitle="Erkenntnisse zu Haltezeiten"
          items={timeLessons}
          colorScheme="cyan"
          icon={Clock}
        />
      )}
    </div>
  );
}

interface WisdomSectionProps {
  title: string;
  subtitle: string;
  items: TradeWisdom[];
  colorScheme: 'amber' | 'red' | 'cyan';
  icon: React.ElementType;
}

function WisdomSection({ title, subtitle, items, colorScheme, icon: Icon }: WisdomSectionProps) {
  const colors = {
    amber: {
      bg: 'bg-accent-amber/5',
      border: 'border-accent-amber/20',
      iconBg: 'bg-accent-amber/20',
      iconColor: 'text-accent-amber',
      bar: 'bg-accent-amber',
      badge: 'bg-accent-amber/20 text-accent-amber',
    },
    red: {
      bg: 'bg-accent-red/5',
      border: 'border-accent-red/20',
      iconBg: 'bg-accent-red/20',
      iconColor: 'text-accent-red',
      bar: 'bg-accent-red',
      badge: 'bg-accent-red/20 text-accent-red',
    },
    cyan: {
      bg: 'bg-accent-cyan/5',
      border: 'border-accent-cyan/20',
      iconBg: 'bg-accent-cyan/20',
      iconColor: 'text-accent-cyan',
      bar: 'bg-accent-cyan',
      badge: 'bg-accent-cyan/20 text-accent-cyan',
    },
  }[colorScheme];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={clsx('rounded-xl border p-5', colors.bg, colors.border)}
    >
      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        <div className={clsx('w-9 h-9 rounded-lg flex items-center justify-center', colors.iconBg)}>
          <Icon className={clsx('w-5 h-5', colors.iconColor)} />
        </div>
        <div>
          <h3 className="text-base font-semibold text-text-primary">{title}</h3>
          <p className="text-xs text-text-muted">{subtitle}</p>
        </div>
        <span className={clsx('ml-auto text-xs font-medium px-2 py-1 rounded', colors.badge)}>
          {items.length} total
        </span>
      </div>

      {/* Items */}
      <div className="space-y-3">
        {items.map((item, idx) => (
          <WisdomItem key={item.id} item={item} index={idx} colorScheme={colorScheme} />
        ))}
      </div>
    </motion.div>
  );
}

interface WisdomItemProps {
  item: TradeWisdom;
  index: number;
  colorScheme: 'amber' | 'red' | 'cyan';
}

function WisdomItem({ item, index, colorScheme }: WisdomItemProps) {
  const barColor = {
    amber: 'bg-accent-amber',
    red: 'bg-accent-red',
    cyan: 'bg-accent-cyan',
  }[colorScheme];

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) return `vor ${diffDays}d`;
    if (diffHours > 0) return `vor ${diffHours}h`;
    return 'gerade eben';
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.05 }}
      className="bg-void/30 rounded-lg p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-sm text-text-primary">
            <span className="text-text-dim mr-2">{index + 1}.</span>
            "{item.description}"
          </p>
          {(item.symbolPattern || item.directionPattern) && (
            <div className="flex gap-2 mt-2">
              {item.symbolPattern && (
                <span className="text-xs px-1.5 py-0.5 rounded bg-glass-bg text-text-muted">
                  {item.symbolPattern}
                </span>
              )}
              {item.directionPattern && (
                <span className="text-xs px-1.5 py-0.5 rounded bg-glass-bg text-text-muted">
                  {item.directionPattern}
                </span>
              )}
            </div>
          )}
        </div>
        <span className="text-xs text-text-dim whitespace-nowrap">
          {item.occurrences}x
        </span>
      </div>

      {/* Occurrence Bar */}
      <div className="mt-3 h-1.5 bg-void rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(item.occurrences * 20, 100)}%` }}
          transition={{ duration: 0.5, delay: index * 0.05 + 0.2 }}
          className={clsx('h-full rounded-full', barColor)}
        />
      </div>

      <p className="text-[10px] text-text-dim mt-2">
        Zuletzt: {formatTimeAgo(item.lastOccurred)}
      </p>
    </motion.div>
  );
}

