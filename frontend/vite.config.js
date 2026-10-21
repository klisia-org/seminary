import path from 'path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import frappeui from 'frappe-ui/vite'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
  		frappeui({
			frappeProxy: true,
			lucideIcons: true,
			jinjaBootData: true,
			frappeTypes: {
				input: {},
			},
			buildConfig: {
				indexHtmlPath: '../seminary/www/seminary.html',
				// frappe-ui's buildConfig defaults this to `true`
				// (`frappe-ui/vite/buildConfig.js`), and the maps were served
				// to **anonymous** callers: 672 KB carrying 70 original source
				// files with their comments intact, verified on the canary.
				// That is the whole SPA source, including the comments that
				// describe each security control (p010 H14, p005a A02-5).
				sourcemap: false,
			},
		}),
    vue()],
  server: {
    host: '0.0.0.0',
    port: 8080,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
      // PageTabs/useTabParam moved into portal-shell/tabs (ADR 075 applies across the
      // portals, not just within this one), and a bare import inside its dist resolves from
      // *its* directory rather than ours. vue-router especially must be one instance:
      // `useRoute` resolves through provide/inject from this app's router, and a second copy
      // injects nothing. Same reason as the prosemirror pins below.
      'vue-router': path.resolve(__dirname, 'node_modules/vue-router'),
      'frappe-ui': path.resolve(__dirname, 'node_modules/frappe-ui'),
      // Force all prosemirror/tiptap imports (including from frappe-ui source)
      // to resolve to the same module instances
      'prosemirror-commands': path.resolve(__dirname, 'node_modules/prosemirror-commands'),
      'prosemirror-dropcursor': path.resolve(__dirname, 'node_modules/prosemirror-dropcursor'),
      'prosemirror-gapcursor': path.resolve(__dirname, 'node_modules/prosemirror-gapcursor'),
      'prosemirror-history': path.resolve(__dirname, 'node_modules/prosemirror-history'),
      'prosemirror-inputrules': path.resolve(__dirname, 'node_modules/prosemirror-inputrules'),
      'prosemirror-keymap': path.resolve(__dirname, 'node_modules/prosemirror-keymap'),
      'prosemirror-model': path.resolve(__dirname, 'node_modules/prosemirror-model'),
      'prosemirror-schema-list': path.resolve(__dirname, 'node_modules/prosemirror-schema-list'),
      'prosemirror-state': path.resolve(__dirname, 'node_modules/prosemirror-state'),
      'prosemirror-tables': path.resolve(__dirname, 'node_modules/prosemirror-tables'),
      'prosemirror-transform': path.resolve(__dirname, 'node_modules/prosemirror-transform'),
      'prosemirror-view': path.resolve(__dirname, 'node_modules/prosemirror-view'),
      '@tiptap/pm': path.resolve(__dirname, 'node_modules/@tiptap/pm'),
      '@tiptap/core': path.resolve(__dirname, 'node_modules/@tiptap/core'),
      '@tiptap/vue-3': path.resolve(__dirname, 'node_modules/@tiptap/vue-3'),
    },
  },
  build: {
    outDir: `../${path.basename(path.resolve('..'))}/public/frontend`,
    emptyOutDir: true,
    target: 'es2015',
    rollupOptions: {
      output: {
        manualChunks(id) {
          // Heavy, on-demand viewers — only load when an instructor opens
          // that submission type.
          if (id.includes('pdfjs-dist')) {
            return 'pdfjs';
          }
          if (id.includes('node_modules/mammoth')) {
            return 'mammoth';
          }
          // Editor.js + all its plugins are pulled in (statically) by
          // utils/index.js, which 25+ pages import. Put them in their own
          // chunk so they parse in parallel and cache independently of the
          // rest of vendor.
          if (id.includes('node_modules/@editorjs')) {
            return 'editorjs';
          }
          // highlight.js is used only by the CodeBox plugin; markdown-it only
          // by LessonContent; both are big.
          if (id.includes('node_modules/highlight.js')) {
            return 'highlight';
          }
          if (id.match(/node_modules\/markdown-it(\/|$)/)) {
            return 'markdown-it';
          }
          if (id.includes('socket.io-client') || id.includes('engine.io-client')) {
            return 'socketio';
          }
          // Only the competency profile draws a chart. Without this branch
          // echarts lands in `vendor`, which every page loads.
          if (id.includes('node_modules/echarts') || id.includes('node_modules/zrender')) {
            return 'echarts';
          }
          // Keep all frappe-ui modules together in one chunk
          if (id.includes('frappe-ui')) {
            return 'frappe-ui';
          }
          // Keep node_modules separate
          if (id.includes('node_modules')) {
            return 'vendor';
          }
        }
      }
    }
  },
  optimizeDeps: {
    include: ['frappe-ui > feather-icons', 'engine.io-client', 'tailwind.config.js', 'interactjs', 'highlight.js'],
  },
})
