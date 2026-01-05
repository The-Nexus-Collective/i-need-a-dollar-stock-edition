'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, CheckCircle, XCircle, ChevronDown, ChevronUp, Brain } from 'lucide-react';
import { clsx } from 'clsx';

interface PreMortemData {
  positionId: string;
  symbol: string;
  direction: string;
  entryPrice: number;
  currentPrice: number;
  currentPnlPercent: number;
  holdHours: number;
  preMortem: string | null;
  bullCase: string | null;
  bearCase: string | null;
  expectedHoldHoursMin: number | null;
  expectedHoldHoursMax: number | null;
  status: 'OK' | 'WARNING' | 'TRIGGERED';
  signals: string[];
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081';

/**
 * A badge component that shows the Pre-Mortem status for a position.
 * Can be used inline in position cards/rows.
 */
export function PreMortemBadge({ positionId }: { positionId: string }) {
  const [data, setData] = useState<PreMortemData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPreMortemStatus();
    const interval = setInterval(fetchPreMortemStatus, 30000); // Update every 30s
    return () => clearInterval(interval);
  }, [positionId]);

  const fetchPreMortemStatus = async () => {
    try {
      const response = await fetch(`${API_URL}/api/learning/positions/${positionId}/premortem-status`);
      if (response.ok) {
        const data = await response.json();
        setData(data);
      }
    } catch (err) {
      // Silently fail - Pre-Mortem is optional
    } finally {
      setLoading(false);
    }
  };

  if (loading || !data || !data.preMortem) {
    return null;
  }

  const statusConfig = {
    OK: {
      icon: CheckCircle,
      color: 'text-accent-emerald',
      bg: 'bg-accent-emerald/10',
      label: 'OK',
    },
    WARNING: {
      icon: AlertTriangle,
      color: 'text-accent-amber',
      bg: 'bg-accent-amber/10',
      label: 'Warnung',
    },
    TRIGGERED: {
      icon: XCircle,
      color: 'text-accent-red',
      bg: 'bg-accent-red/10',
      label: 'Ausgelöst',
    },
  }[data.status];

  const Icon = statusConfig.icon;

  return (
    <span className={clsx(
      'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium',
      statusConfig.bg,
      statusConfig.color
    )}>
      <Icon className="w-3 h-3" />
      {statusConfig.label}
    </span>
  );
}

/**
 * An expandable component that shows full Pre-Mortem details.
 * Shows Pre-Mortem, Bull/Bear cases, expected hold time, and current status signals.
 */
export function PreMortemDetails({ positionId }: { positionId: string }) {
  const [data, setData] = useState<PreMortemData | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    fetchPreMortemStatus();
    const interval = setInterval(fetchPreMortemStatus, 30000);
    return () => clearInterval(interval);
  }, [positionId]);

  const fetchPreMortemStatus = async () => {
    try {
      const response = await fetch(`${API_URL}/api/learning/positions/${positionId}/premortem-status`);
      if (response.ok) {
        const data = await response.json();
        setData(data);
      }
    } catch (err) {
      // Silently fail
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="animate-pulse h-8 bg-glass-bg rounded" />
    );
  }

  if (!data || !data.preMortem) {
    return (
      <div className="text-xs text-text-dim italic">
        Kein Pre-Mortem vorhanden
      </div>
    );
  }

  const statusConfig = {
    OK: {
      icon: CheckCircle,
      color: 'text-accent-emerald',
      bgColor: 'bg-accent-emerald/10',
      borderColor: 'border-accent-emerald/30',
      label: 'Pre-Mortem nicht eingetreten',
    },
    WARNING: {
      icon: AlertTriangle,
      color: 'text-accent-amber',
      bgColor: 'bg-accent-amber/10',
      borderColor: 'border-accent-amber/30',
      label: 'Pre-Mortem könnte eintreten',
    },
    TRIGGERED: {
      icon: XCircle,
      color: 'text-accent-red',
      bgColor: 'bg-accent-red/10',
      borderColor: 'border-accent-red/30',
      label: 'Pre-Mortem scheint einzutreten!',
    },
  }[data.status];

  const Icon = statusConfig.icon;

  return (
    <div className="border-t border-glass-border pt-3 mt-3">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between text-left"
      >
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-purple-400" />
          <span className="text-xs text-text-muted">Pre-Mortem</span>
          <span className={clsx(
            'px-2 py-0.5 rounded text-xs font-medium',
            statusConfig.bgColor,
            statusConfig.color
          )}>
            <Icon className="w-3 h-3 inline mr-1" />
            {data.status}
          </span>
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-text-muted" />
        ) : (
          <ChevronDown className="w-4 h-4 text-text-muted" />
        )}
      </button>

      {/* Content */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="pt-3 space-y-3">
              {/* Status */}
              <div className={clsx(
                'p-2 rounded flex items-center gap-2',
                statusConfig.bgColor,
                'border',
                statusConfig.borderColor
              )}>
                <Icon className={clsx('w-4 h-4', statusConfig.color)} />
                <span className={clsx('text-sm', statusConfig.color)}>
                  {statusConfig.label}
                </span>
              </div>

              {/* Signals */}
              {data.signals.length > 0 && (
                <div className="bg-void/30 rounded p-2">
                  <p className="text-xs text-text-dim mb-1">Signale:</p>
                  <ul className="text-xs text-text-secondary space-y-1">
                    {data.signals.map((signal, i) => (
                      <li key={i}>• {signal}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Pre-Mortem */}
              <div className="bg-void/30 rounded p-2">
                <p className="text-xs text-text-dim mb-1">Pre-Mortem:</p>
                <p className="text-sm italic text-text-secondary">"{data.preMortem}"</p>
              </div>

              {/* Bull/Bear Case */}
              <div className="grid grid-cols-2 gap-2">
                {data.bullCase && (
                  <div className="bg-accent-emerald/5 border border-accent-emerald/20 rounded p-2">
                    <p className="text-xs text-accent-emerald mb-1">Bull Case:</p>
                    <p className="text-xs text-text-secondary">{data.bullCase}</p>
                  </div>
                )}
                {data.bearCase && (
                  <div className="bg-accent-red/5 border border-accent-red/20 rounded p-2">
                    <p className="text-xs text-accent-red mb-1">Bear Case:</p>
                    <p className="text-xs text-text-secondary">{data.bearCase}</p>
                  </div>
                )}
              </div>

              {/* Expected Hold Time */}
              {(data.expectedHoldHoursMin || data.expectedHoldHoursMax) && (
                <div className="text-xs text-text-muted">
                  Erwartete Haltezeit: {' '}
                  {data.expectedHoldHoursMin && data.expectedHoldHoursMax
                    ? `${data.expectedHoldHoursMin}-${data.expectedHoldHoursMax}h`
                    : data.expectedHoldHoursMin
                    ? `min ${data.expectedHoldHoursMin}h`
                    : `max ${data.expectedHoldHoursMax}h`}
                  {' | '}
                  Aktuell: {data.holdHours}h
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/**
 * A summary card showing Pre-Mortem status for all open positions.
 */
export function PreMortemSummary() {
  const [positions, setPositions] = useState<PreMortemData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAllPreMortemStatus();
    const interval = setInterval(fetchAllPreMortemStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchAllPreMortemStatus = async () => {
    try {
      const response = await fetch(`${API_URL}/api/learning/positions/premortem-status`);
      if (response.ok) {
        const data = await response.json();
        setPositions(data);
      }
    } catch (err) {
      // Silently fail
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="glass-card p-4 animate-pulse">
        <div className="h-6 bg-glass-bg rounded w-1/3 mb-2" />
        <div className="h-4 bg-glass-bg rounded w-1/2" />
      </div>
    );
  }

  const positionsWithPreMortem = positions.filter(p => p.preMortem);
  if (positionsWithPreMortem.length === 0) {
    return null;
  }

  const okCount = positionsWithPreMortem.filter(p => p.status === 'OK').length;
  const warningCount = positionsWithPreMortem.filter(p => p.status === 'WARNING').length;
  const triggeredCount = positionsWithPreMortem.filter(p => p.status === 'TRIGGERED').length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass-card p-4"
    >
      <div className="flex items-center gap-2 mb-3">
        <Brain className="w-4 h-4 text-purple-400" />
        <span className="text-sm font-medium text-text-primary">Pre-Mortem Status</span>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1">
          <CheckCircle className="w-4 h-4 text-accent-emerald" />
          <span className="text-sm font-mono text-accent-emerald">{okCount}</span>
          <span className="text-xs text-text-muted">OK</span>
        </div>
        <div className="flex items-center gap-1">
          <AlertTriangle className="w-4 h-4 text-accent-amber" />
          <span className="text-sm font-mono text-accent-amber">{warningCount}</span>
          <span className="text-xs text-text-muted">Warnung</span>
        </div>
        <div className="flex items-center gap-1">
          <XCircle className="w-4 h-4 text-accent-red" />
          <span className="text-sm font-mono text-accent-red">{triggeredCount}</span>
          <span className="text-xs text-text-muted">Ausgelöst</span>
        </div>
      </div>

      {triggeredCount > 0 && (
        <div className="mt-3 p-2 bg-accent-red/10 border border-accent-red/30 rounded text-xs text-accent-red">
          {triggeredCount} Position{triggeredCount > 1 ? 'en' : ''} mit ausgelöstem Pre-Mortem - Überprüfung empfohlen!
        </div>
      )}
    </motion.div>
  );
}

