import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'node:path'

export default defineConfig({
  plugins: [vue()],
  build: {
    lib: {
      // Two entries so the main one needs only vue; see src/tabs.js. ES only: a UMD build
      // cannot have more than one entry, and every consumer is a Vite SPA importing ESM.
      entry: {
        'portal-shell': resolve(__dirname, 'src/index.js'),
        tabs: resolve(__dirname, 'src/tabs.js'),
      },
      formats: ['es'],
    },
    rollupOptions: {
      // vue-router must stay external: `useRoute`/`useRouter` resolve through provide/inject
      // from the host app's router, and a second bundled copy injects nothing.
      external: ['vue', 'vue-router', 'frappe-ui'],
      output: {
        assetFileNames: (asset) =>
          asset.name === 'style.css' ? 'portal-shell.css' : asset.name,
      },
    },
    sourcemap: false,  // see frontend/vite.config.js (p010 H14)
    emptyOutDir: true,
  },
})
