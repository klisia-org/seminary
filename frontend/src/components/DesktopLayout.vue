<template>
	<div class="relative flex h-full flex-col">
		<div class="h-full flex-1">
			<div class="flex h-screen text-base bg-surface-white">
				<div
					class="relative block h-full max-w-56"
				>
					<AppSidebar />
				</div>
				<div class="w-full overflow-auto" id="scrollContainer">
					<slot />
				</div>
			</div>
		</div>
	</div>
</template>
<script setup>
import AppSidebar from './AppSidebar.vue'
</script>