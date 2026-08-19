module.exports = {
  presets: [require('frappe-ui/tailwind')],
  content: ['./index.html', './src/**/*.{vue,ts}'],
  theme: {
    extend: {
      colors: {
        ink: 'oklch(24% 0.015 245)',
        paper: 'oklch(98% 0.006 245)',
        line: 'oklch(88% 0.01 245)',
        signal: 'oklch(55% 0.12 185)',
        caution: 'oklch(72% 0.13 75)',
        stop: 'oklch(58% 0.16 25)'
      }
    }
  }
}
