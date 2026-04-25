import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'node:path'

export default defineConfig({
  plugins: [vue()],
  build: {
    lib: {
      entry: resolve(__dirname, 'src/index.js'),
      name: 'PortalShell',
      fileName: (format) => `portal-shell.${format === 'es' ? 'js' : 'umd.cjs'}`,
      formats: ['es', 'umd'],
    },
    rollupOptions: {
      external: ['vue'],
      output: {
        globals: { vue: 'Vue' },
        assetFileNames: (asset) =>
          asset.name === 'style.css' ? 'portal-shell.css' : asset.name,
      },
    },
    sourcemap: true,
    emptyOutDir: true,
  },
})
