<template>
	<div class="relative isolate flex h-full flex-col">
		<!-- `isolate`: the page's own stacking (sticky PageHeader z-10, sidebar z-20,
		     help widget) stays below dialogs frappe-ui teleports to <body>. Toasts live
		     outside this wrapper, so they still show over an open dialog. -->
		<div class="h-full flex-1">
			<div class="flex h-screen text-base bg-surface-white text-ink-gray-9">
				<div class="relative h-full">
					<AppSidebar />
				</div>
				<!-- The page content is the main landmark and the skip link's target (102 §9). -->
				<main id="scrollContainer" tabindex="-1" class="relative flex-1 overflow-auto focus:outline-none">
					<slot />
					<HelpWidget />
				</main>
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
