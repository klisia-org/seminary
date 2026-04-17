<template>
	<div class="w-full">
		<div @click="dropdownOpen = !dropdownOpen"
			class="flex h-16 w-full items-center rounded-xl text-ink-gray-9 transition-colors duration-200 ease-in-out cursor-pointer"
			:class="[
				dropdownOpen ? 'bg-surface-white shadow-sm ring-1 ring-outline-gray-1' : 'hover:bg-surface-gray-2',
				isCollapsed ? 'justify-center gap-0 px-0' : 'justify-between gap-3 px-3 pr-2'
			]">
			<div
				class="seminary-logo flex h-12 w-12 flex-shrink-0 items-center justify-center overflow-hidden rounded-xl bg-surface-white shadow-sm">
				<Avatar :image="activeLogo" :size="'lg'" class="h-12 w-12 object-cover" />
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

const activeLogo = computed(() => {
	const s = props.seminarySettings;
	if (!s) return null;
	if (theme.value === 'dark' && s.logo_dark) return s.logo_dark;
	return s.logo;
});
</script>

<style>
html[data-theme='dark'] .seminary-logo img {
	filter: none;
}
</style>
