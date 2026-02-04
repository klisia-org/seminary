<template>

    <header
        class="sticky top-0 z-10 flex flex-col md:flex-row md:items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
        <Breadcrumbs class="h-7" :items="breadcrumbs" />
    </header>
    <div class="mt-5 mb-10 w-full px-5">
        <h3>{{ __('Course Calendar') }}</h3>
        <p>{{ __('Subscribe to this course calendar to stay updated with events and schedules.') }}</p>
        <Button variant="solid" @click="subscribeCourseCalendar()" class="ml-2">
            <span>
                {{ __('Subscribe to this course calendar.') }}
            </span>
        </Button>

    </div>
</template>
<script setup>
import { createResource, Breadcrumbs, Button } from 'frappe-ui'
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

console.log('Course Name:', props.courseName);

const course = createResource({
    url: 'seminary.seminary.utils.get_course_details',
    cache: ['course', props.courseName],
    params: {
        course: props.courseName,
    },
    auto: true,
})

const subscribeCourseCalendar = () => {
    const calendarUrl = `${window.location.origin}/api/method/seminary.seminary.doctype.course_schedule.course_schedule.get_course_schedule_ics?course=${props.courseName}&token=${course.data.calendar_token}`;
    navigator.clipboard.writeText(calendarUrl).then(() => {
        alert(__('Calendar URL copied to clipboard! You can now add it to your calendar application.'));
    }, () => {
        alert(__('Failed to copy calendar URL. Please try again.'));
    });
};

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