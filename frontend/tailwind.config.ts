import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    screens: {
      'xs': '480px',
      'sm': '640px',
      'md': '768px',
      'lg': '1024px',
      'xl': '1280px',
      '2xl': '1536px',
    },
    extend: {
      colors: {
        // Background layers
        void: '#050508',
        base: '#0a0a0f',
        elevated: '#0f0f16',
        surface: '#14141d',
        
        // Glass
        glass: {
          bg: 'rgba(14, 14, 20, 0.6)',
          border: 'rgba(255, 255, 255, 0.04)',
          'border-hover': 'rgba(0, 212, 255, 0.2)',
        },
        
        // Accents
        accent: {
          cyan: '#00d4ff',
          'cyan-dim': '#0099cc',
          emerald: '#00ff88',
          'emerald-dim': '#00cc6a',
          red: '#ff4757',
          'red-dim': '#cc3946',
          amber: '#ffbe0b',
          purple: '#8b5cf6',
        },
        
        // Text
        text: {
          primary: '#f0f0f5',
          secondary: '#a0a0b0',
          muted: '#606070',
          dim: '#404050',
        },
      },
      
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      
      fontSize: {
        'display': ['3rem', { lineHeight: '1', letterSpacing: '-0.02em', fontWeight: '700' }],
        'headline': ['2rem', { lineHeight: '1.2', letterSpacing: '-0.01em', fontWeight: '600' }],
        'label': ['0.65rem', { lineHeight: '1', letterSpacing: '0.15em', fontWeight: '500' }],
      },
      
      borderRadius: {
        'xl': '16px',
        '2xl': '20px',
        '3xl': '24px',
      },
      
      boxShadow: {
        'glow-sm': '0 0 10px',
        'glow-md': '0 0 20px',
        'glow-lg': '0 0 40px',
        'glow-xl': '0 0 60px',
        'glow-cyan': '0 0 20px rgba(0, 212, 255, 0.4)',
        'glow-cyan-intense': '0 0 40px rgba(0, 212, 255, 0.5), 0 0 10px rgba(0, 212, 255, 0.8)',
        'glow-emerald': '0 0 20px rgba(0, 255, 136, 0.4)',
        'glow-red': '0 0 20px rgba(255, 71, 87, 0.4)',
        'glow-amber': '0 0 20px rgba(255, 190, 11, 0.4)',
        'inner-glow-cyan': 'inset 0 0 20px rgba(0, 212, 255, 0.05)',
        'card': '0 4px 24px rgba(0, 0, 0, 0.3)',
        'card-hover': '0 8px 40px rgba(0, 0, 0, 0.4), 0 0 40px rgba(0, 212, 255, 0.08)',
      },
      
      backdropBlur: {
        'xs': '2px',
        '3xl': '40px',
      },
      
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'float': 'float 3s ease-in-out infinite',
        'shimmer': 'shimmer 2s infinite',
        'number-tick': 'number-tick 0.3s ease-out',
        'fade-in': 'fadeIn 0.5s ease-out',
        'slide-up': 'slideUp 0.5s ease-out',
        'slide-in-right': 'slideInRight 0.3s ease-out',
        'scale-in': 'scaleIn 0.2s ease-out',
      },
      
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { 
            opacity: '1',
            boxShadow: '0 0 4px currentColor'
          },
          '50%': { 
            opacity: '0.6',
            boxShadow: '0 0 12px currentColor, 0 0 20px currentColor'
          },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-4px)' },
        },
        'shimmer': {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'number-tick': {
          '0%': { transform: 'translateY(0)', opacity: '1' },
          '50%': { transform: 'translateY(-2px)', opacity: '0.8' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        'fadeIn': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'slideUp': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slideInRight': {
          '0%': { opacity: '0', transform: 'translateX(20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'scaleIn': {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
      },
      
      transitionTimingFunction: {
        'bounce-in': 'cubic-bezier(0.68, -0.55, 0.265, 1.55)',
        'smooth': 'cubic-bezier(0.4, 0, 0.2, 1)',
      },
      
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
        '128': '32rem',
      },
    },
  },
  plugins: [],
  darkMode: 'class',
}

export default config
