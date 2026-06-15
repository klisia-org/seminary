<template>
	<div class="relative z-20 flex h-full flex-shrink-0 flex-col justify-between border-r border-outline-gray-1 bg-surface-menu-bar text-ink-gray-9 transition-all duration-300 ease-in-out"
		:class="isSidebarCollapsed ? 'w-16' : 'w-64'">
		<div class="flex flex-col overflow-hidden">
			<div class="px-3 pt-6 pb-4">
				<UserDropdown :isCollapsed="isSidebarCollapsed"
					:seminarySettings="!seminarySettings.loading && seminarySettings.data ? seminarySettings.data : {}" />
			</div>
			<div v-if="!isSidebarCollapsed && orgs.length" class="px-4 pb-3">
				<label class="mb-1 block text-xs font-medium uppercase tracking-wide text-ink-gray-5">
					{{ __('Organization') }}
				</label>
				<select
					v-if="hasMultiple"
					:value="activeOrg"
					@change="onSwitchOrg($event.target.value)"
					class="w-full rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm font-medium text-ink-gray-8 focus:border-outline-gray-4 focus:outline-none"
				>
					<option v-for="o in orgs" :key="o.name" :value="o.name">
						{{ o.organization_name }}
					</option>
				</select>
				<div v-else class="truncate text-sm font-semibold text-ink-gray-8">
					{{ activeOrgName }}
				</div>
			</div>
			<nav class="flex flex-col gap-1 overflow-y-auto px-3 pb-6">
				<SidebarLink v-for="link in links" :key="link.to" :label="link.label" :to="link.to"
					:isCollapsed="isSidebarCollapsed" :icon="link.icon" />
			</nav>
		</div>
		<div class="px-3 pb-6 flex flex-col gap-1">
			<div v-if="!isSidebarCollapsed" class="px-1 pb-1">
				<PortalSwitcher :portals="visiblePortals" />
			</div>
			<button
				type="button"
				@click="toggleTheme"
				:title="theme === 'dark' ? __('Switch to light mode') : __('Switch to dark mode')"
				class="group flex w-full min-h-[44px] cursor-pointer items-center rounded-lg text-ink-gray-8 transition-colors duration-200 hover:bg-surface-gray-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
				:class="isSidebarCollapsed ? 'justify-center px-0 py-2' : 'justify-start px-3 py-2'"
			>
				<span class="grid h-5 w-6 flex-shrink-0 place-items-center">
					<Sun v-if="theme === 'dark'" class="h-4.5 w-4.5 text-ink-gray-7" />
					<Moon v-else class="h-4.5 w-4.5 text-ink-gray-7" />
				</span>
				<span
					class="flex-shrink-0 text-base transition-all duration-200"
					:class="isSidebarCollapsed ? 'ml-0 w-0 overflow-hidden opacity-0' : 'ml-3 w-auto opacity-100'"
				>
					{{ theme === 'dark' ? __('Light mode') : __('Dark mode') }}
				</span>
			</button>
			<SidebarLink :label="isSidebarCollapsed ? 'Expand' : 'Collapse'" :isCollapsed="isSidebarCollapsed"
				@click="isSidebarCollapsed = !isSidebarCollapsed">
				<template #icon>
					<span class="grid h-5 w-6 flex-shrink-0 place-items-center">
						<component :is="collapseIcon"
							class="h-4.5 w-4.5 text-ink-gray-7 transition-transform duration-300" />
					</span>
				</template>
			</SidebarLink>
		</div>
	</div>
</template>

<script setup>
import { useStorage } from '@vueuse/core'
import SidebarLink from '@/components/SidebarLink.vue'
import { Building2, Users, Briefcase, ArrowLeftToLine, ArrowRightToLine, Sun, Moon } from 'lucide-vue-next'
import UserDropdown from './UserDropdown.vue'
import { createResource } from 'frappe-ui'
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { usersStore } from '@/stores/user'
import { useTheme } from '@/composables/useTheme'
import { usePartnerOrg } from '@/composables/usePartnerOrg'
import { PortalSwitcher, getPortalConfig } from '@seminary/portal-shell'

const portalConfig = getPortalConfig()
const { userResource } = usersStore()
const { theme, toggleTheme } = useTheme()
const router = useRouter()

const { activeOrg, activeOrgName, orgs, hasMultiple, setActiveOrg, ensureLoaded } = usePartnerOrg()
onMounted(ensureLoaded)

function onSwitchOrg(name) {
	if (!name || name === activeOrg.value) return
	setActiveOrg(name)
	// Reset to a context that's valid for any org so a stale detail view can't
	// linger; list/profile pages re-fetch for the new org.
	router.push({ name: 'PartnerProfile' })
}

const visiblePortals = computed(() => {
	const roles = userResource?.data?.roles || []
	return portalConfig.portals.filter((p) => {
		if (!p.roles || p.roles.length === 0) return true
		return p.roles.some((r) => roles.includes(r))
	})
})

const links = computed(() => [
	{ label: __('Our Profile'), to: '/partner/profile', icon: Building2 },
	{ label: __('Our People'), to: '/partner/people', icon: Users },
	{ label: __('Job Postings'), to: '/partner/jobs', icon: Briefcase },
])

const isSidebarCollapsed = useStorage('sidebar_is_collapsed', false)
const collapseIcon = computed(() => (isSidebarCollapsed.value ? ArrowRightToLine : ArrowLeftToLine))

const seminarySettings = createResource({
	url: 'seminary.seminary.api.get_school_abbr_logo',
	auto: true,
})
</script>
