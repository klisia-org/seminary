<template>

    <header
        class="sticky top-0 z-10 flex flex-col md:flex-row md:items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
        <Breadcrumbs class="h-7" :items="breadcrumbs" />
    </header>
    <div class="mt-5 mb-10 w-full px-5">
        <h3 class="text-2xl font-bold mb-3">{{ __('Course Calendar') }}</h3>
        <p class="text-gray-700 mb-5">{{ __('Subscribe to this course calendar to stay updated with events and ' +
            'schedules.') }}</p>
        <Button variant="solid" @click="subscribeCourseCalendar()" class="mt-5">
            <span>
                {{ __('Subscribe to this course calendar.') }}
            </span>
        </Button>

        <div class="space-y-4">
            <h3 class="text-2xl font-bold mt-8 mb-3">{{ __('How to Import the Calendar in the Major Platforms') }}</h3>
            <div v-if="CalendarInstructions.data">
                <p class="text-sm text-gray-600" v-html="CalendarInstructions.data"></p>
            </div>
            <div v-else>
                <div>
                    <h4 class="text-lg font-semibold">{{ __('Google Calendar') }}</h4>
                    <p class="text-sm text-gray-600">{{ __('Copy the calendar URL and add it to your Google Calendar by ' +
                        'selecting "Other Calendars" > "From URL".') }}</p>
                </div>

                <div>
                    <h4 class="text-lg font-semibold">{{ __('Outlook Calendar') }}</h4>
                    <p class="text-sm text-gray-600">{{ __('Copy the calendar URL and add it to your Outlook Calendar by ' +
                        'selecting "Add Calendar" > "Subscribe from Web".') }}</p>
                </div>

                <div>
                    <h4 class="text-lg font-semibold">{{ __('Apple Calendar') }}</h4>
                    <p class="text-sm text-gray-600">{{ __('Copy the calendar URL and add it to your Apple Calendar by ' +
                        'selecting "File" > "New Calendar Subscription".') }}</p>
                </div>
            </div>
        </div>

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

const Googlelink = 'https://support.google.com/calendar/answer/37118?hl=en&co=GENIE.Platform%3DDesktop'
const CalendarInstructions = createResource({
    url: 'frappe.client.get_single_value',
    params: {
        doctype: 'SeminarySettings',
        fieldname: 'calendar_instructions',
    },
    auto: true,
})

const course = createResource({
    url: 'seminary.seminary.utils.get_course_details',
    cache: ['course', props.courseName],
    params: {
        course: props.courseName,
    },
    auto: true,
})
console.log('Course Data:', course);

const subscribeCourseCalendar = () => {
    const calendarUrl = `${window.location.origin}/api/method/seminary.seminary.calendar.course_ics?course_schedule=${encodeURIComponent(props.courseName)}&token=${encodeURIComponent(course.data.calendar_token)}`;
    const calendardata = fetch(calendarUrl).then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    });
    console.log('Calendar URL:', calendarUrl);
    console.log('Calendar Data:', calendardata);
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




</script>