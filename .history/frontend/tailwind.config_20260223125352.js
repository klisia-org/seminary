module.exports = {
    presets: [
        require('../node_modules/frappe-ui/src/utils/tailwind.config')
    ],
    content: [
        './index.html',
        './src/**/*.{vue,js,ts,jsx,tsx}',
        './node_modules/frappe-ui/src/**/*.{vue,js,ts,jsx,tsx}',
        '../node_modules/frappe-ui/src/**/*.{vue,js,ts,jsx,tsx}',
    ],
    theme: {
        extend: {},
    },
    plugins: [],
}