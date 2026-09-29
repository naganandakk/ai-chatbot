// tailwind.config.js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class', // Enables dark mode toggles
  theme: {
    extend: {
      fontFamily: {
        // Exact system UI stack match used inside Google's chat applications
        sans: [
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          'Helvetica',
          'Arial',
          'sans-serif'
        ],
        mono: [
          'SFMono-Regular',
          'Consolas',
          '"Liberation Mono"',
          'Menlo',
          'Courier',
          'monospace'
        ],
      },
    },
  },
  plugins: [],
}