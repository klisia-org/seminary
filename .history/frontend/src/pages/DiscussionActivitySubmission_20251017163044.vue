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
      <h1 class="text-2xl font-bold mt-4 mb-4">
        {{ title.data?.discussion_name || __('Discussion Activity Submission') }}
      </h1>
      <label for="submissionDropdown" class="block text-sm font-medium text-gray-700 mb-4">
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
  <div class="flex">
    <!-- Left 2/3 for discussion content -->
    <div class="w-2/3">
      <Suspense>
        <template #default>
          <div class="overflow-hidden h-[calc(100vh-3.2rem)]">
            <div class="mb-6 border-round border-gray-300 p-4 bg-surface-white shadow-sm">
              <h2>{{ __('Original Post(s) by') }} {{ studentName }}</h2>
              <div v-for="post in originalPosts" :key="post.name" class="post">
                <div class="post-content" v-html="post.original_post"></div>
                <div class="post-meta text-sm text-ink-gray-5">
                  {{ formatDate(post.creation) }}
                </div>
                <a v-if="post.original_attachment" :href="post.original_attachment" target="_blank"
                  class="text-blue-500 underline">
                  {{ __('View Attachment') }}
                </a>
              </div>
            </div>

            <div class="replies">
              <h2>{{ __('Replies by') }} {{ studentName }}</h2>
              <div v-for="reply in studentReplies" :key="reply.creation" class="reply">
                <div class="reply-meta text-sm text-ink-gray-5">
                  {{ __('Reply to:') }} {{ reply.student_name }}
                  {{ reply.original_post }}
                </div>
                <div class="reply-content" v-html="reply.reply"></div>
                <div class="reply-meta text-sm text-ink-gray-5">
                  {{ formatDate(reply.reply_dt) }}
                </div>
                <a v-if="reply.reply_attach" :href="reply.reply_attach" target="_blank" class="text-blue-500 underline">
                  {{ __('View Attachment') }}
                </a>
              </div>
            </div>
          </div>
        </template>
        <template #fallback>
          <div class="text-center py-10">
            <span>{{ __('Loading submission data...') }}</span>
          </div>
        </template>
      </Suspense>
    </div>

    <!-- Right 1/3 for grading -->
    <div class="w-1/3 border-l pl-4">
      <h2 class="text-lg font-semibold mb-4">{{ __('Grading') }}</h2>

      <!-- Grade Input -->
      <label for="gradeInput" class="block text-sm font-medium text-gray-700 mb-2">
        {{ __('Grade') }}
      </label>
      <input
        id="gradeInput"
        v-model="grade"
        type="number"
        class="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm mb-4"
      />



      <!-- Save Button -->
      <Button
        variant="solid"
        @click="saveGrading"
        class="w-full"
      >
        {{ __('Save') }}
      </Button>
    </div>
  </div>
</template>

<script setup>
import { Breadcrumbs, createResource, Button } from 'frappe-ui'
import { computed, onBeforeUnmount, onMounted, inject, watch, watchEffect, ref } from 'vue'
import { useRouter } from 'vue-router'
import dayjsModule from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import Discussions from '@/components/Discussions.vue'

const dayjs = typeof dayjsModule === 'function' ? dayjsModule : dayjsModule.default;
dayjs.extend(relativeTime);

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
const originalPosts = ref([]);
const studentReplies = ref([]);
const grade = ref(null);
const comments = ref('');

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

const formatDate = (dateString) => {
  if (dateString && dateString.includes('.')) {
    return dayjs(dateString.split('.')[0]).fromNow();
  }
  return dayjs(dateString).fromNow();
};

const submissionlist = createResource({
  url: 'frappe.client.get_list',
  params: {
    doctype: 'Discussion Submission',
    filters: [
      ['disc_activity', '=', props.discussionID],
      ['coursesc', '=', props.courseName],
    ],
    fields: ['name', 'student_name', 'member'], // Fetch only necessary fields
    order_by: 'student_name asc', // Order by student name
  },
  auto: true,
});


onMounted(() => {


  if (!user.data?.is_instructor && !user.data?.is_moderator)
    router.push({ name: 'Courses' })
})

const currentIndex = computed(() =>
  submissionlist.data?.findIndex((submission) => submission.name === currentSubmission.value)
);

const studentName = computed(() => submissionlist.data?.find(sub => sub.name === currentSubmission.value)?.student_name);
const memberName = computed(() => submissionlist.data?.find(sub => sub.name === currentSubmission.value)?.member);

const fetchStudentData = createResource({
  url: 'seminary.seminary.api.get_user_discussion_submission',
  makeParams(values) {
    return {
      course_name: router.currentRoute.value.params.courseName,
      discussion_id: props.discussionID,
      owner: memberName.value,
    }
  },
  auto: false,
  onSuccess(data) {
    originalPosts.value = data;

  },
});

const fetchStudentReplies = createResource({
  url: 'seminary.seminary.api.get_user_discussion_replies',
  makeParams(values) {
    return {
      course_name: router.currentRoute.value.params.courseName,
      discussion_id: props.discussionID,
      member: memberName.value,
    }
  },
  auto: false,
  onSuccess(data) {
    studentReplies.value = data;
  },
});

watch(currentSubmission, (newSubmission) => {
  submissionName.value = newSubmission; // Update submissionName
  router.push({
    name: 'DiscussionActivitySubmission',
    params: {
      discussionID: props.discussionID,
      courseName: props.courseName,
      submissionName: newSubmission,
    },
  });
});

watch(
  () => studentName.value,
  (newStudentName) => {
    if (newStudentName) {
      fetchStudentData.reload();
      fetchStudentReplies.reload();
    }
  }
);
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

const saveGrading = () => {
  // Call API to update the current discussion submission with grade and comments
  call('frappe.client.set_value', {
    doctype: 'Discussion Submission',
    name: currentSubmission.value,
    fieldname: {
      grade: grade.value,
      comments: comments.value,
    },
  })
    .then(() => {
      toast.success(__('Grading saved successfully'));
    })
    .catch((error) => {
      toast.error(__('Failed to save grading: {0}').format(error.message));
    });
};
</script>

<style scoped>
.flex {
  display: flex;
}

.w-2\/3 {
  width: 66.6667%;
}

.w-1\/3 {
  width: 33.3333%;
}

.border-l {
  border-left: 1px solid #e5e7eb;
}

.pl-4 {
  padding-left: 1rem;
}
</style>
