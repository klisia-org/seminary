<template>

    <header
        class="sticky top-0 z-10 flex flex-col md:flex-row md:items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
        <Breadcrumbs class="h-7" :items="breadcrumbs" />
    </header>
    <div>
        <h3>Course Calendar</h3>
        <p>Subscribe to this course calendar to stay updated with events and schedules.</p>
          <Button variant="subtle" class="ml-2">
                <span>
                  {{ __('Save only allowed when Total Points = 100') }}
                </span>
              </Button>
        <p v-if="calendarLink">
            <a :href="calendarLink" target="_blank">Open Calendar in Your App</a>
        </p>
    </div>
</template>
<script setup>
import { createResource, Breadcrumbs, Button, FormControl, Tooltip, toast } from 'frappe-ui'
import { computed, reactive, onMounted, inject, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const user = inject('$user')


const props = defineProps({
    courseName: {
        type: String,
        required: true,
    },
})

const course = createResource({
    url: 'seminary.seminary.utils.get_course_details',
    cache: ['course', props.courseName],
    params: {
        course: props.courseName,
    },
    auto: true,
})
const calendarLink = ref('')

const breadcrumbs = computed(() => {
    let items = [{ label: 'Courses', route: { name: 'Courses' } }]
    items.push({
        label: course?.data?.course,
        route: { name: 'CourseCalendar', params: { courseName: props.courseName } },
    })

    return items
})

const pageMeta = computed(() => {
    return {
        title: course?.data?.title,
        description: "Course Calendar for the course",
    }
})

updateDocumentTitle(pageMeta)

</script>