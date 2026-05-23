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
