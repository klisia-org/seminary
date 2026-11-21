<template>
	<OralActivity v-if="user.data" :activity="activity" :courseName="courseName" />
	<div v-else class="border rounded-md text-center py-20">
		<div>{{ __('Please log in to open the oral activity.') }}</div>
		<Button class="mt-2" @click="redirectToLogin()">{{ __('Login') }}</Button>
	</div>
</template>
<script setup>
import { inject } from 'vue'
import { Button } from 'frappe-ui'
import OralActivity from '@/components/OralActivity.vue'

const user = inject('$user')

defineProps({
	activity: { type: String, required: true },
	courseName: { type: String, required: true },
})

const redirectToLogin = () => {
	window.location.href = `/login?redirect-to=${encodeURIComponent(window.location.pathname)}`
}
</script>
