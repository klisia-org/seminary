<template>
    <div if="instructor_name">
        <header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
            :aria-label="`Profile page for ${instructorName}`">
            
            <div class="text-3xl font-semibold text-ink-gray-9">
            Profile page of {{ instructor.data.instructor_name }}
		</div>
			
		</header>
        <div v-if="instructor.data.image" class="m-5">
            <img :src="instructor.data.image" alt="Instructor Image" class="rounded-full h-40 w-40" />  
        </div>
        <div v-if="instructor.data.bio" class="m-5">
            <div class="text-3xl font-semibold text-ink-gray-9">
                Know your Professor
            </div>
            <div class="my-3 leading-6 text-ink-gray-7">
                {{ strippedBio }}
            </div>
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

const strippedBio = computed(() => {
    return stripHtmlTags(instructor.data.bio);
});


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