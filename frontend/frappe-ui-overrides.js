// frappe-ui components replaced with a patched copy (decision 102 §9).
//
// A Vite plugin: when frappe-ui's own source imports one of the files below, the copy in
// src/overrides/frappe-ui is used instead. Another portal on the same frappe-ui release
// can use the same copies by importing this file from its vite.config.js:
//
//   import { frappeUiOverrides, OVERRIDES_DIR } from '<path to seminary>/frontend/frappe-ui-overrides.js'
//   plugins: [frappeUiOverrides(), frappeui(...), vue()]
//
// and adding OVERRIDES_DIR to its Tailwind `content`. The copies' own imports (vue,
// vue-router, frappe-ui) resolve from the building app's root, never from this folder, so
// the build uses that app's packages, and works whether or not this frontend has its own
// node_modules installed.
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
export const OVERRIDES_DIR = path.join(HERE, 'src', 'overrides', 'frappe-ui')

// The file under frappe-ui/src -> its copy in OVERRIDES_DIR.
const OVERRIDES = {
  'components/TextEditor/Menu.vue': 'TextEditorMenu.vue',
  'components/Button/Button.vue': 'Button.vue',
  'components/ListView/ListRow.vue': 'ListRow.vue',
  'components/ListView/ListHeader.vue': 'ListHeader.vue',
  'components/TabButtons/TabButtons.vue': 'TabButtons.vue',
  'components/Select/Select.vue': 'Select.vue',
  'components/Combobox/Combobox.vue': 'Combobox.vue',
  'components/Autocomplete/Autocomplete.vue': 'Autocomplete.vue',
  'components/FormControl/FormControl.vue': 'FormControl.vue',
}
const FRAPPE_UI_SRC = '/frappe-ui/src/'

const isBare = (source) => !/^[./\0]/.test(source) && !source.startsWith('virtual:') && !path.isAbsolute(source)

export function frappeUiOverrides() {
  let root = process.cwd()
  return {
    name: 'seminary-frappe-ui-overrides',
    enforce: 'pre',
    configResolved(config) {
      root = config.root
    },
    async resolveId(source, importer, options) {
      if (!importer) return null
      const from = importer.split('?')[0]
      // A copy's bare imports resolve as if the building app imported them.
      if (from.startsWith(OVERRIDES_DIR + path.sep) && isBare(source)) {
        return this.resolve(source, path.join(root, 'index.html'), { ...options, skipSelf: true })
      }
      if (!source.includes('.vue') || !from.includes(FRAPPE_UI_SRC)) return null
      const resolved = await this.resolve(source, importer, { ...options, skipSelf: true })
      const id = resolved?.id?.split('?')[0]
      if (!id) return null
      const at = id.lastIndexOf(FRAPPE_UI_SRC)
      if (at < 0) return null
      const copy = OVERRIDES[id.slice(at + FRAPPE_UI_SRC.length)]
      return copy ? path.join(OVERRIDES_DIR, copy) : null
    },
  }
}
