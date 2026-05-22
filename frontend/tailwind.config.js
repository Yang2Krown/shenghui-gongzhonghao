/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand Colors - Clay 砖红系
        clay: {
          DEFAULT: '#CC785C',
          deep: '#A85A40',
          soft: '#E9B79E',
          tint: '#F5E2D5',
        },
        // Accent Colors
        pine: {
          DEFAULT: '#3F5C52',
          soft: '#C9D4CD',
        },
        sand: {
          DEFAULT: '#C49B5C',
          soft: '#ECDCBF',
        },
        // Neutral Colors
        paper: '#FAF9F5',
        ivory: '#F5F1EB',
        bone: '#EFEAE0',
        line: '#E4DDCE',
        ink: {
          DEFAULT: '#1F1F1E',
          2: '#3A3935',
          3: '#6B6862',
          4: '#9A968D',
        },
        // Semantic Colors
        leaf: '#5C8A5C',
        crimson: '#B85450',
        // Legacy support (can be removed later)
        primary: {
          DEFAULT: '#CC785C',
          hover: '#A85A40',
          light: '#F5E2D5',
        },
        secondary: {
          DEFAULT: '#3F5C52',
          hover: '#2D4A3E',
        },
        success: {
          DEFAULT: '#5C8A5C',
          hover: '#4A7A4A',
        },
        warning: {
          DEFAULT: '#C49B5C',
          hover: '#B08A4B',
        },
        danger: {
          DEFAULT: '#B85450',
          hover: '#A04844',
        },
      },
      fontFamily: {
        serif: ['"Source Han Serif SC"', '"Songti SC"', '"STSong"', '"Noto Serif SC"', 'Georgia', 'serif'],
        sans: ['-apple-system', 'BlinkMacSystemFont', '"PingFang SC"', '"Microsoft YaHei"', '"Hiragino Sans GB"', 'Inter', '"Helvetica Neue"', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"SF Mono"', 'Menlo', 'Consolas', 'monospace'],
      },
      spacing: {
        's1': '4px',
        's2': '8px',
        's3': '12px',
        's4': '16px',
        's5': '24px',
        's6': '32px',
        's7': '48px',
        's8': '64px',
        's9': '96px',
        's10': '128px',
      },
      borderRadius: {
        'r-xs': '4px',
        'r-sm': '6px',
        'r-md': '10px',
        'r-lg': '16px',
        'r-xl': '24px',
        'r-pill': '999px',
      },
      boxShadow: {
        'sh-1': '0 1px 2px rgba(31,31,30,.04), 0 0 0 1px rgba(31,31,30,.04)',
        'sh-2': '0 4px 12px rgba(31,31,30,.06), 0 0 0 1px rgba(31,31,30,.04)',
        'sh-3': '0 12px 32px rgba(31,31,30,.08), 0 0 0 1px rgba(31,31,30,.04)',
        'sh-clay': '0 8px 24px rgba(204,120,92,.18)',
      },
      fontSize: {
        'display': ['56px', { lineHeight: '1.10', fontWeight: '500' }],
        'h1': ['40px', { lineHeight: '1.15', fontWeight: '500' }],
        'h2': ['30px', { lineHeight: '1.20', fontWeight: '500' }],
        'h3': ['22px', { lineHeight: '1.30', fontWeight: '600' }],
        'h4': ['18px', { lineHeight: '1.40', fontWeight: '600' }],
        'body': ['15px', { lineHeight: '1.70', fontWeight: '400' }],
        'small': ['13px', { lineHeight: '1.60', fontWeight: '400' }],
        'caption': ['12px', { lineHeight: '1.50', fontWeight: '500', letterSpacing: '0.04em' }],
      },
    },
  },
  plugins: [],
}