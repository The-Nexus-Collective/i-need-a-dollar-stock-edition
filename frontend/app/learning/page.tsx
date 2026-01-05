'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { WisdomList } from '@/components/learning/WisdomList';
import { LearningTimeline } from '@/components/learning/LearningTimeline';
import { LearningStats } from '@/components/learning/LearningStats';
import { Sidebar } from '@/components/Sidebar';
import { MobileHeader } from '@/components/MobileHeader';
import { useWebSocket } from '@/lib/websocket';
import { Brain, Clock, BarChart3 } from 'lucide-react';
import { clsx } from 'clsx';

type TabType = 'wisdom' | 'timeline' | 'stats';

interface TabConfig {
  id: TabType;
  label: string;
  icon: React.ElementType;
}

const tabs: TabConfig[] = [
  { id: 'wisdom', label: 'Akkumulierte Weisheit', icon: Brain },
  { id: 'timeline', label: 'Learning Timeline', icon: Clock },
  { id: 'stats', label: 'Effectiveness', icon: BarChart3 },
];

export default function LearningPage() {
  const [activeTab, setActiveTab] = useState<TabType>('wisdom');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { isConnected } = useWebSocket();

  return (
    <div className="flex min-h-screen bg-void">
      <Sidebar 
        isConnected={isConnected} 
        mobileOpen={mobileMenuOpen}
        onMobileClose={() => setMobileMenuOpen(false)}
      />

      <main className="flex-1 md:ml-[280px] min-w-0">
        <MobileHeader 
          onMenuClick={() => setMobileMenuOpen(true)}
          isConnected={isConnected}
          title="Learning"
        />

        <div className="p-4 md:p-6 lg:p-8 space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500/20 to-indigo-500/20 flex items-center justify-center border border-purple-500/30">
                <Brain className="w-5 h-5 text-purple-400" />
              </div>
              <div>
                <h1 className="text-xl font-semibold text-text-primary">Grok's Learning Dashboard</h1>
                <p className="text-xs text-text-muted">Self-Learning aus vergangenen Trades</p>
              </div>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="flex space-x-1 bg-void/50 p-1 rounded-xl w-fit border border-glass-border">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={clsx(
                    'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200',
                    isActive
                      ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                      : 'text-text-muted hover:text-text-secondary hover:bg-glass-bg'
                  )}
                >
                  <Icon className="w-4 h-4" />
                  <span className="hidden sm:inline">{tab.label}</span>
                </button>
              );
            })}
          </div>

          {/* Tab Content */}
          <AnimatePresence mode="wait">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.2 }}
            >
              {activeTab === 'wisdom' && <WisdomList />}
              {activeTab === 'timeline' && <LearningTimeline />}
              {activeTab === 'stats' && <LearningStats />}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}

