<template>
	<div class="portal-user-menu">
		<button
			type="button"
			class="portal-user-menu__trigger"
			:aria-expanded="open"
			aria-haspopup="menu"
			@click="open = !open"
		>
			<span v-if="user.image" class="portal-user-menu__avatar">
				<img :src="user.image" :alt="user.full_name" />
			</span>
			<span v-else class="portal-user-menu__avatar portal-user-menu__avatar--initials">
				{{ initials }}
			</span>
		</button>

		<div v-if="open" class="portal-user-menu__panel" role="menu">
			<div class="portal-user-menu__identity">
				<div class="portal-user-menu__name">{{ user.full_name }}</div>
				<div class="portal-user-menu__email">{{ user.email }}</div>
			</div>
			<button
				type="button"
				class="portal-user-menu__action"
				role="menuitem"
				@click="handleSignOut"
			>
				{{ __('Sign out') }}
			</button>
		</div>
	</div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'

const props = defineProps({
	user: { type: Object, required: true },
	onSignOut: { type: Function, required: true },
})

const open = ref(false)
const __ = (s) => s

const initials = computed(() => {
	return (props.user.full_name || props.user.email || '?')
		.split(/\s+/)
		.filter(Boolean)
		.slice(0, 2)
		.map((p) => p[0].toUpperCase())
		.join('') || '?'
})

const handleSignOut = async () => {
	open.value = false
	await props.onSignOut()
}

const close = (e) => {
	if (!e.target.closest('.portal-user-menu')) open.value = false
}
document.addEventListener('click', close)
onBeforeUnmount(() => document.removeEventListener('click', close))
</script>

<style>
.portal-user-menu {
	position: relative;
	display: inline-block;
}

.portal-user-menu__trigger {
	background: transparent;
	border: none;
	padding: 0;
	cursor: pointer;
	border-radius: 9999px;
	display: inline-flex;
}

.portal-user-menu__trigger:hover {
	outline: 2px solid rgba(0, 0, 0, 0.06);
}

.portal-user-menu__avatar {
	display: inline-grid;
	place-items: center;
	width: 2rem;
	height: 2rem;
	border-radius: 9999px;
	overflow: hidden;
	background: rgba(0, 0, 0, 0.06);
}

.portal-user-menu__avatar img {
	width: 100%;
	height: 100%;
	object-fit: cover;
}

.portal-user-menu__avatar--initials {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--portal-brand, #0d3049);
}

.portal-user-menu__panel {
	position: absolute;
	right: 0;
	top: calc(100% + 6px);
	min-width: 12rem;
	background: #ffffff;
	border: 1px solid #e5e7eb;
	border-radius: 8px;
	box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
	overflow: hidden;
	z-index: 50;
}

.portal-user-menu__identity {
	padding: 0.75rem;
	border-bottom: 1px solid #e5e7eb;
}

.portal-user-menu__name {
	font-weight: 600;
	font-size: 0.875rem;
	color: #1f2937;
}

.portal-user-menu__email {
	font-size: 0.75rem;
	color: #6b7280;
	margin-top: 0.1rem;
	word-break: break-all;
}

.portal-user-menu__action {
	display: block;
	width: 100%;
	text-align: left;
	padding: 0.6rem 0.75rem;
	background: transparent;
	border: none;
	cursor: pointer;
	color: #1f2937;
	font: inherit;
	font-size: 0.875rem;
}

.portal-user-menu__action:hover {
	background: rgba(0, 0, 0, 0.04);
}

[data-theme='dark'] .portal-user-menu__panel,
.dark .portal-user-menu__panel {
	background: #111827;
	border-color: #1f2937;
	box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

[data-theme='dark'] .portal-user-menu__identity,
.dark .portal-user-menu__identity {
	border-bottom-color: #1f2937;
}

[data-theme='dark'] .portal-user-menu__name,
.dark .portal-user-menu__name,
[data-theme='dark'] .portal-user-menu__action,
.dark .portal-user-menu__action {
	color: #f3f4f6;
}

[data-theme='dark'] .portal-user-menu__email,
.dark .portal-user-menu__email {
	color: #9ca3af;
}

[data-theme='dark'] .portal-user-menu__action:hover,
.dark .portal-user-menu__action:hover {
	background: rgba(255, 255, 255, 0.06);
}
</style>
