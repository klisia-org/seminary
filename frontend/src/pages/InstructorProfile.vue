<template>
    <div v-if="instructor.data">
        <header
            class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
            :aria-label="`Profile page for ${instructorName}`">

            <div class="text-3xl font-semibold text-ink-gray-9">
                {{ __('Profile page of') }} {{ instructorName }}
            </div>

        </header>
        <div v-if="instructor.data.profileimage" class="m-5">
            <img :src="instructor.data.profileimage" alt="Instructor Image" class="rounded-full h-40 w-40" />
        </div>
        <div class="m-5">
            <div class="text-lg font-semibold text-ink-blue-link flex items-center gap-3">
                <Mail class="h-5 w-5 text-ink-gray-5" />
                <a :href="`mailto:${instructor.data.prof_email || instructor.data.user}`">
                    {{ instructor.data.prof_email || instructor.data.user }}
                </a>
            </div>
            <div v-if="instructor.data.phone_message && instructor.data.messaging_apps?.length"
                class="flex items-center gap-3 mt-2">
                <template v-for="app in instructor.data.messaging_apps" :key="app.app_name">
                    <a :href="`${app.url_prefix}${instructor.data.phone_message.replace(/\D/g, '')}`"
                        target="_blank"
                        class="flex items-center gap-1 text-ink-blue-link hover:text-ink-green-3 transition-colors">
                        <span v-html="app.svg_icon" class="inline-block h-5 w-5 [&>svg]:h-full [&>svg]:w-full"></span>
                        {{ app.app_name }}
                    </a>
                </template>
            </div>
        </div>
        <div v-if="instructor.data.bio" class="m-5">
            <div class="text-3xl font-semibold text-ink-gray-9">
                {{ __('Know your Professor') }}
            </div>
            <div v-html="instructor.data.bio"
                class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal">
            </div>

        </div>


    </div>
</template>

<script setup>
import { Breadcrumbs, createResource, Button, TabButtons } from 'frappe-ui'
import { computed, inject, watch, ref, onMounted, watchEffect } from 'vue'

import { Mail } from 'lucide-vue-next'

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