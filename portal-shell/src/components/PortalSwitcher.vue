<template>
	<div class="portal-switcher">
		<button
			ref="triggerEl"
			type="button"
			class="portal-switcher__trigger"
			:aria-expanded="open"
			aria-haspopup="menu"
			@click="toggle"
		>
			<svg class="portal-switcher__icon" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
				<path d="M3 5h4v4H3V5zm0 6h4v4H3v-4zm6-6h4v4H9V5zm0 6h4v4H9v-4zm6-6h4v4h-4V5zm0 6h4v4h-4v-4z" />
			</svg>
			<span>{{ __('Portals') }}</span>
		</button>

		<Teleport to="body">
			<ul
				v-if="open"
				ref="menuEl"
				class="portal-switcher__menu"
				role="menu"
				:style="menuStyle"
			>
				<li v-for="portal in portals" :key="portal.id" role="none">
					<a
						:href="portal.url"
						role="menuitem"
						class="portal-switcher__item"
						:class="{ 'portal-switcher__item--current': isCurrent(portal) }"
						@click="close"
					>
						<span class="portal-switcher__item-label">{{ portal.label }}</span>
						<span v-if="portal.description" class="portal-switcher__item-desc">
							{{ portal.description }}
						</span>
					</a>
				</li>
			</ul>
		</Teleport>
	</div>
</template>

<script setup>
import { ref, reactive, nextTick, onBeforeUnmount } from 'vue'

defineProps({
	portals: { type: Array, required: true },
})

const triggerEl = ref(null)
const menuEl = ref(null)
const open = ref(false)
const menuStyle = reactive({ display: 'none' })
const __ = (s) => s

const MENU_WIDTH = 240
const MENU_HEIGHT = 240
const GAP = 6

function place() {
	const el = triggerEl.value
	if (!el) return
	const r = el.getBoundingClientRect()
	const vw = window.innerWidth
	const vh = window.innerHeight

	// If trigger is in the left half of the viewport, open to the right of it.
	// Otherwise, open below+left-aligned to the trigger's right edge.
	const openRightOfTrigger = r.left + MENU_WIDTH < vw && r.left < vw / 2

	// If trigger is in the bottom half, open upward.
	const openUpward = r.bottom + MENU_HEIGHT > vh

	const style = { position: 'fixed', display: 'block' }

	if (openRightOfTrigger) {
		style.left = `${r.right + GAP}px`
		if (openUpward) {
			style.bottom = `${vh - r.bottom}px`
		} else {
			style.top = `${r.top}px`
		}
	} else {
		style.right = `${vw - r.right}px`
		if (openUpward) {
			style.bottom = `${vh - r.top + GAP}px`
		} else {
			style.top = `${r.bottom + GAP}px`
		}
	}

	Object.assign(menuStyle, { left: '', right: '', top: '', bottom: '' }, style)
}

async function toggle() {
	if (open.value) return close()
	open.value = true
	await nextTick()
	place()
}

function close() {
	open.value = false
}

function isCurrent(portal) {
	if (typeof window === 'undefined') return false
	return window.location.pathname.startsWith(portal.url)
}

function onDocumentClick(ev) {
	if (!open.value) return
	if (triggerEl.value?.contains(ev.target)) return
	if (menuEl.value?.contains(ev.target)) return
	close()
}

function onWindowChange() {
	if (open.value) place()
}

document.addEventListener('click', onDocumentClick)
window.addEventListener('resize', onWindowChange)
window.addEventListener('scroll', onWindowChange, true)
onBeforeUnmount(() => {
	document.removeEventListener('click', onDocumentClick)
	window.removeEventListener('resize', onWindowChange)
	window.removeEventListener('scroll', onWindowChange, true)
})
</script>

<style>
.portal-switcher {
	position: relative;
	display: inline-block;
}

.portal-switcher__trigger {
	display: inline-flex;
	align-items: center;
	gap: 0.4rem;
	background: transparent;
	border: 1px solid transparent;
	border-radius: 6px;
	padding: 0.3rem 0.6rem;
	cursor: pointer;
	color: inherit;
	font: inherit;
}

.portal-switcher__trigger:hover {
	background: rgba(0, 0, 0, 0.04);
	border-color: rgba(0, 0, 0, 0.06);
}

.portal-switcher__icon {
	width: 1rem;
	height: 1rem;
}

.portal-switcher__menu {
	min-width: 14rem;
	max-width: 18rem;
	background: #ffffff;
	color: #1f2937;
	border: 1px solid #e5e7eb;
	border-radius: 8px;
	box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1);
	padding: 0.25rem;
	margin: 0;
	list-style: none;
	z-index: 9999;
	font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
	font-size: 0.875rem;
}

.portal-switcher__item {
	display: block;
	padding: 0.5rem 0.75rem;
	border-radius: 6px;
	color: #1f2937;
	text-decoration: none;
}

.portal-switcher__item:hover {
	background: rgba(0, 0, 0, 0.04);
	color: #1f2937;
}

.portal-switcher__item--current {
	background: rgba(13, 48, 73, 0.08);
	color: var(--portal-brand, #0d3049);
	font-weight: 600;
}

.portal-switcher__item-label {
	display: block;
}

.portal-switcher__item-desc {
	display: block;
	font-size: 0.75rem;
	color: #6b7280;
	margin-top: 0.1rem;
}

[data-theme='dark'] .portal-switcher__menu,
.dark .portal-switcher__menu {
	background: #111827;
	color: #f3f4f6;
	border-color: #1f2937;
	box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

[data-theme='dark'] .portal-switcher__item,
.dark .portal-switcher__item {
	color: #f3f4f6;
}

[data-theme='dark'] .portal-switcher__item:hover,
.dark .portal-switcher__item:hover {
	background: rgba(255, 255, 255, 0.06);
	color: #f3f4f6;
}

[data-theme='dark'] .portal-switcher__trigger:hover,
.dark .portal-switcher__trigger:hover {
	background: rgba(255, 255, 255, 0.06);
	border-color: rgba(255, 255, 255, 0.1);
}
</style>
