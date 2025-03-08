<template>
	<Dropdown :options="userDropdownOptions" class="p-2">
		<template v-slot="{ open }">
			<button class="flex h-12 py-2 items-center  duration-300 ease-in-out" :class="isCollapsed
					? 'px-0 w-auto'
					: open
						? 'bg-white shadow-sm px-2 w-52'
						: 'hover:bg-gray-200 px-2 w-52'
				">
				<div class="w-8 h-8 flex items-center justify-center overflow-hidden">
					<Avatar v-if="seminarySettings?.logo" :image="seminarySettings?.logo" size="xl" class="object-cover" />
					<School v-else />
				</div>
				<div class="flex flex-1 flex-col text-left duration-300 ease-in-out" :class="isCollapsed
						? 'opacity-0 ml-0 w-0 overflow-hidden'
						: 'opacity-100 ml-2 w-auto'
					">
					<div class="text-base font-medium text-gray-900 leading-none">
						{{ seminarySettings?.name || 'Seminary' }}
					</div>
					<div class="mt-1 text-sm text-gray-700 leading-none">
						{{ userResource.data.full_name }}
					</div>
				</div>

				<div class="duration-300 ease-in-out" :class="isCollapsed
						? 'opacity-0 ml-0 w-0 overflow-hidden'
						: 'opacity-100 ml-2 w-auto'
					">
					<FeatherIcon name="chevron-down" class="h-4 w-4 text-gray-600" aria-hidden="true" />
				</div>
			</button>
		</template>
	</Dropdown>

	<ProfileModal />
</template>
  
<script setup>

import { Dropdown, FeatherIcon, Avatar } from 'frappe-ui'
import { sessionStore } from '@/stores/session'
import { usersStore } from '@/stores/user';
import { provide, ref, markRaw, computed } from 'vue'
import ProfileModal from '@/components/ProfileModal.vue'
import { School, ChevronDown, LogIn, LogOut, Moon, User, Settings, Sun, } from 'lucide-vue-next';
import { useSettings } from '@/stores/settings'
import { createDialog } from '@/utils/dialogs'

import { useRouter } from 'vue-router'


const router = useRouter()

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
provide('showProfileDialog', showProfileDialog)


const userDropdownOptions = computed(() => {
	return [
		{
			icon: User,
			label: 'My Profile',
			onClick: () => {
				router.push(`/user/${userResource.data?.username}`)
			},
			condition: () => {
				return isLoggedIn
			},
		},
		
		{
			icon: Settings,
			label: 'Settings',
			onClick: () => {
				settingsStore.isSettingsOpen = true
			},
			condition: () => {
				return userResource.data?.is_moderator
			},
		},
		
		{
			icon: LogOut,
			label: 'Log out',
			onClick: () => {
				logout.submit().then(() => {
					isLoggedIn = false
				})
			},
			condition: () => {
				return isLoggedIn
			},
		},
		{
			icon: LogIn,
			label: 'Log in',
			onClick: () => {
				window.location.href = '/login'
			},
			condition: () => {
				return !isLoggedIn
			},
		},
	]
})

</script>
  