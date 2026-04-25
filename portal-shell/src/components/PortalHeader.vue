<template>
	<header class="portal-header" :style="{ '--portal-brand': config.brand.color }">
		<div class="portal-header__section portal-header__section--left">
			<slot name="brand">
				<a class="portal-header__brand" :href="brandHref">
					<img
						v-if="config.brand.logoUrl"
						:src="config.brand.logoUrl"
						:alt="config.brand.name"
						class="portal-header__logo"
					/>
					<span class="portal-header__brand-name">{{ config.brand.name }}</span>
				</a>
			</slot>
		</div>

		<div class="portal-header__section portal-header__section--center">
			<slot name="title">
				<h1 v-if="title" class="portal-header__title">{{ title }}</h1>
			</slot>
		</div>

		<div class="portal-header__section portal-header__section--right">
			<slot name="actions" />
			<PortalSwitcher v-if="visiblePortals.length > 1" :portals="visiblePortals" />
			<UserMenu v-if="user" :user="user" :on-sign-out="signOut" />
		</div>
	</header>
</template>

<script setup>
import { computed } from 'vue'
import { getPortalConfig } from '../config.js'
import { useSession } from '../composables/useSession.js'
import PortalSwitcher from './PortalSwitcher.vue'
import UserMenu from './UserMenu.vue'

const props = defineProps({
	title: { type: String, default: '' },
	brandHref: { type: String, default: '/' },
})

const config = getPortalConfig()
const { user, signOut } = useSession()

const visiblePortals = computed(() => {
	const userRoles = user.value?.roles || []
	return config.portals.filter((p) => {
		if (!p.roles || p.roles.length === 0) return true
		return p.roles.some((r) => userRoles.includes(r))
	})
})
</script>

<style>
.portal-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 1rem;
	padding: 0.5rem 1rem;
	background: var(--portal-header-bg, #ffffff);
	color: var(--portal-header-fg, #1f2937);
	border-bottom: 1px solid var(--portal-header-border, #e5e7eb);
	min-height: 3.25rem;
	font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
	font-size: 0.875rem;
}

.portal-header__section {
	display: flex;
	align-items: center;
	gap: 0.75rem;
	min-width: 0;
}

.portal-header__section--center {
	flex: 1;
	justify-content: flex-start;
}

.portal-header__brand {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	color: inherit;
	text-decoration: none;
	font-weight: 600;
}

.portal-header__logo {
	height: 1.5rem;
	width: auto;
}

.portal-header__brand-name {
	color: var(--portal-brand);
	font-weight: 700;
}

.portal-header__title {
	font-size: 1rem;
	font-weight: 600;
	margin: 0;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

[data-theme='dark'] .portal-header,
.dark .portal-header {
	background: var(--portal-header-bg-dark, #111827);
	color: var(--portal-header-fg-dark, #f3f4f6);
	border-bottom-color: var(--portal-header-border-dark, #1f2937);
}
</style>
