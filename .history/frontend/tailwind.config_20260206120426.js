export default {
  presets: [
    require('frappe-ui')
  ],
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
    './node_modules/frappe-ui/src/**/*.{vue,js,ts,jsx,tsx}',
    '../node_modules/frappe-ui/src/**/*.{vue,js,ts,jsx,t sx}',
    './node_modules/frappe-ui/frappe/**/*.{vue,j s,t s,j sx,t sx}',
    '../node_modules/frappe-ui/frappe/**/*.{vue,j s,t s,j sx,t sx}',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}