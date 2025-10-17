<template>
  <header class="flex justify-between sticky top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5">
    <Breadcrumbs :items="breadcrumbs" />
  </header>
  <div class="flex items-center justify-between mb-5">
    <!-- Previous Button -->
    <Button variant="subtle" :disabled="currentIndex === 0"
      @click="currentSubmission = submissionlist.data[currentIndex - 1]?.name">
      {{ __('Previous') }}
    </Button>

    <!-- Dropdown for All Submissions -->
    <div class="w-1/3">
      <label for="submissionDropdown" class="block text-sm font-medium text-gray-700">
        {{ __('Select Submission') }}
      </label>
      <select id="submissionDropdown" v-model="currentSubmission"
        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
        <option v-for="submission in submissionlist.data" :key="submission.name" :value="submission.name">
          {{ submission.student_name }}
        </option>
      </select>
    </div>

    <!-- Next Button -->
    <Button variant="subtle" :disabled="!submissionlist.data || currentIndex === submissionlist.data.length - 1"
      @click="currentSubmission = submissionlist.data[currentIndex + 1]?.name">
      {{ __('Next') }}
    </Button>
  </div>
  <div class="overflow-hidden h-[calc(100vh-3.2rem)]">
    <DiscussionActivity :discussionID="discussionID" :submissionName="submissionName" :canGradeSubmission="true" />
  </div>
</template>
<script setup>
import { Breadcrumbs, createResource,  } from 'frappe-ui'
import { computed, onBeforeUnmount, onMounted, inject, watch, watchEffect, ref } from 'vue'
import { useRouter } from 'vue-router'
import DiscussionActivity from '@/components/DiscussionActivity.vue'
import Discussions from '@/components/Discussions.vue'


const router = useRouter()
const user = inject('$user')

const props = defineProps({
  discussionID: {
    type: String,
    required: true,
  },
  submissionName: {
    type: String,
    required: true,
  },
  courseName: {
    type: String,
    required: true,
  },
})
const currentSubmission = ref(props.submissionName); // Initialize with the current submissionName
const submissionName = ref(props.submissionName); // Create a reactive copy of the prop

const title = createResource({
  url: 'frappe.client.get_value',
  params: {
    doctype: 'Discussion Activity',
    fieldname: 'discussion_name',
    filters: {
      name: props.discussionID,
    },
  },
  auto: true,
})

const submissionlist = createResource({
  url: 'frappe.client.get_list',
  params: {
    doctype: 'Discussion Submission',
    filters: [
      ['disc_activity', '=', props.discussionID],
      ['coursesc', '=', props.courseName],
    ],
    fields: ['name', 'student_name'], // Fetch only necessary fields
    order_by: 'student_name asc', // Order by student name
  },
  auto: true,
});
console.log('Submission List:', submissionlist)

onMounted(() => {
  if (!user.data?.is_instructor && !user.data?.is_moderator)
    router.push({ name: 'Courses' })
})

const currentIndex = computed(() =>
  submissionlist.data?.findIndex((submission) => submission.name === currentSubmission.value)
);

// watch(currentSubmission, (newSubmission) => {
//   submissionName.value = newSubmission; // Update submissionName
//   router.push({
//     name: 'DiscussionActivitySubmission',
//     params: {
//       discussionID: props.discussionID,
//       courseName: props.courseName,
//       submissionName: newSubmission,
//     },
//   });
// });

const course = createResource({
  url: 'seminary.seminary.utils.get_course_details',
  cache: ['course', props.courseName],
  params: {
    course: props.courseName,
  },
  auto: true,
}) //Neded for the breadcrumbs

const breadcrumbs = computed(() => {
  let items = [{ label: 'Courses', route: { name: 'Courses' } }]
  items.push({
    label: course?.data?.course,
    route: { name: 'CourseDetail', params: { courseName: props.courseName } },
  })
  items.push({
    label: 'Gradebook',
    route: { name: 'Gradebook', params: { courseName: props.courseName } },
  })
  items.push({
    label: 'Discussion Submissions',
    route: { name: 'DiscussionActivitySubmission', params: { courseName: props.courseName, discussionID: props.discussionID } },
  })
  return items
})


</script>
