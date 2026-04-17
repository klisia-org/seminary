<template>
  <div v-if="isExamLoaded" class="grid" :class="hasSubmittedExam && examSubmissionName ? 'md:grid-cols-[70%,30%]' : ''">
    <!-- Left / Main column -->
    <div>
      <!-- Exam Header -->
      <div v-if="!hasSubmittedExam" class="bg-surface-blue-2 space-y-1 py-4 px-3 mb-4 rounded-md text-lg text-ink-blue-2">
        <div class="leading-5">
          {{ __('This exam consists of ') + exam.data.questions.length }}
          {{ exam.data.questions.length === 1 ? __('question') : __('questions') }}.
        </div>
        <div v-if="exam.data?.duration" class="leading-5">
          {{ `Please ensure that you complete all the questions in ${exam.data.duration} minutes.` }}
        </div>
        <div v-if="exam.data?.duration" class="leading-5">
          {{ __('If you fail to do so, the exam will be automatically submitted when the timer ends.') }}
        </div>
      </div>

      <div v-if="exam.data.duration && !hasSubmittedExam" class="flex flex-col space-x-1 my-4">
        <div class="mb-2">
          <span>{{ __('Time') }}: </span>
          <span class="font-semibold">{{ formatTimer(timer) }}</span>
        </div>
        <ProgressBar :progress="timerProgress" />
      </div>

      <!-- Start Screen -->
      <div v-if="!fullExamMode && !is_instructor()">
        <div class="border text-center p-20 rounded-md">
          <div class="font-semibold text-lg">
            {{ exam.data.title }}
          </div>
          <Button v-if="exam.data.qbyquestion && !hasSubmittedExam" @click="startExam" class="mt-2">
            <span>{{ __('Start') }}</span>
          </Button>
          <Button v-else-if="!hasSubmittedExam" @click="startExam2" class="mt-2">
            <span>{{ __('Start Exam') }}</span>
          </Button>
          <div v-else-if="hasSubmittedExam && submission?.data?.name" class="w-full max-w-4xl mx-auto py-5">
            <ExamGraded :submission="submission.data.name" />
          </div>
          <div v-else>
            {{ __('You have already submitted this exam. As soon as it is graded, you will see the feedback here.') }}
          </div>
        </div>
      </div>

      <!-- Full Exam Mode -->
      <div v-if="fullExamMode || is_instructor()">
        <div class="border text-center p-20 rounded-md">
          <div class="font-semibold text-lg text-ink-gray-9 mt-3 mb-3">
            {{ exam.data.title }}
          </div>
          <router-link v-if="is_instructor()" :to="{
            name: 'ExamForm',
            params: { examID: exam.data.name },
          }" class="flex items-center text-ink-gray-4 mb-3 mr-4 hover:text-ink-gray-6">
            <SquarePen class="w-5 h-5 mr-2" />
            <span class="tooltip" data-tooltip="Edit this exam">Edit</span>
          </router-link>
          <div v-if="fullExamMode && !hasSubmittedExam" class="flex items-center gap-2 mb-4">
            <div v-if="isSaving" class="text-sm text-ink-gray-5">
              {{ __('Saving...') }}
            </div>
            <div v-else-if="submissionName" class="text-sm text-ink-green-3">
              {{ __('Draft saved') }}
            </div>
          </div>
          <div v-for="(question, index) in exam.data.questions" :key="question.name"
            class="relative border rounded-md p-5 mb-4">
            <div
              class="absolute -top-3 -left-3 bg-surface-gray-7 text-ink-white rounded-full w-8 h-8 flex items-center justify-center text-sm">
              {{ index + 1 }}
            </div>
            <div class="text-ink-gray-9 text-sm font-semibold text-right">
              {{ question.points }} {{ question.points === 1 ? __('Point') : __('Points') }}
            </div>
            <div class="text-ink-gray-9 text-left font-semibold mt-2 leading-5">
              <div v-html="question.question_detail || __('No question detail provided.')"></div>
            </div>
            <div class="mt-4">
              <LightEditor v-if="answers && answers[question.name] !== undefined" :content="answers[question.name]"
                :id="question.name" :placeholder="__('Type your answer here')"
                @change="(val) => updateAnswer(question.name, val)" />
            </div>
          </div>
          <div class="text-center mt-4">
            <Button @click="submitExam">
              <span>{{ __('Submit Your Exam') }}</span>
            </Button>
          </div>
        </div>
      </div>
    </div>

    <!-- Right column: Exam Comments (only when submitted) -->
    <div v-if="hasSubmittedExam && examSubmissionName" class="p-5 border-l">
      <h3 class="text-lg font-semibold text-ink-gray-9 mb-4">{{ __('Exam Comments') }}</h3>
      <div v-if="gradingComments.length" class="space-y-3 mb-4">
        <div v-for="c in gradingComments" :key="c.name"
          class="p-3 rounded-lg text-sm"
          :class="c.author === user.data?.name
            ? 'bg-surface-blue-1 text-ink-blue-2 border border-outline-blue-1 ml-4'
            : 'bg-surface-gray-1 text-ink-gray-8 border border-outline-gray-1 mr-4'">
          <div class="flex items-center justify-between mb-1">
            <span class="font-medium text-ink-gray-7">{{ c.author_name }}</span>
            <span class="text-xs text-ink-gray-4">{{ timeAgo(c.comment_dt) }}</span>
          </div>
          <div v-html="c.comment" class="prose-sm"></div>
        </div>
      </div>
      <div v-else class="text-sm text-ink-gray-4 mb-4">
        {{ __('No comments yet.') }}
      </div>
      <LightEditor
        :id="'exam-comment-' + examSubmissionName"
        :key="'ec-' + examSubmissionName"
        ref="commentEditor"
        :placeholder="__('Write a comment...')"
        @change="(val) => newComment = val"
      />
      <Button variant="solid" size="sm" class="mt-2" @click="postExamComment"
        :disabled="!newComment || addExamCommentResource.loading">
        {{ __('Send') }}
      </Button>
    </div>
  </div>
</template>

<script setup>
import { Button, call, createResource, toast } from 'frappe-ui'
import { ref, watch, inject, computed, toRaw, onMounted, onBeforeUnmount } from 'vue'
import { SquarePen } from 'lucide-vue-next'
import { timeAgo } from '@/utils'
import { useRouter } from 'vue-router'
import ProgressBar from '@/components/ProgressBar.vue'
import ExamGraded from '@/components/ExamGraded.vue'
import LightEditor from '@/components/LightEditor.vue'

const user = inject('$user')
const timer = ref(0);
let timerInterval = null;
const elapsedTime = ref(0);
const answer = ref('');
const answers = ref({});
const questions = ref([]);
const fullExamMode = ref(false);
const router = useRouter()
let user_is_instructor = false
let isReloading = false
const editorKey = ref({});

// Grading comments state
const gradingComments = ref([])
const newComment = ref('')
const commentEditor = ref(null)

const ensureAnswersInitialized = (questionsList = []) => {
  const existingAnswers = { ...answers.value }
  const initialized = {}

  questionsList.forEach((question) => {
    const current = existingAnswers[question.name]
    initialized[question.name] = typeof current === 'string' ? current : ''
  })

  answers.value = initialized
}

const props = defineProps({
  examName: {
    type: String,
    required: true,
  },
});

// Exam resource
const exam = createResource({
  url: 'frappe.client.get',
  makeParams(values) {
    return {
      doctype: 'Exam Activity',
      name: props.examName,
    };
  },
  cache: ['exam', props.examName],
  auto: true,
  transform(data) {
    if (!data) return null;
    data.duration = parseInt(data.duration) || 0;
    return data;
  },
  onSuccess(data) {
    if (data) {
      data.questions = data.questions || [];
      ensureAnswersInitialized(data.questions);
      populateQuestions();
    }
  },
});

// Check if exam data is loaded
const isExamLoaded = computed(() => !!exam.data);

const hasSubmittedExam = computed(() => {
  if (attempts.data?.length > 0) {
    return attempts.data.some(a => a.status !== 'Not Submitted')
  }
  return false
})

const examSubmissionName = computed(() => {
  return submission_anystatus.data?.name
    || attempts.data?.find(a => a.status !== 'Not Submitted')?.name
    || null
})

const instructors = createResource({
  url: 'seminary.seminary.utils.get_instructors',
  makeParams(values) {
    const courseName = router.currentRoute.value.params.courseName;
    if (!courseName) return {};
    return { course: courseName };
  },
  auto: true,
});

watch(
  () => instructors.data,
  (list) => {
    if (!Array.isArray(list)) return;
    const wasInstructor = user_is_instructor;
    user_is_instructor = list.some((instructor) => instructor.user === user.data?.name);
    if (!wasInstructor && user_is_instructor && exam.data?.questions?.length) {
      ensureAnswersInitialized(exam.data.questions);
    }
  },
);

const is_instructor = () => {
  if (instructors.data) {
    instructors.data.forEach((instructor) => {
      if (instructor.user === user.data?.name) {
        user_is_instructor = true;
      }
    });
  }
  return user_is_instructor;
};

const populateQuestions = () => {
  if (!exam.data || !exam.data.questions) return

  const data = exam.data
  let selectedQuestions

  if (data.shuffle_questions) {
    const plainQuestions = JSON.parse(JSON.stringify(data.questions))
    const shuffled = shuffleArray(plainQuestions)
    selectedQuestions = data.limit_questions_to
      ? shuffled.slice(0, data.limit_questions_to)
      : shuffled
  } else {
    selectedQuestions = data.questions
  }

  exam.data.questions = selectedQuestions
  ensureAnswersInitialized(selectedQuestions)
}

// Timer setup
let timerStartTime = null;
const startTimer = () => {
  if (exam.data.duration) {
    timer.value = exam.data.duration * 60;
    timerStartTime = Date.now();
    const endTime = timerStartTime + timer.value * 1000;

    timerInterval = setInterval(() => {
      const currentTime = Date.now();
      const remainingTime = Math.max(0, Math.floor((endTime - currentTime) / 1000));

      timer.value = remainingTime;
      elapsedTime.value = exam.data.duration * 60 - remainingTime;

      if (remainingTime === 300) {
        toast.warning(__('5 minutes remaining!'))
      }
      if (remainingTime === 60) {
        toast.warning(__('1 minute remaining! Your exam will be auto-submitted.'))
      }
      if (remainingTime <= 0) {
        clearInterval(timerInterval)
        toast.warning(__('Time is up! Submitting your exam...'))
        submitExam()
      }
    }, 1000);
  } else {
    timerStartTime = Date.now();
    timerInterval = setInterval(() => {
      const currentTime = Date.now();
      elapsedTime.value = Math.floor((currentTime - timerStartTime) / 1000);
    }, 1000);
  }
};

const formatTimer = (seconds) => {
  const mins = Math.floor(seconds / 60).toString().padStart(2, '0');
  const secs = (seconds % 60).toString().padStart(2, '0');
  return `${mins}:${secs}`;
};

const timerProgress = computed(() => {
  return (timer.value / (exam.data.duration * 60)) * 100;
});

const shuffleArray = (array) => {
  for (let i = array.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [array[i], array[j]] = [array[j], array[i]];
  }
  return array;
};

watch(answers, () => {}, { deep: true });

const get_answers = () => {
  const rawAnswers = toRaw(answers.value);
  return Object.entries(rawAnswers).map(([questionName, answer]) => ({
    question: questionName,
    answer: answer,
  }));
};

const updateAnswer = (questionName, value) => {
  answers.value[questionName] = value
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    autoSave()
  }, 2000)
}

const attempts = createResource({
  url: 'frappe.client.get_list',
  makeParams(values) {
    return {
      doctype: 'Exam Submission',
      filters: {
        member: user.data?.name,
        exam: props.examName,
      },
      fields: ['name', 'creation', 'status'],
      order_by: 'creation desc',
    };
  },
  auto: true,
  transform(data) {
    data.forEach((submission, index) => {
      submission.creation = timeAgo(submission.creation);
      submission.idx = index + 1;
    });
  },
});

// Debounced auto-save
let saveTimer = null
const isSaving = ref(false)
const submissionName = ref(null)


const autoSave = async () => {
  if (isSaving.value || hasSubmittedExam.value) return
  isSaving.value = true

  try {
    const submittedAnswers = get_answers()
    const timeTaken = exam.data.duration
      ? exam.data.duration * 60 - (timer.value || 0)
      : elapsedTime.value || 0

    const result = await call(
      'seminary.seminary.doctype.exam_submission.exam_submission.save_exam_draft',
      {
        exam: props.examName,
        course: router.currentRoute.value.params.courseName,
        member: user.data?.name,
        answers: submittedAnswers,
        time_taken: timeTaken,
        submission_name: submissionName.value,
      }
    )

    submissionName.value = result.name
  } catch (error) {
    console.error('Auto-save failed:', error)
  } finally {
    isSaving.value = false
  }
}

const submitExam = async () => {
  try {
    await autoSave()

    if (!submissionName.value) {
      toast.error(__('No saved draft found. Please answer at least one question.'))
      return
    }

    await call(
      'seminary.seminary.doctype.exam_submission.exam_submission.submit_exam',
      {
        submission_name: submissionName.value,
      }
    )

    toast.success(__('Your exam was submitted successfully.'))
    clearInterval(timerInterval)
    fullExamMode.value = false
    attempts.reload()
    submission.reload()
    submission_anystatus.reload()
  } catch (error) {
    console.error('Error submitting exam:', error)
    toast.error(error.messages?.[0] || error)
  }
}

const startExam = () => {
  activeQuestion.value = 1
  localStorage.removeItem(exam.data.title)
  startTimer()
  ensureAnswersInitialized(exam.data?.questions || []);
}

const startExam2 = async () => {
  localStorage.removeItem(exam.data.title)
  fullExamMode.value = true
  startTimer()
  ensureAnswersInitialized(exam.data?.questions || [])

  try {
    const existing = await call('frappe.client.get_value', {
      doctype: 'Exam Submission',
      fieldname: ['name', 'result'],
      filters: {
        exam: props.examName,
        member: user.data?.name,
        docstatus: 0,
      },
    })
    if (existing?.name) {
      submissionName.value = existing.name
      const draft = await call('frappe.client.get', {
        doctype: 'Exam Submission',
        name: existing.name,
      })
      if (draft?.result) {
        draft.result.forEach((r) => {
          if (answers.value.hasOwnProperty(r.question)) {
            answers.value[r.question] = r.answer || ''
          }
        })
      }
    }
  } catch (e) {
    // No existing draft found
  }
}

const submission = createResource({
  url: 'frappe.client.get_value',
  params: {
    doctype: 'Exam Submission',
    fieldname: 'name',
    filters: {
      exam: props.examName,
      member: user.data?.name,
      status: 'Graded',
    },
  },
  auto: false,
});


const submission_anystatus = createResource({
  url: 'frappe.client.get_value',
  params: {
    doctype: 'Exam Submission',
    fieldname: 'name',
    filters: {
      exam: props.examName,
      member: user.data?.name,
    },
  },
  auto: false,
});

// Grading comments resources
const commentsResource = createResource({
  url: 'seminary.seminary.doctype.exam_submission.exam_submission.get_exam_grading_comments',
  auto: false,
  onSuccess(data) {
    gradingComments.value = data || [];
  },
})

const fetchExamComments = () => {
  if (examSubmissionName.value) {
    commentsResource.submit({ submission_name: examSubmissionName.value })
  }
}

const addExamCommentResource = createResource({
  url: 'seminary.seminary.doctype.exam_submission.exam_submission.add_exam_grading_comment',
  onSuccess() {
    newComment.value = ''
    commentEditor.value?.clear()
    fetchExamComments()
  },
  onError(err) {
    toast.error(err.messages?.[0] || err)
  },
})

const postExamComment = () => {
  if (!newComment.value || !examSubmissionName.value) return
  addExamCommentResource.submit({
    submission_name: examSubmissionName.value,
    comment: newComment.value,
  })
}

// Fetch comments when submission name becomes available
watch(examSubmissionName, (name) => {
  if (name) fetchExamComments()
}, { immediate: true })

const beforeUnloadHandler = (e) => {
  if (fullExamMode.value && !hasSubmittedExam.value) {
    e.preventDefault()
    e.returnValue = ''
  }
}

const removeRouterGuard = router.beforeEach((to, from, next) => {
  if (fullExamMode.value && !hasSubmittedExam.value) {
    const confirmed = window.confirm(
      __('Leaving this page will automatically submit your exam. Are you sure you want to leave?')
    )
    if (confirmed) {
      submitExamBeforeLeave().then(() => next())
      return
    }
    next(false)
    return
  }
  next()
})

const submitExamBeforeLeave = async () => {
  try {
    await autoSave()
    if (submissionName.value) {
      await call(
        'seminary.seminary.doctype.exam_submission.exam_submission.submit_exam',
        { submission_name: submissionName.value }
      )
    }
    clearInterval(timerInterval)
  } catch (error) {
    console.error('Error auto-submitting on leave:', error)
  }
}

onMounted(() => {
  window.addEventListener('beforeunload', beforeUnloadHandler)
  submission.reload()
  submission_anystatus.reload()
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', beforeUnloadHandler)
  removeRouterGuard()
  if (timerInterval) {
    clearInterval(timerInterval)
  }
})

</script>

<style>
/* Tooltip styling */
.tooltip {
  position: relative;
  cursor: pointer;
}

.tooltip::after {
  content: attr(data-tooltip);
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  background-color: #333;
  color: #fff;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  white-space: nowrap;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.2s ease-in-out;
}

.tooltip:hover::after {
  opacity: 1;
  visibility: visible;
}
</style>
