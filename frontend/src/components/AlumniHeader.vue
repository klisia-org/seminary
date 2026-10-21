<!--
  The alumni section's frame (ADR 075).

  The four alumni areas were already sibling routes, reached via a grid of
  router-link cards on AlumniHome and two sidebar entries — so they were
  navigation without looking like it, and there was no way to tell where you
  were. Route-backed tabs: no local state, and the active tab is the URL.
-->
<template>
	<PageHeader :title="title">
		<template #actions>
			<slot name="actions" />
		</template>
		<template #tabs>
			<PageTabs :tabs="tabs" :label="__('Alumni areas')" />
		</template>
	</PageHeader>
</template>

<script setup>
import { computed } from 'vue'
import { createResource } from 'frappe-ui'
import PageHeader from './PageHeader.vue'
import PageTabs from './PageTabs.vue'

defineProps({ title: { type: String, default: '' } })

const seminarySettings = createResource({
	url: 'seminary.seminary.api.get_school_abbr_logo',
	auto: true,
})

const tabs = computed(() => [
	{ key: 'home', label: __('Overview'), route: '/alumni' },
	{ key: 'directory', label: __('Directory'), route: '/alumni/directory' },
	// Same gate the sidebar link uses: the partner directory is opt-in per school.
	...(seminarySettings.data?.allow_alumni_partner_directory
		? [{ key: 'organizations', label: __('Organizations'), route: '/alumni/organizations' }]
		: []),
	{ key: 'profile', label: __('My Profile'), route: '/alumni/profile' },
])
</script>
