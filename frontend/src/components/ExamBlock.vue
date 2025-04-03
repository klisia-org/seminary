<template>
	<Exam v-if="user.data" :examName="exam" ></Exam>
	<div v-else class="border rounded-md text-center py-20">
		<div>
			{{ __('Please login to access the exam.') }}
		</div>
		<Button @click="redirectToLogin()" class="mt-2">
			<span>
				{{ __('Login') }}
			</span>
		</Button>
	</div>
</template>
<script setup>
import { inject } from 'vue'
import { Button } from 'frappe-ui'
import Exam from '@/components/Exam.vue'

const user = inject('$user')


const props = defineProps({
	exam: {
		type: String,
		required: true,
	},
	
})


const redirectToLogin = () => {
	window.location.href = `/login`
}
</script>
