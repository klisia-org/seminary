<template>
	<div class="relative flex h-full flex-col">
		<div class="h-full flex-1">
			<div class="flex h-screen text-base bg-surface-white text-ink-gray-9">
				<div class="relative h-full">
					<PartnerSidebar v-if="isPartner" />
					<AppSidebar v-else />
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
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppSidebar from './AppSidebar.vue'
import PartnerSidebar from './PartnerSidebar.vue'
import HelpWidget from './HelpWidget.vue'

const route = useRoute()
const isPartner = computed(() => route.path.startsWith('/partner'))
</script>
