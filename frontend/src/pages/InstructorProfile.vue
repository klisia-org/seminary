<template>
    <div if="instructor_name">
        <header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
            :aria-label="`Profile page for ${instructorName}`">
            
            <div class="text-3xl font-semibold text-ink-gray-9">
            Profile page of {{ instructorName }}
		</div>
			
		</header>
        <div v-if="instructor.data.profileimage" class="m-5">
            <img :src="instructor.data.profileimage" alt="Instructor Image" class="rounded-full h-40 w-40" />  
        </div>
        <div v-if="instructor.data.bio" class="m-5">
            <div class="text-3xl font-semibold text-ink-gray-9">
                Know your Professor
            </div>
            <div v-html="instructor.data.bio" class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal"></div>
                
        </div>
        

    </div>
</template>

<script setup>
import { Breadcrumbs, createResource, Button, TabButtons } from 'frappe-ui'
import { computed, inject, watch, ref, onMounted, watchEffect } from 'vue'

import { Edit } from 'lucide-vue-next'

import { useRoute, useRouter } from 'vue-router'

import { convertToTitleCase, updateDocumentTitle } from '@/utils'

const props = defineProps({
	instructorName: {
		type: String,
		required: true,
	},
})

const route = useRoute();
const instructorName = route.params.instructorName;

const instructor = createResource({
    url: 'seminary.seminary.utils.get_instructor',
    params: {
        instructorName: instructorName,
    },  
    auto: true,
})





// Function to strip HTML tags from a string
function stripHtmlTags(str) {
	const div = document.createElement('div')
	div.innerHTML = str
	return div.textContent || div.innerText || ''
}

const pageMeta = computed(() => {
	return {
		title: instructor.instructor_name,
		description: instructor.bio,
	}
})

updateDocumentTitle(pageMeta)
</script>