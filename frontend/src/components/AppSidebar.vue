<template>
	<div class="relative z-20 flex h-full flex-shrink-0 flex-col justify-between border-r border-outline-gray-1 bg-surface-menu-bar text-ink-gray-9 transition-all duration-300 ease-in-out"
		:class="isSidebarCollapsed ? 'w-16' : 'w-64'">
		<div class="flex flex-col overflow-hidden">
			<div class="px-3 pt-6 pb-4">
				<UserDropdown :isCollapsed="isSidebarCollapsed"
					:seminarySettings="!seminarySettings.loading && seminarySettings.data ? seminarySettings.data : {}" />
			</div>
			<nav class="flex flex-col gap-1 overflow-y-auto px-3 pb-6">
				<SidebarLink v-for="link in links" :key="link.to" :label="link.label" :to="link.to"
					:isCollapsed="isSidebarCollapsed" :icon="link.icon" :badge="link.badge || 0" />
				<template
					v-if="userResource?.data?.is_moderator || userResource?.data?.is_system_manager || userResource?.data?.is_registrar">
					<SidebarLink :label="__('Desk')" :to="'/desk/seminary'" :icon="MonitorCog"
						:isCollapsed="isSidebarCollapsed" />
				</template>
			</nav>
		</div>
		<div class="px-3 pb-6 flex flex-col gap-1">
			<div v-if="!isSidebarCollapsed" class="px-1 pb-1">
				<PortalSwitcher :portals="visiblePortals" />
			</div>
			<button type="button" @click="toggleTheme"
				:title="theme === 'dark' ? __('Switch to light mode') : __('Switch to dark mode')"
				class="group flex w-full min-h-[44px] cursor-pointer items-center rounded-lg text-ink-gray-8 transition-colors duration-200 hover:bg-surface-gray-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-outline-gray-3"
				:class="isSidebarCollapsed ? 'justify-center px-0 py-2' : 'justify-start px-3 py-2'">
				<span class="grid h-5 w-6 flex-shrink-0 place-items-center">
					<Sun v-if="theme === 'dark'" class="h-4.5 w-4.5 text-ink-gray-7" />
					<Moon v-else class="h-4.5 w-4.5 text-ink-gray-7" />
				</span>
				<span class="flex-shrink-0 text-base transition-all duration-200"
					:class="isSidebarCollapsed ? 'ml-0 w-0 overflow-hidden opacity-0' : 'ml-3 w-auto opacity-100'">
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
import { GraduationCap, Banknote, ArrowLeftToLine, ArrowRightToLine, BookOpen, MonitorCog, ClipboardCheck, ListChecks, Sun, Moon, Inbox, SlidersHorizontal, Users, ScrollText, Briefcase, Handshake, Building2, MessagesSquare } from 'lucide-vue-next';
import UserDropdown from './UserDropdown.vue';
import { createResource } from 'frappe-ui';
import { computed, watch } from 'vue';
import { useRoute } from 'vue-router';
import { usersStore } from '@/stores/user';
import { useTheme } from '@/composables/useTheme';
import { PortalSwitcher, getPortalConfig, visiblePortalsFor } from '@seminary/portal-shell';

const portalConfig = getPortalConfig();

// ADR 074: one implementation of "which portals may this session see". This had
// its own copy that applied the role filter but dropped `when`, so capability
// gates (has_aretenic, has_giving) were ignored here — and this sidebar is where
// most users meet the switcher. `userResource.data` already carries `roles` plus
// those flags, so it serves directly as the session.
const visiblePortals = computed(() =>
	visiblePortalsFor(portalConfig.portals, userResource?.data),
);

const { theme, toggleTheme } = useTheme();

const { userResource } = usersStore();

// Members (students/instructors and super-roles) get the Courses + Inbox portal.
// Other roles that reach this shell — e.g. an external examiner who is also a
// partner — only see the links relevant to them, and we skip the member-only
// data fetches below that would otherwise 403 in the console.
const isMember = computed(() => {
	const u = userResource?.data || {}
	return !!(u.is_student || u.is_instructor || u.is_moderator || u.is_system_manager || u.is_registrar)
});

const unreadCount = createResource({
	url: 'seminary.seminary.comms.get_my_unread_count',
	auto: false,
});

// Fetch (and refresh as the user moves around) the unread badge only for members
// who can access the Inbox.
const route = useRoute();
watch(
	() => [isMember.value, route.path],
	() => { if (isMember.value) unreadCount.reload() },
	{ immediate: true }
);

const links = computed(() => {
	const isStudent = userResource?.data?.is_student
	const isAlumni = userResource?.data?.is_alumni
	const isParticipant = (userResource?.data?.roles || []).includes('Cohort Participant')
	const isEvaluator = userResource?.data?.is_evaluator
	const hasCulminatingProjects = userResource?.data?.has_culminating_projects
	// ADR 074: one server-side flag, so the link and the page agree. Hand-checking
	// capabilities here left mentors with no way to reach their own queue.
	const hasFacultyWorklist = userResource?.data?.has_faculty_worklist
	// Partner users are not `isMember`, so without this they'd see a sidebar
	// containing only Preferences — the portal-switcher tile ADR 074 removed was
	// previously their sole route into the partner area.
	const isPartner = userResource?.data?.is_partner && userResource?.data?.partner_org
	const allowEnroll = seminarySettings.data?.allow_portal_enroll
	return [
		...(isMember.value ? [{
			label: __('Courses'),
			to: '/courses',
			icon: BookOpen,
		}] : []),
		...((isMember.value || isAlumni || isParticipant) ? [{
			label: __('Community'),
			to: '/community',
			icon: MessagesSquare,
		}] : []),
		...(isStudent ? [
			{
				label: __('Transcripts'),
				to: '/grades',
				icon: GraduationCap,
			},
			{
				label: __('Program Audit'),
				to: '/program-audit',
				icon: ClipboardCheck,
			},
			...(allowEnroll ? [{
				label: __('Enrollment'),
				to: '/enrollment',
				icon: ListChecks,
			}] : []),
			{
				label: __('Fees'),
				to: '/fees',
				icon: Banknote,
			},
		] : []),
		...(hasCulminatingProjects ? [{
			label: __('Culminating Project'),
			to: '/culminating-project',
			icon: ScrollText,
		}] : []),
		...(hasFacultyWorklist ? [{
			label: __('Faculty Worklist'),
			to: '/faculty-worklist',
			icon: ClipboardCheck,
		}] : []),
		...(isPartner ? [{
			label: __('Partner'),
			to: '/partner/jobs',
			icon: Building2,
		}] : []),
		...((isStudent || isAlumni) ? [{
			label: __('Jobs'),
			to: '/jobs',
			icon: Briefcase,
		}] : []),
		...(isStudent ? [{
			label: __('Internships'),
			to: '/internships',
			icon: Handshake,
		}] : []),
		...(isMember.value ? [{
			label: __('Inbox'),
			to: '/inbox',
			icon: Inbox,
			badge: unreadCount.data || 0,
		}] : []),
		{
			label: __('Preferences'),
			to: '/preferences',
			icon: SlidersHorizontal,
		},
		...(userResource?.data?.is_alumni ? [{
			label: __('Alumni'),
			to: '/alumni',
			icon: Users,
		}] : []),
		...((isAlumni && seminarySettings.data?.allow_alumni_partner_directory) ? [{
			label: __('Organizations'),
			to: '/alumni/organizations',
			icon: Building2,
		}] : []),
	]
})

const isSidebarCollapsed = useStorage('sidebar_is_collapsed', false);

const collapseIcon = computed(() => (isSidebarCollapsed.value ? ArrowRightToLine : ArrowLeftToLine));

const seminarySettings = createResource({
	url: 'seminary.seminary.api.get_school_abbr_logo',
	auto: true,
});
console.log("Seminary Settings:", seminarySettings);


</script>