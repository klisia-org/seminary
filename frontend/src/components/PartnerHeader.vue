<!--
  The partner section's frame (ADR 075).

  Replaces PartnerSidebar: the five partner areas were a whole swapped-in
  sidebar, which cost a second copy of the portal switcher (it drifted, and kept
  showing a Donate tile on sites without frappe_giving), a third copy of the nav
  link rules, and the user's primary navigation for as long as they were in the
  section. They are peer areas of one section, so they are tabs.

  The organization switcher stays in the header row rather than moving to the
  body: it is the one control that decides what the whole section is *about*,
  which is the exception ADR 075 carves out for a primary scope selector.
-->
<template>
	<PageHeader :title="title">
		<template #actions>
			<label v-if="hasMultiple" class="sr-only" :for="orgSelectId">
				{{ __('Organization') }}
			</label>
			<select
				v-if="hasMultiple"
				:id="orgSelectId"
				:value="activeOrg"
				@change="onSwitchOrg($event.target.value)"
				class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm font-medium text-ink-gray-8 focus:border-outline-gray-4 focus:outline-none"
			>
				<option v-for="o in orgs" :key="o.name" :value="o.name">
					{{ o.organization_name }}
				</option>
			</select>
			<span v-else-if="activeOrgName" class="truncate text-sm text-ink-gray-6">
				{{ activeOrgName }}
			</span>
			<slot name="actions" />
		</template>
		<template #tabs>
			<PageTabs :tabs="tabs" :label="__('Partner areas')" />
		</template>
	</PageHeader>
</template>

<script setup>
import { computed, onMounted, useId } from 'vue'
import { useRouter } from 'vue-router'
import PageHeader from './PageHeader.vue'
import PageTabs from './PageTabs.vue'
import { usePartnerOrg } from '@/composables/usePartnerOrg'

defineProps({ title: { type: String, default: '' } })

const router = useRouter()
const orgSelectId = useId()
const { activeOrg, activeOrgName, orgs, hasMultiple, setActiveOrg, ensureLoaded } =
	usePartnerOrg()
onMounted(ensureLoaded)

function onSwitchOrg(name) {
	if (!name || name === activeOrg.value) return
	setActiveOrg(name)
	// Reset to a context valid for any org so a stale detail view can't linger;
	// list/profile pages re-fetch for the new org.
	router.push({ name: 'PartnerProfile' })
}

// Route-backed: no local state, and a detail route (/partner/jobs/ABC) keeps
// its list tab highlighted because PageTabs matches on path prefix.
const tabs = computed(() => [
	{ key: 'profile', label: __('Our Profile'), route: '/partner/profile' },
	{ key: 'people', label: __('Our People'), route: '/partner/people' },
	{ key: 'jobs', label: __('Job Postings'), route: '/partner/jobs' },
	{ key: 'internships', label: __('Internships'), route: '/partner/internships' },
	{ key: 'interns', label: __('Our Interns'), route: '/partner/interns' },
])
</script>
