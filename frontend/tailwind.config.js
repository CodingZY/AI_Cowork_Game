import tailwindcssAnimate from 'tailwindcss-animate'

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // 前端设计文档.md §1.2 — Dark Modern Studio Style
        canvas: '#0F172A', // Slate-900  页面基底
        surface: '#1E293B', // Slate-800  卡片背景
        'surface-2': '#283449', // 提升层 / hover
        line: '#334155', // Slate-700  分隔线 / 边框
        ink: '#F8FAFC', // Slate-50   主文字
        'ink-2': '#94A3B8', // Slate-400  次文字
        'ink-3': '#64748B', // Slate-500  更弱文字
        accent: '#10B981', // Emerald-500 Agent 活跃 / 代码生成
        'accent-2': '#06B6D4', // Cyan-500   素材 pipeline / 流式
        danger: '#EF4444', // Red-500    错误 / 编译报错
        warn: '#F59E0B', // Amber-500  等待用户输入
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(16,185,129,0.35), 0 0 24px -6px rgba(16,185,129,0.45)',
        'glow-cyan': '0 0 0 1px rgba(6,182,212,0.35), 0 0 24px -6px rgba(6,182,212,0.45)',
        card: '0 1px 0 0 rgba(255,255,255,0.03) inset, 0 8px 24px -12px rgba(0,0,0,0.6)',
      },
      keyframes: {
        pulseDot: {
          '0%,100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.45', transform: 'scale(0.82)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        fadeIn: {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        pulseDot: 'pulseDot 1.4s ease-in-out infinite',
        shimmer: 'shimmer 1.6s infinite',
        fadeIn: 'fadeIn 0.18s ease-out',
      },
    },
  },
  plugins: [tailwindcssAnimate],
}
