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
        sans: ["'Google Sans Flex'", "'Google Sans'", "'Helvetica Neue'", 'sans-serif'],
      },
      keyframes: {
        'fade-in-down': {
          '0%': { opacity: '0', transform: 'translateY(-10px) scale(0.95)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)' },
        }
      },
      animation: {
        'fade-in-down': 'fade-in-down 0.2s ease-out forwards',
      }
    },
  },
  plugins: [],
}