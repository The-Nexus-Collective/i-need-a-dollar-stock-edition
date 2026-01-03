'use client'

import { useEffect, useRef, useState } from 'react'

/**
 * Live Stream Page - Watch the Swarm Think
 * 
 * Real-time view of agent thoughts and signals.
 * Discord-like chat interface.
 */

interface ThoughtChunk {
  type: 'thought'
  agent_id: string
  agent_name: string
  content: string
  is_final: boolean
  timestamp: string
}

interface SignalMessage {
  type: 'signal'
  id: string
  sender_id: string
  sender_name: string
  signal_type: string
  topic: string
  content: string
  confidence: number
  importance: number
  timestamp: string
}

type StreamMessage = ThoughtChunk | SignalMessage | { type: 'heartbeat' | 'connected'; timestamp: string }

interface AgentInfo {
  emoji: string
  color: string
  gradient: string
}

const AGENT_STYLES: Record<string, AgentInfo> = {
  'scout': { emoji: '🔍', color: '#10b981', gradient: 'from-emerald-500 to-teal-600' },
  'analyst': { emoji: '🔬', color: '#6366f1', gradient: 'from-indigo-500 to-purple-600' },
  'oracle': { emoji: '🔮', color: '#a855f7', gradient: 'from-purple-500 to-pink-600' },
  'tactician': { emoji: '🎯', color: '#f59e0b', gradient: 'from-amber-500 to-orange-600' },
  'operator': { emoji: '⚡', color: '#3b82f6', gradient: 'from-blue-500 to-cyan-600' },
  'sage': { emoji: '🧙', color: '#8b5cf6', gradient: 'from-violet-500 to-purple-600' },
  'grok': { emoji: '🤖', color: '#64748b', gradient: 'from-slate-500 to-gray-600' },
}

interface ChatMessage {
  id: string
  agent_id: string
  agent_name: string
  content: string
  type: 'thought' | 'signal'
  timestamp: Date
  isStreaming: boolean
}

export default function StreamPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [connected, setConnected] = useState(false)
  const [streamingMessages, setStreamingMessages] = useState<Record<string, string>>({})
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  
  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingMessages])
  
  // WebSocket connection
  useEffect(() => {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'
    const ws = new WebSocket(`${wsUrl}/ws/swarm?channel=all`)
    wsRef.current = ws
    
    ws.onopen = () => {
      console.log('Connected to swarm stream')
      setConnected(true)
    }
    
    ws.onclose = () => {
      console.log('Disconnected from swarm stream')
      setConnected(false)
      
      // Reconnect after 3 seconds
      setTimeout(() => {
        if (wsRef.current?.readyState === WebSocket.CLOSED) {
          window.location.reload()
        }
      }, 3000)
    }
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
    
    ws.onmessage = (event) => {
      try {
        const data: StreamMessage = JSON.parse(event.data)
        
        if (data.type === 'thought') {
          handleThought(data as ThoughtChunk)
        } else if (data.type === 'signal') {
          handleSignal(data as SignalMessage)
        }
      } catch (e) {
        console.error('Failed to parse message:', e)
      }
    }
    
    return () => {
      ws.close()
    }
  }, [])
  
  const handleThought = (chunk: ThoughtChunk) => {
    const key = `thought_${chunk.agent_id}`
    
    if (chunk.is_final) {
      // Convert streaming message to final message
      setStreamingMessages(prev => {
        const content = prev[key] || ''
        if (content.trim()) {
          const newMessage: ChatMessage = {
            id: `${Date.now()}_${chunk.agent_id}`,
            agent_id: chunk.agent_id,
            agent_name: chunk.agent_name,
            content: content,
            type: 'thought',
            timestamp: new Date(chunk.timestamp),
            isStreaming: false,
          }
          setMessages(msgs => [...msgs.slice(-100), newMessage])
        }
        
        const { [key]: _, ...rest } = prev
        return rest
      })
    } else {
      // Append to streaming message
      setStreamingMessages(prev => ({
        ...prev,
        [key]: (prev[key] || '') + chunk.content,
      }))
    }
  }
  
  const handleSignal = (signal: SignalMessage) => {
    const newMessage: ChatMessage = {
      id: signal.id,
      agent_id: signal.sender_id,
      agent_name: signal.sender_name,
      content: signal.content,
      type: 'signal',
      timestamp: new Date(signal.timestamp),
      isStreaming: false,
    }
    setMessages(msgs => [...msgs.slice(-100), newMessage])
  }
  
  const getAgentStyle = (agentId: string): AgentInfo => {
    return AGENT_STYLES[agentId.toLowerCase()] || AGENT_STYLES['grok']
  }
  
  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('de-DE', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  }
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <div className="border-b border-slate-700 bg-slate-800/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
                <span className="text-xl">🧠</span>
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">Swarm Mind</h1>
                <p className="text-sm text-slate-400">Live Agent Thoughts</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-4">
              {/* Connection status */}
              <div className={`flex items-center space-x-2 px-3 py-1.5 rounded-full ${
                connected ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
              }`}>
                <div className={`w-2 h-2 rounded-full ${
                  connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'
                }`} />
                <span className="text-sm font-medium">
                  {connected ? 'Live' : 'Disconnected'}
                </span>
              </div>
              
              {/* Agent legend */}
              <div className="hidden md:flex items-center space-x-2 text-sm">
                {Object.entries(AGENT_STYLES).slice(0, 6).map(([id, style]) => (
                  <span key={id} className="text-slate-400">
                    {style.emoji}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
      
      {/* Chat area */}
      <div className="max-w-6xl mx-auto px-6 py-6">
        <div className="bg-slate-800/30 rounded-2xl border border-slate-700/50 backdrop-blur-sm min-h-[calc(100vh-200px)]">
          <div className="p-6 space-y-4">
            {/* Welcome message */}
            {messages.length === 0 && Object.keys(streamingMessages).length === 0 && (
              <div className="text-center py-20">
                <div className="text-6xl mb-4">🧠</div>
                <h2 className="text-2xl font-bold text-white mb-2">Waiting for thoughts...</h2>
                <p className="text-slate-400">
                  The swarm is thinking. Their thoughts will appear here in real-time.
                </p>
              </div>
            )}
            
            {/* Messages */}
            {messages.map((msg) => {
              const style = getAgentStyle(msg.agent_id)
              
              return (
                <div key={msg.id} className="flex items-start space-x-3 group">
                  {/* Avatar */}
                  <div 
                    className={`w-10 h-10 rounded-full bg-gradient-to-br ${style.gradient} flex items-center justify-center flex-shrink-0 shadow-lg`}
                  >
                    <span className="text-lg">{style.emoji}</span>
                  </div>
                  
                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline space-x-2 mb-1">
                      <span className="font-semibold text-white">{msg.agent_name}</span>
                      <span className="text-xs text-slate-500">
                        {formatTime(msg.timestamp)}
                      </span>
                      {msg.type === 'signal' && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400">
                          signal
                        </span>
                      )}
                    </div>
                    <div className="text-slate-300 whitespace-pre-wrap break-words">
                      {msg.content}
                    </div>
                  </div>
                </div>
              )
            })}
            
            {/* Streaming messages */}
            {Object.entries(streamingMessages).map(([key, content]) => {
              const agentId = key.replace('thought_', '')
              const style = getAgentStyle(agentId)
              const agentName = Object.keys(AGENT_STYLES).find(k => k === agentId) || 'Agent'
              
              return (
                <div key={key} className="flex items-start space-x-3 group">
                  {/* Avatar */}
                  <div 
                    className={`w-10 h-10 rounded-full bg-gradient-to-br ${style.gradient} flex items-center justify-center flex-shrink-0 shadow-lg animate-pulse`}
                  >
                    <span className="text-lg">{style.emoji}</span>
                  </div>
                  
                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-baseline space-x-2 mb-1">
                      <span className="font-semibold text-white capitalize">{agentName}</span>
                      <span className="text-xs text-slate-500">now</span>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 animate-pulse">
                        thinking...
                      </span>
                    </div>
                    <div className="text-slate-300 whitespace-pre-wrap break-words">
                      {content}
                      <span className="inline-block w-2 h-4 bg-white/50 animate-pulse ml-0.5" />
                    </div>
                  </div>
                </div>
              )
            })}
            
            {/* Scroll anchor */}
            <div ref={messagesEndRef} />
          </div>
        </div>
      </div>
    </div>
  )
}

