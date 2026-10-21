---
title: Website widget test page
sidebar: false
outline: false
---

<script setup>
import { ref, onMounted, nextTick } from 'vue'

const portal = ref('http://potestas.localhost:8006')
const key = ref('')
const slug = ref('')
const mode = ref('light')
const lang = ref('')

const frameHost = ref(null)
const programs = ref(null)
const program = ref(null)
const admissions = ref(null)
const error = ref('')
const raw = ref({})

const SAVED = 'aretenic-widget-test'

onMounted(() => {
  const q = new URLSearchParams(location.search)
  let saved = {}
  try { saved = JSON.parse(localStorage.getItem(SAVED) || '{}') } catch (e) {}
  portal.value = q.get('portal') || saved.portal || portal.value
  key.value = q.get('key') || saved.key || ''
  slug.value = q.get('program') || saved.slug || ''
  mode.value = saved.mode || 'light'
  lang.value = q.get('lang') || saved.lang || ''
  mode.value = q.get('mode') || mode.value
  // ?autorun=1 loads both sections at once.
  if (q.get('autorun') && key.value) nextTick(() => { loadIframes(); loadJson() })
})

function remember() {
  try {
    localStorage.setItem(SAVED, JSON.stringify({
      portal: portal.value, key: key.value, slug: slug.value, mode: mode.value, lang: lang.value,
    }))
  } catch (e) {}
}

async function loadIframes() {
  remember()
  const host = frameHost.value
  host.innerHTML = ''
  const widgets = [['admissions', 'Open admission windows'], ['programs', 'Programs']]
  if (slug.value) widgets.push(['program', 'One program'])
  for (const [widget, label] of widgets) {
    const h = document.createElement('h3')
    h.textContent = label
    const div = document.createElement('div')
    div.className = 'widget-frame'
    div.setAttribute('data-aretenic-widget', widget)
    div.setAttribute('data-key', key.value)
    if (widget === 'program') div.setAttribute('data-program', slug.value)
    if (mode.value !== 'light') div.setAttribute('data-mode', mode.value)
    if (lang.value) div.setAttribute('data-lang', lang.value)
    host.append(h, div)
  }
  // A fresh loader each time, so it mounts the divs above.
  const script = document.createElement('script')
  script.src = `${portal.value}/assets/aretenic/js/embed.js?t=${Date.now()}`
  host.append(script)
}

async function call(method, params = {}) {
  const url = new URL(`${portal.value}/api/method/aretenic.embed.v1.${method}`)
  url.searchParams.set('key', key.value)
  if (lang.value) url.searchParams.set('_lang', lang.value)
  for (const [k, v] of Object.entries(params)) if (v) url.searchParams.set(k, v)
  const res = await fetch(url)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(`${method}: HTTP ${res.status} ${body.exc_type || ''}`)
  return body.message
}

async function loadJson() {
  remember()
  error.value = ''
  programs.value = program.value = admissions.value = null
  try {
    programs.value = await call('programs')
    admissions.value = await call('admissions')
    if (slug.value) program.value = await call('program', { slug: slug.value })
    raw.value = { programs: programs.value, admissions: admissions.value, program: program.value }
  } catch (e) {
    // A blocked CORS request surfaces as a TypeError with no status.
    error.value = e instanceof TypeError
      ? `${e.message}: the browser blocked the response. Is ${location.origin} in Allowed Websites?`
      : e.message
  }
}
</script>

# Website widget test page

A local harness for aretenic's website widgets: this page plays the school's own website. It is
served by `yarn dev` (or a `DOCS_DEV_PAGES=1 yarn build`) and is never part of the published docs.

Add `?autorun=1` (and `key=`, `program=`, `mode=`, `lang=`, `portal=`) to the address to load
everything at once.

**Before you start:** the bench is running, Website Widgets is on in Website Branding, and
**Allowed Websites** includes this page's origin (`http://localhost:5173` by default). Without it,
the iframes stay blank and the JSON calls are blocked, which is the point of that setting.

<div class="settings">
  <label>Portal <input v-model="portal" placeholder="http://site.localhost:8006"></label>
  <label>Embed key <input v-model="key" placeholder="from Website Branding"></label>
  <label>Program slug <input v-model="slug" placeholder="e.g. demo-master-of-divinity"></label>
  <label>Mode
    <select v-model="mode"><option>light</option><option>dark</option><option>auto</option></select>
  </label>
  <label>Language <input v-model="lang" placeholder="es, pt-BR… (blank: site default)"></label>
</div>

## 1. iframe

The snippet Website Branding shows, built from the settings above.

<button class="run" @click="loadIframes">Load the widgets</button>

<div ref="frameHost" class="frames"></div>

## 2. JSON (`aretenic.embed.v1`)

The same data fetched from this page's origin, rendered by this page.

<button class="run" @click="loadJson">Fetch the JSON</button>

<p v-if="error" class="error">{{ error }}</p>

<template v-if="admissions">

### Open admission windows

<p v-if="!admissions.windows.length"><em>None open.</em></p>
<div v-for="w in admissions.windows" :key="w.id" class="card">
  <strong>{{ w.term }}</strong> · {{ w.status_label }}<br>
  Apply {{ w.apply_from }} → {{ w.apply_until }}
  <ul>
    <li v-for="p in w.programs" :key="p.id">
      <a :href="p.url" target="_blank">{{ p.name }}</a>
      <a v-if="p.apply_url" :href="p.apply_url" target="_blank"> — Apply</a>
    </li>
  </ul>
</div>

</template>

<template v-if="programs">

### {{ programs.label }}

<div v-for="g in programs.groups" :key="g.level">
  <h4>{{ g.level }}</h4>
  <div class="grid">
    <a v-for="p in g.programs" :key="p.id" class="card" :href="p.url" target="_blank">
      <img v-if="p.image" :src="p.image" alt="">
      <strong>{{ p.name }}</strong>
      <span v-if="p.duration">{{ p.duration }} {{ p.duration_unit }}</span>
    </a>
  </div>
</div>

</template>

<template v-if="program">

### {{ program.name }}

<div class="card">
  <div v-if="program.description_html" v-html="program.description_html"></div>
  <p>Enrollment: {{ program.enrollment_mode }}</p>
  <ul>
    <li v-for="w in program.windows" :key="w.id">
      {{ w.term }}: {{ w.apply_window_display }}
      <a v-if="w.apply_url" :href="w.apply_url" target="_blank">Apply</a>
    </li>
  </ul>
  <p v-if="program.continuous_term">
    Apply anytime for {{ program.continuous_term.term }}
    <a :href="program.continuous_term.apply_url" target="_blank">Apply</a>
  </p>
</div>

</template>

<details v-if="Object.keys(raw).length">
  <summary>Raw responses</summary>
  <pre>{{ JSON.stringify(raw, null, 2) }}</pre>
</details>

<style scoped>
.settings { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: .75rem; margin: 1rem 0; }
.settings label { display: flex; flex-direction: column; font-size: .85rem; gap: .25rem; }
.settings input, .settings select { border: 1px solid var(--vp-c-divider); border-radius: 6px; padding: .35rem .5rem; background: var(--vp-c-bg-soft); }
.run { background: var(--vp-c-brand-1); color: var(--vp-c-white); border-radius: 6px; padding: .4rem .9rem; font-weight: 600; }
.frames :deep(.widget-frame) { border: 2px dashed var(--vp-c-divider); margin-bottom: 1rem; }
.error { color: var(--vp-c-danger-1); font-weight: 600; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: .75rem; }
.card { display: flex; flex-direction: column; gap: .25rem; border: 1px solid var(--vp-c-divider); border-radius: 8px; padding: .75rem; margin: .5rem 0; text-decoration: none; }
.card img { width: 100%; aspect-ratio: 3 / 2; object-fit: cover; border-radius: 4px; }
pre { max-height: 400px; overflow: auto; font-size: .75rem; }
</style>
