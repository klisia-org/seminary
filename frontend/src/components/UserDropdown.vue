<template>
	<div class="w-full">
		<!-- A portal theme may lay the logo out wide (p017); compact is the default. -->
		<div v-if="isWide" @click="dropdownOpen = !dropdownOpen"
			class="w-full rounded-xl px-3 pt-3 pb-2 text-ink-gray-9 transition-colors duration-200 ease-in-out cursor-pointer"
			:class="dropdownOpen ? 'bg-surface-white shadow-sm ring-1 ring-outline-gray-1' : 'hover:bg-surface-gray-2'">
			<img :src="activeLogo" :alt="seminarySettings?.name || 'Seminary'"
				class="seminary-logo-wide w-full object-contain object-left" :class="WIDE_HEIGHT[logoSize]" />
			<div class="mt-2 flex items-center gap-2">
				<div class="min-w-0 flex-1">
					<div v-if="logoPlacement === 'Wide with name'" class="truncate text-sm font-semibold leading-snug">
						{{ seminarySettings?.name || 'Seminary' }}
					</div>
					<div class="truncate text-xs text-ink-gray-6 leading-snug">
						{{ userResource?.data?.full_name || '' }}
					</div>
				</div>
				<FeatherIcon name="chevron-down" class="h-4 w-4 flex-shrink-0 text-ink-gray-6" aria-hidden="true" />
			</div>
		</div>
		<div v-else @click="dropdownOpen = !dropdownOpen"
			class="flex w-full items-center rounded-xl text-ink-gray-9 transition-colors duration-200 ease-in-out cursor-pointer"
			:class="[
				ROW_HEIGHT[logoSize],
				dropdownOpen ? 'bg-surface-white shadow-sm ring-1 ring-outline-gray-1' : 'hover:bg-surface-gray-2',
				isCollapsed ? 'justify-center gap-0 px-0' : 'justify-between gap-3 px-3 pr-2'
			]">
			<div
				class="seminary-logo flex flex-shrink-0 items-center justify-center overflow-hidden rounded-xl bg-surface-white shadow-sm"
				:class="TILE[logoSize]">
				<Avatar :image="activeLogo" :size="'lg'" class="object-cover" :class="TILE[logoSize]" />
			</div>
			<div class="transition-all duration-200" :class="isCollapsed ? 'hidden' : 'min-w-0 flex-1 opacity-100'">
				<div class="truncate text-sm font-semibold leading-snug">
					{{ seminarySettings?.name || 'Seminary' }}
				</div>
				<div class="truncate text-xs text-ink-gray-6 leading-snug">
					{{ userResource?.data?.full_name || '' }}
				</div>
			</div>
			<FeatherIcon name="chevron-down" class="h-4 w-4 flex-shrink-0 text-ink-gray-6 transition-opacity duration-200"
				:class="isCollapsed ? 'hidden' : 'ml-auto opacity-100'" aria-hidden="true" />
		</div>
		<div v-if="dropdownOpen" class="mt-2 bg-surface-white shadow-md rounded-md w-full">
			<div v-for="option in userDropdownOptions" :key="option.label" @click="option.onClick"
				class="px-4 py-2 hover:bg-surface-gray-2 cursor-pointer flex items-center gap-2">
				<FeatherIcon :name="option.icon" class="h-4 w-4" />
				<span>{{ option.label }}</span>
			</div>
		</div>
		<ProfileModal v-if="showProfileDialog" v-model="showProfileDialog" />
	</div>
</template>

<script setup>
import { Avatar, FeatherIcon } from 'frappe-ui';
import { sessionStore } from '@/stores/session';
import { usersStore } from '@/stores/user';
import { computed, ref } from 'vue';
import { School } from 'lucide-vue-next';
import ProfileModal from '@/components/ProfileModal.vue';
import { useTheme } from '@/composables/useTheme';

const { logout } = sessionStore();
const { userResource } = usersStore();
const { theme } = useTheme();

const dropdownOpen = ref(false);
const showProfileDialog = ref(false);

const userDropdownOptions = [
	{
		icon: 'user',
		label: __('Profile'),
		onClick: () => (showProfileDialog.value = true),

	},
	{
		icon: 'log-out',
		label: __('Log out'),
		onClick: () => logout.submit(),
	},
];

const props = defineProps({
	isCollapsed: {
		type: Boolean,
		default: false,
	},
	seminarySettings: {
		type: Object,
		default: () => ({ name: 'Seminary', logo: School }),
	},
});

// Set by a portal theme through the page's boot data (p017); absent means compact, medium.
const logoPlacement = window.portal_logo?.placement || 'Compact';
const logoSize = window.portal_logo?.size || 'Medium';
const TILE = { Small: 'h-10 w-10', Medium: 'h-12 w-12', Large: 'h-14 w-14' };
const ROW_HEIGHT = { Small: 'h-14', Medium: 'h-16', Large: 'h-[4.5rem]' };
const WIDE_HEIGHT = { Small: 'max-h-10', Medium: 'max-h-14', Large: 'max-h-[4.5rem]' };

// Wide needs room and an image: a collapsed sidebar or the fallback icon stays compact.
const isWide = computed(
	() => logoPlacement !== 'Compact' && !props.isCollapsed && typeof activeLogo.value === 'string'
);

const activeLogo = computed(() => {
	const s = props.seminarySettings;
	if (!s) return null;
	if (theme.value === 'dark' && s.logo_dark) return s.logo_dark;
	return s.logo;
});
</script>

<style>
html[data-theme='dark'] .seminary-logo img,
html[data-theme='dark'] img.seminary-logo-wide {
	filter: none;
}
</style>
