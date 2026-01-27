<template>
	<div class="relative z-20 flex h-full flex-shrink-0 flex-col justify-between border-r border-gray-200 bg-[#f8f8f8] text-gray-900 transition-all duration-300 ease-in-out"
		:class="isSidebarCollapsed ? 'w-16' : 'w-64'">
		<div class="flex flex-col overflow-hidden">
			<div class="px-3 pt-6 pb-4">
				<UserDropdown :isCollapsed="isSidebarCollapsed"
					:seminarySettings="!seminarySettings.loading && seminarySettings.data" />
			</div>
			<nav class="flex flex-col gap-1 overflow-y-auto px-3 pb-6">
				<SidebarLink v-for="link in links" :key="link.to" :label="link.label" :to="link.to"
					:isCollapsed="isSidebarCollapsed" :icon="link.icon" />
				<template v-if="user.data?.is_moderator">
					<SidebarLink :label="'Desk'" :to="'/app'" :icon="MonitorCog" :isCollapsed="isSidebarCollapsed" />
				</template>
			</nav>
		</div>
		<div class="px-3 pb-6">
			<SidebarLink :label="isSidebarCollapsed ? 'Expand' : 'Collapse'" :isCollapsed="isSidebarCollapsed"
				@click="isSidebarCollapsed = !isSidebarCollapsed">
				<template #icon>
					<span class="grid h-5 w-6 flex-shrink-0 place-items-center">
						<component :is="collapseIcon"
							class="h-4.5 w-4.5 text-gray-700 transition-transform duration-300" />
					</span>
				</template>
			</SidebarLink>
		</div>
	</div>
</template>

<script setup>
import { useStorage } from '@vueuse/core'
import SidebarLink from '@/components/SidebarLink.vue'
import { GraduationCap, Banknote, ArrowLeftToLine, ArrowRightToLine, BookOpen, MonitorCog } from 'lucide-vue-next';
import UserDropdown from './UserDropdown.vue';
import { createResource } from 'frappe-ui';
import { computed } from 'vue';
import { usersStore } from '@/stores/user';

const { userResource } = usersStore();

const links = [
	{
		label: 'Courses',
		to: '/courses',
		icon: BookOpen,
	},
	{
		label: 'Transcripts',
		to: '/grades',
		icon: GraduationCap,
	},
	{
		label: 'Fees',
		to: '/fees',
		icon: Banknote,
	},
]

const isSidebarCollapsed = useStorage('sidebar_is_collapsed', false);

const collapseIcon = computed(() => (isSidebarCollapsed.value ? ArrowRightToLine : ArrowLeftToLine));

const seminarySettings = createResource({
	url: 'seminary.seminary.api.get_school_abbr_logo',
	auto: true,
});
console.log("Seminary Settings:", seminarySettings);


</script>