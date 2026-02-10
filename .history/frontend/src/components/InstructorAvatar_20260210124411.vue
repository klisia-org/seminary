<template>
	<Tooltip :text="`${instructor_name} - ('Profile Page')`">
		<router-link :to="{
			name: 'InstructorProfile',
			params: { instructorName: instructor_name },

		}">
			<Avatar class="avatar border border-outline-gray-2 cursor-auto" v-if="instructor_name"
				:label="instructor_name" :image="encodedProfileImage" :size="size" v-bind="$attrs" />
		</router-link>
	</Tooltip>
</template>
<script setup>
import { Avatar, Tooltip } from 'frappe-ui'
import { computed, defineProps } from 'vue'
const props = defineProps({
	instructor: {
		type: Object,
		default: null,
	},
	size: {
		type: String,

	}
})

const instructor_name = computed(() => props.instructor?.instructor_name || '')
const profileImage = computed(() => props.instructor?.profileimage || '')
const encodedProfileImage = computed(() => profileImage.value ? encodeURI(profileImage.value) : '')
</script>
