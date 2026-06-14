export default {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: '#1f2937',
        secondary: '#374151',
      }
    }
  },
  plugins: [require('@tailwindcss/typography')]
}
