<template>
	<div
	
	  class="flex h-full flex-col justify-between transition-all duration-300 ease-in-out"
	  :class="isSidebarCollapsed ? 'w-12' : 'w-56'"
	>
	  <div class="flex flex-col overflow-hidden" >
		<UserDropdown 
			class="p-2"  
			:isCollapsed="isSidebarCollapsed" 
			:seminarySettings ="!seminarySettings.loading && seminarySettings.data"
		/>
		<div class="flex flex-col overflow-y-auto">
			<SidebarLink
				:label="link.label"
				:to="link.to"
				v-for="link in links"
				:isCollapsed="isSidebarCollapsed"
				:icon="link.icon"
				class="mx-2 my-0.5"
			/>
		</div>
	  </div>
	  <SidebarLink
		:label="isSidebarCollapsed ? 'Expand' : 'Collapse'"
		:isCollapsed="isSidebarCollapsed"
		@click="isSidebarCollapsed = !isSidebarCollapsed"
		class="m-2"
	  >
		<template #icon>
		  <span class="grid h-5 w-6 flex-shrink-0 place-items-center">
			<ArrowLeftToLine
			  class="h-4.5 w-4.5 text-gray-700 duration-300 ease-in-out"
			  :class="{ '[transform:rotateY(180deg)]': isSidebarCollapsed }"
			/>
		  </span>
		</template>
	  </SidebarLink>
	</div>
  </template>
  

<script setup>
import { useStorage } from '@vueuse/core'
import SidebarLink from '@/components/SidebarLink.vue'
import { LayoutDashboard,CalendarCheck,GraduationCap, Banknote, UserCheck, ArrowLeftToLine, BookOpen } from 'lucide-vue-next';
import { usersStore } from '@/stores/user'
import { sessionStore } from '@/stores/session'
import UserDropdown from './UserDropdown.vue';
import { createResource } from 'frappe-ui';
import { ref } from 'vue'

const { userResource } = usersStore()
const { user } = sessionStore()
const isModerator = ref(false)
const isInstructor = ref(false)


const links = [
	// {
	// 	label: 'Dashboard',
	// 	to: '/',
	// 	icon: LayoutDashboard,
	// },
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
	// {
	// 	label: 'Attendance',
	// 	to: '/attendance',
	// 	icon: UserCheck,
	// },
	// {
	// 	// TODO: create School Diary Page with card like CRM and from ListView go to Resource Document of each Card
	// 	label: 'Notes',
	// 	to: '/notes',
	// 	icon: BookOpen,
	// },
	// {
	// 	label: 'Profile',
	// 	to: '/profile',
	// 	icon: User,
	// },
]

const isSidebarCollapsed = useStorage('sidebar_is_collapsed', false)

// create a resource which call the function get_school_abbr_logo in api file using createResource
const seminarySettings = createResource({	
	url: 'seminary.seminary.api.get_school_abbr_logo',
	auto: true,
})


</script>