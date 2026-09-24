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
      // vue-router must stay external: `useRoute`/`useRouter` resolve through provide/inject
      // from the host app's router, and a second bundled copy injects nothing.
      external: ['vue', 'vue-router', 'frappe-ui'],
      output: {
        globals: { vue: 'Vue', 'vue-router': 'VueRouter', 'frappe-ui': 'FrappeUI' },
        assetFileNames: (asset) =>
          asset.name === 'style.css' ? 'portal-shell.css' : asset.name,
      },
    },
    sourcemap: false,  // see frontend/vite.config.js (p010 H14)
    emptyOutDir: true,
  },
})
