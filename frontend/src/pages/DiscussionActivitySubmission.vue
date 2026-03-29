<template>
  <header class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
    <Breadcrumbs :items="breadcrumbs" />
  </header>
  <div class="px-5 py-5 h-[calc(100vh-3.2rem)] overflow-y-auto">
    <!-- Navigation bar -->
    <div class="flex items-center justify-between mb-5">
      <Button variant="subtle" :disabled="currentIndex === 0"
        @click="currentSubmission = submissionlist.data[currentIndex - 1]?.name">
        {{ __('Previous') }}
      </Button>
      <div class="text-center">
        <h1 class="text-xl font-semibold text-ink-gray-9">
          {{ title.data?.discussion_name || __('Discussion Activity Submission') }}
        </h1>
        <div class="mt-2 w-64 mx-auto">
          <select v-model="currentSubmission"
            class="block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 text-sm">
            <option v-for="submission in submissionlist.data" :key="submission.name" :value="submission.name">
              {{ submission.student_name }}
            </option>
          </select>
        </div>
      </div>
      <Button variant="subtle" :disabled="!submissionlist.data || currentIndex === submissionlist.data.length - 1"
        @click="currentSubmission = submissionlist.data[currentIndex + 1]?.name">
        {{ __('Next') }}
      </Button>
    </div>

    <!-- Main content: 2 columns -->
    <div class="grid grid-cols-1 md:grid-cols-[65%,35%] gap-6">
      <!-- Left: Student posts & replies -->
      <div class="space-y-6">
        <div class="border rounded-lg p-5 bg-surface-white shadow-sm">
          <h2 class="text-lg font-semibold mb-3 text-ink-gray-9">
            {{ __('Original Post(s) by') }} {{ studentName }}
          </h2>
          <div v-for="post in originalPosts" :key="post.name" class="border rounded-md p-4 mb-3 last:mb-0">
            <div class="prose-sm" v-html="post.original_post"></div>
            <div class="text-xs text-ink-gray-4 mt-2">{{ formatDate(post.creation) }}</div>
            <a v-if="post.original_attachment" :href="post.original_attachment" target="_blank"
              class="text-blue-500 underline text-sm mt-1 inline-block">
              {{ __('View Attachment') }}
            </a>
          </div>
          <div v-if="!originalPosts.length" class="text-sm text-ink-gray-4">
            {{ __('No original posts found.') }}
          </div>
        </div>

        <div class="border rounded-lg p-5 bg-surface-white shadow-sm">
          <h2 class="text-lg font-semibold mb-3 text-ink-gray-9">
            {{ __('Replies by') }} {{ studentName }}
          </h2>
          <div v-for="reply in studentReplies" :key="reply.creation" class="border rounded-md p-4 mb-3 last:mb-0">
            <div class="text-xs text-ink-gray-5 mb-2">
              {{ __('Reply to') }}: {{ reply.student_name }}
              <div class="prose-sm text-ink-gray-4 mt-1" v-html="reply.original_post"></div>
            </div>
            <div class="prose-sm mt-2" v-html="reply.reply"></div>
            <div class="text-xs text-ink-gray-4 mt-2">{{ formatDate(reply.reply_dt) }}</div>
            <a v-if="reply.reply_attach" :href="reply.reply_attach" target="_blank"
              class="text-blue-500 underline text-sm mt-1 inline-block">
              {{ __('View Attachment') }}
            </a>
          </div>
          <div v-if="!studentReplies.length" class="text-sm text-ink-gray-4">
            {{ __('No replies found.') }}
          </div>
        </div>
      </div>

      <!-- Right: Grading + Feedback -->
      <div class="space-y-6">
        <div class="border rounded-lg p-5 bg-surface-white shadow-sm">
          <h2 class="text-lg font-semibold mb-4 text-ink-gray-9">{{ __('Grading') }}</h2>
          <label class="block text-sm font-medium text-gray-700 mb-1">{{ __('Grade') }}</label>
          <input v-model="grade" type="text" inputmode="decimal" :disabled="gradeLocked"
            class="block w-full rounded-md border-gray-300 shadow-sm text-sm mb-3"
            :class="gradeLocked ? 'bg-gray-100 text-ink-gray-5 cursor-not-allowed' : 'focus:border-indigo-500 focus:ring-indigo-500'" />
          <Button :variant="gradeLocked ? 'subtle' : 'solid'" @click="gradeLocked ? unlockGrade() : saveGrade()" class="w-full">
            {{ gradeLocked ? __('Edit Grade') : __('Save Grade') }}
          </Button>
        </div>

        <div class="border rounded-lg p-5 bg-surface-white shadow-sm">
          <h3 class="text-lg font-semibold mb-3 text-ink-gray-9">{{ __('Feedback') }}</h3>

          <!-- Comment thread -->
          <div v-if="gradingComments.length" class="space-y-3 mb-4">
            <div v-for="c in gradingComments" :key="c.name"
              class="p-3 rounded-lg text-sm"
              :class="c.author === user.data?.name
                ? 'bg-blue-50 border border-blue-200 ml-4'
                : 'bg-gray-50 border border-gray-200 mr-4'">
              <div class="flex items-center justify-between mb-1">
                <span class="font-medium text-ink-gray-7">{{ c.author_name }}</span>
                <span class="text-xs text-ink-gray-4">{{ formatDate(c.comment_dt) }}</span>
              </div>
              <div v-html="c.comment" class="prose-sm"></div>
            </div>
          </div>
          <div v-else class="text-sm text-ink-gray-4 mb-4">
            {{ __('No feedback yet. Write a comment below.') }}
          </div>

          <!-- New comment -->
          <LightEditor
            :id="'grading-comment-' + currentSubmission"
            :key="'gc-' + currentSubmission"
            ref="commentEditor"
            :placeholder="__('Write feedback...')"
            @change="(val) => newComment = val"
          />
          <div v-if="newComment && gradeEmpty" class="mt-2 text-sm text-ink-red-3">
            {{ __('Grade cannot be empty to provide grading feedback.') }}
          </div>
          <Button variant="solid" size="sm" class="mt-2" @click="postComment"
            :disabled="!newComment || gradeEmpty || addCommentResource.loading">
            {{ __('Send') }}
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup>
import { Breadcrumbs, createResource, Button, toast } from 'frappe-ui'
import { computed, onMounted, inject, watch, ref } from 'vue'
import { useRouter } from 'vue-router'
import dayjsModule from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import LightEditor from '@/components/LightEditor.vue'

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

const currentSubmission = ref(props.submissionName);
const submissionName = ref(props.submissionName);
const originalPosts = ref([]);
const studentReplies = ref([]);
const grade = ref('');
const gradeLocked = ref(false);
const gradingComments = ref([]);
const newComment = ref('');
const commentEditor = ref(null);

const title = createResource({
  url: 'frappe.client.get_value',
  params: {
    doctype: 'Discussion Activity',
    fieldname: 'discussion_name',
    filters: { name: props.discussionID },
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
    fields: ['name', 'student_name', 'member'],
    order_by: 'student_name asc',
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
  makeParams() {
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
  makeParams() {
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

// Fetch submission doc (for saved grade)
const submissionDetail = createResource({
  url: 'frappe.client.get_value',
  auto: false,
  onSuccess(data) {
    if (data) {
      const isGraded = data.status === 'Graded';
      grade.value = isGraded ? data.grade : '';
      gradeLocked.value = isGraded;
    }
  },
});

const fetchSubmissionDetail = () => {
  if (currentSubmission.value) {
    submissionDetail.submit({
      doctype: 'Discussion Submission',
      filters: { name: currentSubmission.value },
      fieldname: ['grade', 'status'],
    });
  }
};

// Grading comments
const commentsResource = createResource({
  url: 'seminary.seminary.api.get_grading_comments',
  auto: false,
  onSuccess(data) {
    gradingComments.value = data || [];
  },
});

const fetchComments = () => {
  if (currentSubmission.value) {
    commentsResource.submit({ submission_name: currentSubmission.value });
  }
};

const gradeEmpty = computed(() => !grade.value && grade.value !== 0)

const addCommentResource = createResource({
  url: 'seminary.seminary.api.add_grading_comment',
  onSuccess() {
    newComment.value = '';
    commentEditor.value?.clear();
    fetchComments();
  },
  onError(err) {
    toast.error(err.messages?.[0] || err);
  },
});

const postComment = async () => {
  if (!newComment.value || gradeEmpty.value) return;
  try {
    await submissionDoc.submit({
      submission_name: currentSubmission.value,
      grade: grade.value,
    });
    await addCommentResource.submit({
      submission_name: currentSubmission.value,
      comment: newComment.value,
    });
  } catch (e) {
    // errors handled by individual resource onError callbacks
  }
};

watch(currentSubmission, (newSubmission) => {
  submissionName.value = newSubmission;
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
      fetchComments();
      fetchSubmissionDetail();
    }
  }
);

const course = createResource({
  url: 'seminary.seminary.utils.get_course_details',
  cache: ['course', props.courseName],
  params: { course: props.courseName },
  auto: true,
})

const submissionDoc = createResource({
  url: 'seminary.seminary.api.save_discussion_submission_grade',
});

const saveGrade = async () => {
  if (gradeEmpty.value) {
    toast.error(__('Please enter a grade.'));
    return;
  }
  await submissionDoc.submit({
    submission_name: currentSubmission.value,
    grade: grade.value,
  });
  gradeLocked.value = true;
};

const unlockGrade = () => {
  gradeLocked.value = false;
};

const breadcrumbs = computed(() => [
  { label: __('Courses'), route: { name: 'Courses' } },
  { label: course?.data?.course, route: { name: 'CourseDetail', params: { courseName: props.courseName } } },
  { label: __('Gradebook'), route: { name: 'Gradebook', params: { courseName: props.courseName } } },
  { label: __('Discussion Submissions'), route: { name: 'DiscussionActivitySubmissionCS', params: { courseName: props.courseName, discussionID: props.discussionID } } },
])
</script>
