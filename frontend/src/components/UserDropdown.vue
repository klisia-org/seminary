<template>
	<Dropdown v-model="dropdownOpen" :options="userDropdownOptions" class="w-full">
		<template #default="{ open }">
			<div
			@click="dropdownOpen = !dropdownOpen"
			class="flex h-16 w-full items-center rounded-xl text-gray-900 transition-colors duration-200 ease-in-out cursor-pointer"
			:class="[
				dropdownOpen ? 'bg-white shadow-sm ring-1 ring-gray-200' : 'hover:bg-[#f3f3f3]',
				isCollapsed ? 'justify-center gap-0 px-0' : 'justify-between gap-3 px-3 pr-2'
			]"
		>
				<div class="flex h-12 w-12 flex-shrink-0 items-center justify-center overflow-hidden rounded-xl bg-white shadow-sm">
					<Avatar
						v-if="seminarySettings?.logo"
						:image="seminarySettings?.logo"
						:size="'lg'"
						class="h-12 w-12 object-cover"
					/>
					<School v-else class="h-6 w-6 text-gray-700" />
				</div>
				<div
					class="transition-all duration-200"
					:class="isCollapsed ? 'hidden' : 'min-w-0 flex-1 opacity-100'"
				>
					<div class="truncate text-sm font-semibold leading-snug">
						{{ seminarySettings?.name || 'Seminary' }}
					</div>
					<div class="truncate text-xs text-gray-600 leading-snug">
						{{ userResource?.data?.full_name || '' }}
					</div>
				</div>
				<FeatherIcon
					name="chevron-down"
					class="h-4 w-4 flex-shrink-0 text-gray-600 transition-opacity duration-200"
					:class="isCollapsed ? 'hidden' : 'ml-auto opacity-100'
					"
					aria-hidden="true"
				/>
			</div>
		</template>
	</Dropdown>
	<ProfileModal  />

</template>
  
<script setup>

import { Dropdown, FeatherIcon, Avatar } from 'frappe-ui'
import { sessionStore } from '@/stores/session'
import { usersStore } from '@/stores/user';
import { ref } from 'vue'
import { School } from 'lucide-vue-next';
import ProfileModal from '@/components/ProfileModal.vue'


let { userResource } = usersStore()
const { logout } = sessionStore()
defineOptions({
  inheritAttrs: false
})
const props = defineProps({
	isCollapsed: {
		type: Boolean,
		default: false,
	},
	seminarySettings: {
	}
})


const showProfileDialog = ref(false)

const dropdownOpen = ref(false)


const userDropdownOptions = [
  {
    icon: 'user',
    label: 'Profile',
    onClick: () => (showProfileDialog.value = true),
  },
  {
    icon: 'log-out',
    label: 'Log out',
    onClick: () => logout.submit(),
  },
]

</script>
