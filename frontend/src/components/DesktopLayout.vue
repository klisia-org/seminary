<template>
	<div class="relative flex h-full flex-col">
		<div class="h-full flex-1">
			<div class="flex h-screen text-base bg-surface-white text-ink-gray-9">
				<div class="relative h-full">
					<AppSidebar />
				</div>
				<div class="relative flex-1 overflow-auto" id="scrollContainer">
					<slot />
					<HelpWidget />
				</div>
			</div>
		</div>
	</div>
</template>
<script setup>
// One shell for every section (ADR 075). This used to swap in a whole
// PartnerSidebar on a `/partner` path prefix, which took the primary navigation
// away from partner users and forced the nav rules and the portal switcher to
// be maintained in a second place. The partner areas are tabs now.
import AppSidebar from './AppSidebar.vue'
import HelpWidget from './HelpWidget.vue'
</script>
