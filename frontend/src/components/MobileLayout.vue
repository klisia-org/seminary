<template>
	<div class="flex h-full flex-col relative bg-surface-white text-ink-gray-9">
		<div class="h-full pb-16 overflow-y-auto" id="scrollContainer">
			<slot />
		</div>

		<!-- Fixed bottom navigation -->
		<div
			class="fixed bottom-0 left-0 w-full flex items-center justify-around border-t border-outline-gray-1 bg-surface-menu-bar standalone:pb-4 z-20"
		>
			<button
				v-for="link in visibleLinks"
				:key="link.to"
				class="flex flex-col items-center justify-center py-2 px-1 min-w-0 flex-1 transition active:scale-95"
				@click="handleClick(link)"
			>
				<component
					:is="link.icon"
					class="h-5 w-5 stroke-1.5"
					:class="isActive(link) ? 'text-ink-gray-9' : 'text-ink-gray-4'"
				/>
				<span
					class="text-[10px] mt-0.5 truncate max-w-full"
					:class="isActive(link) ? 'text-ink-gray-9 font-medium' : 'text-ink-gray-4'"
				>
					{{ link.label }}
				</span>
			</button>
		</div>

		<HelpWidget mobile />

		<ProfileModal v-model="showProfile" />
	</div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { usersStore } from '@/stores/user'
import { createResource } from 'frappe-ui'
import { BookOpen, GraduationCap, ClipboardCheck, ListChecks, Banknote, MonitorCog, UserRound, Building2 } from 'lucide-vue-next'
import ProfileModal from '@/components/ProfileModal.vue'
import HelpWidget from '@/components/HelpWidget.vue'

const router = useRouter()
const { userResource } = usersStore()
const showProfile = ref(false)

const seminarySettings = createResource({
	url: 'seminary.seminary.api.get_school_abbr_logo',
	auto: true,
})

// ADR 075: no /partner branch here any more. The partner areas are a PageTabs
// row inside the section, so this bottom bar stays the primary navigation on
// mobile exactly as it does everywhere else -- and the link rules live in one
// place instead of being restated per section.
const links = computed(() => {
	const isPartner = userResource?.data?.is_partner && userResource?.data?.partner_org
	const isStudent = userResource?.data?.is_student
	const isModerator = userResource?.data?.is_moderator
	const isSystemManager = userResource?.data?.is_system_manager
	const allowEnroll = seminarySettings.data?.allow_portal_enroll

	return [
		{ label: __('Courses'), to: '/courses', icon: BookOpen, activeFor: ['Courses', 'CourseDetail', 'Lesson', 'CourseForm', 'LessonForm'] },
		...(isStudent ? [
			{ label: __('Grades'), to: '/grades', icon: GraduationCap, activeFor: ['Transcripts'] },
			{ label: __('Audit'), to: '/program-audit', icon: ClipboardCheck, activeFor: ['ProgramAudit'] },
			...(allowEnroll ? [
				{ label: __('Enroll'), to: '/enrollment', icon: ListChecks, activeFor: ['Enrollment'] },
			] : []),
			{ label: __('Fees'), to: '/fees', icon: Banknote, activeFor: ['Fees'] },
		] : []),
		...(isPartner ? [
			{ label: __('Partner'), to: '/partner/jobs', icon: Building2, activeFor: ['PartnerProfile', 'PartnerPeople', 'PartnerJobPostings', 'PartnerJobPosting', 'PartnerApplication', 'PartnerInternshipPostings', 'PartnerInternshipPosting', 'PartnerInterns'] },
		] : []),
		...((isModerator || isSystemManager) ? [
			{ label: __('Desk'), to: '/desk/seminary', icon: MonitorCog, activeFor: ['Desk'] },
		] : []),
		{ label: __('Profile'), to: null, icon: UserRound, action: 'profile' },
	]
})

const visibleLinks = computed(() => links.value)

const isActive = (link) => {
	return link.activeFor?.includes(router.currentRoute.value.name)
}

const handleClick = (link) => {
	if (link.action === 'profile') {
		showProfile.value = true
	} else if (link.to === '/desk/seminary') {
		window.location.href = '/desk/seminary'
	} else {
		router.push(link.to)
	}
}
</script>
