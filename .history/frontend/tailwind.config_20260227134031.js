const path = require('path')

module.exports = {
    presets: [
        require(path.resolve(__dirname, 'node_modules/frappe-ui/src/utils/preset'))
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