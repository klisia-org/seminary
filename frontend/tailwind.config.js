const path = require('path')

module.exports = {
    presets: [
        require(path.resolve(__dirname, 'node_modules/frappe-ui/src/utils/tailwind.config'))
    ],
    content: [
        './index.html',
        './src/**/*.{vue,js,ts,jsx,tsx}',
        './node_modules/frappe-ui/src/**/*.{vue,js,ts,jsx,tsx}',
        '../node_modules/frappe-ui/src/**/*.{vue,js,ts,jsx,tsx}',
        // The shared portal components (portal-shell) carry Tailwind classes too.
        '../portal-shell/src/**/*.vue',
    ],
    theme: {
        extend: {},
    },
    plugins: [],
}