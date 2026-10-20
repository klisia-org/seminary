<template>
	<!-- decisions/091 §11: what the person still has to sign or upload, where they land. -->
	<div v-if="count" class="mb-6">
		<h2 class="text-lg font-semibold text-ink-gray-9">{{ __('Requirements') }}</h2>
		<hr class="border-outline-gray-2 mb-3" />
		<div class="rounded border border-outline-amber-2 bg-surface-amber-1 px-3 py-2.5">
			<div class="text-sm text-ink-gray-8">
				{{ count === 1 ? __('You have 1 item to sign or upload.') : __('You have {0} items to sign or upload.').format(count) }}
			</div>
			<Button class="mt-2" size="sm" variant="solid" :label="__('Open')"
				@click="router.push({ name: 'Requirements' })" />
		</div>
	</div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Button } from 'frappe-ui'
import { usersStore } from '@/stores/user'

const router = useRouter()
const { userResource } = usersStore()
const count = computed(() => userResource?.data?.open_requirements || 0)
</script>
