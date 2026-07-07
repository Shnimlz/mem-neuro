/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{svelte,js,ts}'],
  theme: {
    extend: {
      colors: {
        surface: {
          DEFAULT: '#15151f',
          2: '#1c1c29',
          3: '#242435',
        },
        line: {
          subtle: '#2a2a3c',
        },
        ink: {
          primary: '#e7e7ee',
          secondary: '#9797ab',
          tertiary: '#6c6c80',
        },
        accent: {
          indigo: '#6366f1',
          amber: '#f5b942',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        xl2: '1.25rem',
      },
    },
  },
  plugins: [],
}
