/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Gaming color palette
        neon: {
          green: '#22c55e',
          cyan: '#06b6d4',
          yellow: '#fbbf24',
          purple: '#a855f7',
          pink: '#ec4899',
          red: '#ef4444',
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
        gaming: ['Orbitron', 'sans-serif'],
      },
      boxShadow: {
        'neon-green': '0 0 10px #22c55e, 0 0 20px #22c55e40, 0 0 30px #22c55e20',
        'neon-cyan': '0 0 10px #06b6d4, 0 0 20px #06b6d440, 0 0 30px #06b6d420',
        'neon-yellow': '0 0 10px #fbbf24, 0 0 20px #fbbf2440',
        'neon-purple': '0 0 10px #a855f7, 0 0 20px #a855f740',
        'glow': '0 0 20px rgba(34, 197, 94, 0.3)',
        'glow-lg': '0 0 40px rgba(34, 197, 94, 0.4)',
      },
      animation: {
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
        'flicker': 'flicker 3s linear infinite',
        'slide-up': 'slide-up 0.3s ease-out',
        'glow-pulse': 'glow-pulse 2s ease-in-out infinite',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 10px #22c55e, 0 0 20px #22c55e40' },
          '50%': { boxShadow: '0 0 20px #22c55e, 0 0 40px #22c55e60' },
        },
        'flicker': {
          '0%, 100%': { opacity: '1' },
          '92%': { opacity: '1' },
          '93%': { opacity: '0.8' },
          '94%': { opacity: '1' },
          '95%': { opacity: '0.9' },
          '96%': { opacity: '1' },
        },
        'slide-up': {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        'glow-pulse': {
          '0%, 100%': { filter: 'brightness(1)' },
          '50%': { filter: 'brightness(1.2)' },
        },
      },
      backgroundImage: {
        'grid-pattern': 'linear-gradient(rgba(34, 197, 94, 0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(34, 197, 94, 0.03) 1px, transparent 1px)',
        'gradient-radial': 'radial-gradient(ellipse at center, var(--tw-gradient-stops))',
      },
      backgroundSize: {
        'grid': '50px 50px',
      },
    },
  },
  plugins: [],
}
