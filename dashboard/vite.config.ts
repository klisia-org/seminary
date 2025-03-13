import path from 'path';
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import proxyOptions from './proxyOptions';

// https://vitejs.dev/config/
export default defineConfig({
	plugins: [vue()],
	server: {
		port: 8080,
		host: '0.0.0.0',
		proxy: proxyOptions
	},
	resolve: {
		alias: {
			'@': path.resolve(__dirname, 'src')
		}
	},
	build: {
		outDir: '../seminary/public/dashboard',
		emptyOutDir: true,
		target: 'es2015',
	},
});
