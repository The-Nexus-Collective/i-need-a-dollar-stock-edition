'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle, XCircle, Lightbulb, TrendingUp, TrendingDown, Clock } from 'lucide-react';
import { clsx } from 'clsx';

interface ReflectionEntry {
  id: string;
  positionId: string;
  symbol: string;
  direction: string;
  entryPrice: number;
  exitPrice: number;
  pnlPercent: number;
  holdHours: number;
  preMortem: string;
  whatHappened: string;
  preMortemWasCorrect: boolean;
  lessonType: string | null;
  lessonLearned: string | null;
  reflectedAt: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

export function LearningTimeline() {
  const [entries, setEntries] = useState<ReflectionEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTimeline();
  }, []);

  const fetchTimeline = async () => {
    try {
      const response = await fetch(`${API_URL}/api/learning/timeline?limit=20`);
      if (!response.ok) throw new Error('Failed to fetch timeline');
      const data = await response.json();
      setEntries(data);
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

  if (entries.length === 0) {
    return (
      <div className="glass-card p-12 text-center">
        <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-purple-500/10 flex items-center justify-center">
          <Clock className="w-8 h-8 text-purple-400/50" />
        </div>
        <p className="text-text-muted text-lg">Noch keine Reflections</p>
        <p className="text-text-dim text-sm mt-2">
          Reflections werden nach geschlossenen Trades generiert
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {entries.map((entry, idx) => (
        <TimelineEntry key={entry.id} entry={entry} index={idx} />
      ))}
    </div>
  );
}

interface TimelineEntryProps {
  entry: ReflectionEntry;
  index: number;
}

function TimelineEntry({ entry, index }: TimelineEntryProps) {
  const isProfitable = entry.pnlPercent >= 0;
  const hasLesson = entry.lessonLearned != null;

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="glass-card overflow-hidden"
    >
      {/* Header */}
      <div className="p-4 border-b border-glass-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            {/* Direction Badge */}
            <span className={clsx(
              'flex items-center gap-1 px-2 py-1 rounded text-xs font-medium',
              entry.direction === 'LONG'
                ? 'bg-accent-emerald/20 text-accent-emerald'
                : 'bg-accent-red/20 text-accent-red'
            )}>
              {entry.direction === 'LONG' ? (
                <TrendingUp className="w-3 h-3" />
              ) : (
                <TrendingDown className="w-3 h-3" />
              )}
              {entry.direction}
            </span>

            {/* Symbol */}
            <span className="font-medium text-text-primary">{entry.symbol}</span>

            {/* PnL */}
            <span className={clsx(
              'text-sm font-mono font-medium',
              isProfitable ? 'text-accent-emerald' : 'text-accent-red'
            )}>
              {isProfitable ? '+' : ''}{entry.pnlPercent.toFixed(1)}%
            </span>
          </div>

          {/* Timestamp */}
          <span className="text-xs text-text-dim">
            {formatDate(entry.reflectedAt)}
          </span>
        </div>

        {/* Trade Details */}
        <div className="mt-2 text-sm text-text-muted flex items-center gap-2">
          <span>Entry: ${entry.entryPrice.toLocaleString()}</span>
          <span className="text-text-dim">→</span>
          <span>Exit: ${entry.exitPrice.toLocaleString()}</span>
          <span className="text-text-dim">|</span>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {entry.holdHours}h
          </span>
        </div>
      </div>

      {/* Pre-Mortem */}
      <div className="p-4 space-y-3">
        {entry.preMortem && (
          <div className="bg-void/30 rounded-lg p-3">
            <p className="text-xs text-text-dim mb-1">Pre-Mortem:</p>
            <p className="text-sm italic text-text-secondary">"{entry.preMortem}"</p>
          </div>
        )}

        {/* What Happened */}
        {entry.whatHappened && (
          <div className="bg-void/30 rounded-lg p-3">
            <p className="text-xs text-text-dim mb-1">Was passiert ist:</p>
            <p className="text-sm text-text-secondary">{entry.whatHappened}</p>
          </div>
        )}

        {/* Result */}
        <div className={clsx(
          'flex items-center gap-2 p-3 rounded-lg',
          entry.preMortemWasCorrect
            ? 'bg-accent-emerald/10 text-accent-emerald'
            : 'bg-accent-red/10 text-accent-red'
        )}>
          {entry.preMortemWasCorrect ? (
            <CheckCircle className="w-4 h-4" />
          ) : (
            <XCircle className="w-4 h-4" />
          )}
          <span className="text-sm font-medium">
            Pre-Mortem war {entry.preMortemWasCorrect ? 'korrekt' : 'falsch'}
          </span>
        </div>

        {/* Lesson Learned */}
        {hasLesson && (
          <div className="bg-purple-500/10 border border-purple-500/30 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-1">
              <Lightbulb className="w-4 h-4 text-purple-400" />
              <span className="text-xs text-purple-400 font-medium">
                Neues Learning ({entry.lessonType?.replace('_', ' ')})
              </span>
            </div>
            <p className="text-sm text-purple-300">"{entry.lessonLearned}"</p>
          </div>
        )}
      </div>
    </motion.div>
  );
}

