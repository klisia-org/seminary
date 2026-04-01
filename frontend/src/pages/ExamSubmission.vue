<template>
  <header class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
    <Breadcrumbs v-if="submisisonDetails.doc" :items="breadcrumbs" />
    <div class="space-x-2">
      <Badge v-if="submisisonDetails.isDirty" :label="__('Not Saved')" variant="subtle" theme="orange" />
      <Button variant="solid" @click="validateSubmission()">
        {{ __('Save') }}
      </Button>
    </div>
  </header>
  <div class="flex justify-center text-xl font-bold text-gray-900 mt-3">
    {{ ExamTitle.data?.title }}
  </div>
  <div class="flex items-center justify-between mb-5">
    <!-- Previous Button -->
    <Button variant="subtle" :disabled="currentIndex === 0" @click="navigateToSubmission(currentIndex - 1)">
      {{ __('Previous') }}
    </Button>

    <!-- Dropdown for All Submissions -->
    <div class="w-1/3 mt-5">
      <label for="submissionDropdown" class="block text-sm font-medium text-gray-700">
        {{ __('Select Submission') }}
      </label>
      <select id="submissionDropdown" v-model="currentSubmission"
        @change="navigateToSubmissionByName(currentSubmission)"
        class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm">
        <option v-for="submission in submissionlist.data" :key="submission.name" :value="submission.name">
          {{ submission.member_name }}
        </option>
      </select>
    </div>

    <!-- Next Button -->
    <Button variant="subtle" :disabled="!submissionlist.data || currentIndex === submissionlist.data.length - 1"
      @click="navigateToSubmission(currentIndex + 1)">
      {{ __('Next') }}
    </Button>
  </div>
  <div v-if="submisisonDetails.doc" class="w-2/3 mx-auto py-5 space-y-5">
    <div class="grid grid-cols-3 gap-5">
      <!-- Left Section (2/3 width) -->
      <div class="col-span-2 space-y-4">
        <div class="text-xl font-semibold text-ink-gray-9">
          {{ submisisonDetails.doc.member_name }}
        </div>
        <div class="space-y-4 border p-5 rounded-md">
          <div class="flex items-center justify-between py-4">
            <!-- Exam Percentage -->
            <div class="text-center ml-5">
              <div class="text-3xl font-bold text-ink-gray-9">
                {{ submisisonDetails.doc.percentage || 0 }}%
              </div>
              <div class="text-sm text-ink-gray-5">
                Score
              </div>
            </div>

            <!-- Score and Time Taken -->
            <div class="text-center">
              <div class="text-3xl font-semibold text-ink-gray-9">
                {{ submisisonDetails.doc.score }}
              </div>
              <div class="text-sm text-ink-gray-5">
                {{ __('Out of') }} {{ submisisonDetails.doc.score_out_of }} {{ __('Points') }}
              </div>
            </div>
            <div class="text-center mr-5">
              <div class="text-3xl font-semibold text-ink-gray-9 mt-2">
                {{ formatTime(submisisonDetails.doc.time_taken) }}
              </div>
              <div class="text-sm text-ink-gray-5">
                {{ __('Time taken') }}
              </div>
            </div>
          </div>
        </div>

        <!-- Questions Section -->
        <div v-for="(row, index) in submisisonDetails.doc.result" :key="index" class="border p-5 rounded-md space-y-4">
          <!-- Question Title -->
          <div class="space-y-1">
            <div class="font-semibold text-ink-gray-9">
              {{ __('Question') }} {{ index + 1 }}:
            </div>
            <div class="leading-5 text-ink-gray-9" v-html="row.question_name"></div>
          </div>
          <!-- Answer -->
          <div class="leading-5 text-ink-gray-7 space-x-1">
            <span> {{ __('Your Answer') }}: </span>
            <span v-html="row.answer"></span>
          </div>
          <!-- Points and Buttons -->
          <div class="flex items-center justify-end space-x-5">
            <!-- Buttons for Auto-Grading -->
            <div class="flex items-center space-x-2">
              <Button variant="solid" theme="green" size="sm" @click="setPoints(row, row.points_out_of)">
                <Check class="w-4 h-4" />
              </Button>
              <Button variant="solid" theme="red" size="sm" @click="setPoints(row, 0)">
                <X class="w-4 h-4" />
              </Button>
            </div>

            <!-- Points Input -->
            <div class="flex flex-col items-end space-y-1">
              <div class="flex items-center space-x-2">
                <FormControl v-model="row.points" type="number" class="w-20 text-right"
                  @change="(val) => onPointsChange(row, val)" />
                <span class="text-sm text-ink-gray-7">
                  / {{ parseInt(row.points_out_of, 10) }} {{ __('Points') }}
                </span>
              </div>
              <span v-if="Number(row.points) > Number(row.points_out_of)" class="text-xs text-ink-red-3">
                {{ __('Grade cannot be greater than maximum') }}
              </span>
              <span v-else-if="Number(row.points) < 0" class="text-xs text-ink-red-3">
                {{ __('Grade cannot be negative') }}
              </span>
            </div>
          </div>
          <span> {{ __('Comments for this question') }}: </span>
          <LightEditor :key="row.name" :id="row.name" :content="row.comments" :editable="true"
            @change="(val) => onCommentChange(row, val)" />


        </div>
      </div>


      <!-- Right Section (1/3 width) -->
      <div class="col-span-1 space-y-4">
        <div class="space-y-4 border p-5 rounded-md">
          <div class="text-sm text-ink-gray-7">
            {{ __('Final grade is auto-calculated') }}
          </div>
          <FormControl v-model="submisisonDetails.doc.fudge_points" :label="__('Fudge Points')" :disabled="false" />
          <FormControl v-model="submisisonDetails.doc.status" :label="__('Status')" type="select" :options="[
            {
              label: __('Not Graded'),
              value: 'Not Graded',
            },
            {
              label: __('Graded'),
              value: 'Graded',
            },
          ]" :disabled="false" />
        </div>
        <div class="border rounded-lg p-5 bg-surface-white shadow-sm">
          <h3 class="text-lg font-semibold mb-3 text-ink-gray-9">{{ __('Exam Comments') }}</h3>
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
            {{ __('No comments yet.') }}
          </div>
          <LightEditor
            :id="'exam-gc-' + currentSubmission"
            :key="'egc-' + currentSubmission"
            ref="gcEditor"
            :placeholder="__('Write a comment...')"
            @change="(val) => newGradingComment = val"
          />
          <Button variant="solid" size="sm" class="mt-2" @click="postGradingComment"
            :disabled="!newGradingComment || addGradingCommentResource.loading">
            {{ __('Send') }}
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup>
import {
  createDocumentResource,
  createResource,
  Breadcrumbs,
  FormControl,
  Button,
  Badge,
  toast, call
} from 'frappe-ui'
import { computed, onBeforeUnmount, onMounted, inject, watch, ref } from 'vue'
import { useRouter } from 'vue-router'
import LightEditor from '@/components/LightEditor.vue'
import { Check, X } from 'lucide-vue-next'

const router = useRouter()
const user = inject('$user')

onMounted(() => {
  if (!user.data?.is_instructor && !user.data?.is_moderator)
    router.push({ name: 'Courses' })

  window.addEventListener('keydown', keyboardShortcut)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', keyboardShortcut)
})

const keyboardShortcut = (e) => {
  if (
    e.key === 's' &&
    (e.ctrlKey || e.metaKey) &&
    !e.target.classList.contains('ProseMirror')
  ) {
    saveSubmission()
    e.preventDefault()
  }
}

const props = defineProps({
  submission: {
    type: String,
    required: true,
  },
  courseName: {
    type: String,
    required: true,
  },
  examID: {
    type: String,
    required: true,
  },
})

const ExamTitle = createResource({
  url: 'frappe.client.get_value',
  params: {
    doctype: 'Exam Activity',
    fieldname: 'title',
    filters: {
      name: props.examID,
    },
  },
  auto: true,
})

const submissionlist = createResource({
  url: 'frappe.client.get_list',
  params: {
    doctype: 'Exam Submission',
    filters: [
      ['exam', '=', props.examID],
      ['course', '=', props.courseName],
    ],
    fields: ['name', 'member_name'], // Fetch only necessary fields
    order_by: 'member_name asc', // Order by member name
  },
  auto: true,
});

const submisisonDetails = createDocumentResource({
  doctype: 'Exam Submission',
  name: props.submission,
  auto: true,
})


const course = createResource({
  url: 'seminary.seminary.utils.get_course_details',
  cache: ['course', props.courseName],
  params: {
    course: props.courseName,
  },
  auto: true,
}) //Neded for the breadcrumbs

const breadcrumbs = computed(() => {
  let items = [{ label: __('Courses'), route: { name: 'Courses' } }]
  items.push({
    label: course?.data?.course,
    route: { name: 'CourseDetail', params: { courseName: props.courseName } },
  })
  items.push({
    label: __('Gradebook'),
    route: { name: 'Gradebook', params: { courseName: props.courseName } },
  })
  items.push({
    label: __('Exam Submissions'),
    route: { name: 'ExamSubmissionCS', params: { courseName: props.courseName, examID: props.examID } },
  })
  return items
})




const formatTime = (seconds) => {
  if (!seconds) return '00:00:00'; // Handle null or undefined values
  const hrs = Math.floor(seconds / 3600).toString().padStart(2, '0');
  const mins = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
  const secs = (seconds % 60).toString().padStart(2, '0');
  return `${hrs}:${mins}:${secs}`;
};
const clampPoints = (row) => {
  const max = Number(row.points_out_of)
  const val = Number(row.points)
  if (val > max) row.points = max
  else if (val < 0) row.points = 0
}

const setPoints = (row, points) => {
  row.points = points;
  row.graded = true;
  updateScoreAndPercentage()
};

const updateScoreAndPercentage = () => {
  // Calculate the total score by summing up all row.points
  const totalScore = (submisisonDetails.doc.result || []).reduce((sum, row) => {
    return sum + Number(row.points || 0); // Convert row.points to a number and default to 0 if undefined
  }, 0);

  // Update the score
  submisisonDetails.doc.score = totalScore;

  // Ensure score_out_of is treated as a float
  const scoreOutOf = parseFloat(submisisonDetails.doc.score_out_of) || 1; // Default to 1 to avoid division by 0
  const Fudge = parseFloat(submisisonDetails.doc.fudge_points) || 0; // Default to 0 if none
  // Calculate the exam percentage
  const percentage = ((totalScore / scoreOutOf) * 100) + Fudge;
  submisisonDetails.doc.percentage = parseFloat(percentage.toFixed(2)); // Ensure it's a float and round to 2 decimal places
};

// Recalculate only on fudge_points user edits (not initial load)
let fudgeInitialized = false
watch(
  () => submisisonDetails.doc?.fudge_points,
  () => {
    if (!fudgeInitialized) {
      fudgeInitialized = true
      return
    }
    updateScoreAndPercentage()
  }
)

const commentTimers = {}

const onCommentChange = (row, value) => {
  row.comments = value
  clearTimeout(commentTimers[row.name])
  commentTimers[row.name] = setTimeout(async () => {
    try {
      await call('seminary.seminary.doctype.exam_submission.exam_submission.save_exam_comment', {
        submission_name: props.submission,
        row_name: row.name,
        comments: value,
      })
    } catch (e) {
      console.error('Failed to auto-save comment:', e)
    }
  }, 1500)
}

const validateSubmission = async () => {
  // Find ungraded questions
  const ungradedQuestions = submisisonDetails.doc.result
    .map((row, index) => (!row.graded ? `Question ${index + 1}` : null))
    .filter((question) => question !== null);

  if (ungradedQuestions.length > 0) {
    // Show confirmation dialog for ungraded questions
    const confirmSave = confirm(
      __('The following questions need grading: {questions}. Do you want to save anyway?', { questions: ungradedQuestions.join(', ') })
    );

    if (!confirmSave) {
      // User canceled the save
      return;
    }
  } else {
    // If all questions are graded, set the status to 'Graded'
    submisisonDetails.doc.status = 'Graded';
  }

  // Proceed with saving
  try {
    await saveSubmission()
    toast.success(__('Submission saved successfully'))
  } catch (error) {
    console.error('Save failed:', error)
    toast.error(error.messages?.[0] || __('Failed to save'))
  }
};

const onPointsChange = (row, value) => {
  clampPoints(row)
  row.graded = true
  updateScoreAndPercentage()
};

const saveSubmission = async () => {
  await call('seminary.seminary.doctype.exam_submission.exam_submission.save_exam_grade', {
    submission_name: props.submission,
    status: submisisonDetails.doc.status,
    score: submisisonDetails.doc.score,
    percentage: submisisonDetails.doc.percentage,
    fudge_points: submisisonDetails.doc.fudge_points,
    result: submisisonDetails.doc.result.map(row => ({
      name: row.name,
      points: row.points,
      graded: row.graded,
      comments: row.comments || '',
    })),
  })
  await submisisonDetails.reload()
}

// Grading comments
const gradingComments = ref([])
const newGradingComment = ref('')
const gcEditor = ref(null)

const gradingCommentsResource = createResource({
  url: 'seminary.seminary.doctype.exam_submission.exam_submission.get_exam_grading_comments',
  auto: false,
  onSuccess(data) {
    gradingComments.value = data || []
  },
})

const fetchGradingComments = () => {
  if (currentSubmission.value) {
    gradingCommentsResource.submit({ submission_name: currentSubmission.value })
  }
}

const addGradingCommentResource = createResource({
  url: 'seminary.seminary.doctype.exam_submission.exam_submission.add_exam_grading_comment',
  onSuccess() {
    newGradingComment.value = ''
    gcEditor.value?.clear()
    fetchGradingComments()
  },
  onError(err) {
    toast.error(err.messages?.[0] || err)
  },
})

const postGradingComment = () => {
  if (!newGradingComment.value || !currentSubmission.value) return
  addGradingCommentResource.submit({
    submission_name: currentSubmission.value,
    comment: newGradingComment.value,
  })
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  const d = new Date(dateString)
  return d.toLocaleDateString(undefined, { dateStyle: 'medium' }) + ' ' + d.toLocaleTimeString(undefined, { timeStyle: 'short' })
}

const currentSubmission = ref(props.submission);
const currentIndex = computed(() =>
  submissionlist.data?.findIndex((submission) => submission.name === currentSubmission.value)
);

const navigateToSubmission = (index) => {
  if (index >= 0 && index < submissionlist.data.length) {
    const submission = submissionlist.data[index];
    router.push({
      name: 'ExamSubmission',
      params: {
        submission: submission.name,
        courseName: props.courseName,
        examID: props.examID,
      },
    });
  }
};

const navigateToSubmissionByName = (submissionName) => {
  const submission = submissionlist.data.find((sub) => sub.name === submissionName);
  if (submission) {
    router.push({
      name: 'ExamSubmission',
      params: {
        submission: submission.name,
        courseName: props.courseName,
        examID: props.examID,
      },
    });
  }
};

watch(currentSubmission, async (newSubmission) => {
  if (newSubmission) {
    submisisonDetails.name = newSubmission;
    await submisisonDetails.reload();
    fetchGradingComments();
  }
}, { immediate: true });
</script>
