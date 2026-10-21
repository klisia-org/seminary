<!--
  The one secondary-navigation control (ADR 075).

  Two bindings, both addressable:
    - route-backed  — pass `route` on each tab; active state derives from the
                      current route and there is no local state at all.
    - param-backed  — pass `v-model`; pair it with `useTabParam` so the active
                      tab lives in `?tab=`.

  Why this is not frappe-ui's `Tabs`: that component wraps list *and* panels in
  one `flex flex-1 overflow-hidden` root, so it owns a scroll context. This app
  scrolls in DesktopLayout's `#scrollContainer` and pins page headers with
  `position: sticky` inside it, which a nested scroll context breaks. It also
  models by tab *index*, which cannot round-trip through `?tab=directory`.
  See ADR 075's "Deviation" note.
-->
<template>
	<nav
		class="flex gap-5 overflow-x-auto border-b px-3 sm:px-5"
		role="tablist"
		:aria-label="label || __('Sections')"
	>
		<component
			:is="tab.route ? 'router-link' : 'button'"
			v-for="(tab, i) in tabs"
			:key="tab.key || i"
			:to="tab.route"
			:type="tab.route ? undefined : 'button'"
			role="tab"
			:aria-selected="isActive(tab) ? 'true' : 'false'"
			:tabindex="isActive(tab) ? 0 : -1"
			:ref="(el) => setTabRef(el, i)"
			class="flex items-center gap-1.5 whitespace-nowrap border-b-2 py-2.5 text-base duration-200 ease-in-out"
			:class="isActive(tab)
				? 'border-outline-gray-4 text-ink-gray-9 font-medium'
				: 'border-transparent text-ink-gray-5 hover:text-ink-gray-9'"
			@click="!tab.route && select(tab)"
			@keydown="onKeydown($event, i)"
		>
			{{ tab.label }}
			<!-- A count is part of the label, not decoration: on a worklist it is
			     what preserves the at-a-glance overview the stacked sections gave. -->
			<Badge
				v-if="tab.count !== undefined && tab.count !== null"
				:label="String(tab.count)"
				:theme="tab.count ? 'blue' : 'gray'"
			/>
		</component>
	</nav>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { Badge } from 'frappe-ui'

const props = defineProps({
	// [{ key, label, count?, route? }]
	tabs: { type: Array, required: true },
	modelValue: { type: String, default: '' },
	label: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const route = useRoute()
const tabEls = ref([])
function setTabRef(el, i) {
	tabEls.value[i] = el?.$el || el
}

// A route-backed tab is active when the current path is at or below it, so a
// detail route (/partner/jobs/ABC) still highlights its list tab.
const activeRouteKey = computed(() => {
	const matches = props.tabs
		.filter((t) => t.route && route.path.startsWith(resolvePath(t.route)))
		.sort((a, b) => resolvePath(b.route).length - resolvePath(a.route).length)
	return matches[0]?.key
})

function resolvePath(to) {
	return typeof to === 'string' ? to : to?.path || ''
}

function isActive(tab) {
	if (tab.route) return tab.key === activeRouteKey.value
	return tab.key === props.modelValue
}

function select(tab) {
	if (tab.key !== props.modelValue) emit('update:modelValue', tab.key)
}

// Roving focus, per the WAI-ARIA tabs pattern: arrows move between tabs,
// Home/End jump to the ends. Route-backed tabs are links and activate on Enter
// natively, so we only move focus here.
function onKeydown(ev, i) {
	const keys = { ArrowRight: 1, ArrowLeft: -1 }
	let next
	if (ev.key in keys) next = (i + keys[ev.key] + props.tabs.length) % props.tabs.length
	else if (ev.key === 'Home') next = 0
	else if (ev.key === 'End') next = props.tabs.length - 1
	else return
	ev.preventDefault()
	tabEls.value[next]?.focus()
}
</script>
