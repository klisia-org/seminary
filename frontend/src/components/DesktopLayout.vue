<template>
	<div class="relative flex h-full flex-col">
		<div class="h-full flex-1">
			<div class="flex h-screen text-base bg-surface-white">
				<div class="relative h-full">
					<AppSidebar />
				</div>
				<div class="relative flex-1 overflow-auto" id="scrollContainer">
					<slot />
					<a v-if="helpData"
						:href="helpData.mkdocs_url"
						target="_blank"
						class="fixed bottom-6 right-6 rounded-full bg-blue-500 p-3 text-white shadow-lg hover:bg-blue-600 z-50"
						:title="__('Help Documentation')">
						<HelpCircle class="h-5 w-5" />
					</a>
				</div>
			</div>
		</div>
	</div>
</template>
<script setup>
import AppSidebar from './AppSidebar.vue'
import { HelpCircle } from 'lucide-vue-next'
import { useHelp } from '@/utils/useHelp'

const { helpData } = useHelp()
</script>