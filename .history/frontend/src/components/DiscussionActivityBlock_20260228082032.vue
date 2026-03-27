<template>
	<DiscussionActivity v-if="user.data" :discussionID="discussionID" :courseName="props.courseName"
		:submissionName="submission.data?.name || 'new'" />
	<div v-else class="border rounded-md text-center py-20">
		<div>
			{{ __('Please login to access the Discussion Activity.') }}
		</div>
		<Button @click="redirectToLogin()" class="mt-2">
			<span>
				{{ __('Login') }}
			</span>
		</Button>
	</div>
</template>
<script setup>
import { inject, onMounted } from 'vue'
import { Button, createResource } from 'frappe-ui'
import DiscussionActivity from '@/components/DiscussionActivity.vue'


const user = inject('$user')

const props = defineProps({
	discussionID: {
		type: String,
		required: true,
	},
	courseName: {
		type: String,
		required: true,
	},
})

console.log('Props:', props)
const submission = createResource({
	url: 'frappe.client.get_value',
	makeParams(values) {
		return {
			doctype: 'Discussion Submission',
			fieldname: 'name',
			filters: {
				disc_activity: props.discussionID,
				member: user.data?.name,
			},
		}
	},
	auto: true,
})
console.log(submission)

</script>
