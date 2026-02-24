<template>
  <div v-if="isExamLoaded">
    <!-- Exam Header -->
    <div v-if="!hasSubmittedExam" class="bg-blue-200 space-y-1 py-4 px-3 mb-4 rounded-md text-lg text-ink-blue-900">
      <div class="leading-5">
        {{ __('This exam consists of ') + exam.data.questions.length }}
        {{ exam.data.questions.length === 1 ? __('question') : __('questions') }}.
      </div>
      <div v-if="exam.data?.duration" class="leading-5">
        {{
          `Please ensure that you complete all the questions in ${exam.data.duration} minutes.`
        }}
      </div>
      <div v-if="exam.data?.duration" class="leading-5">
        {{
          (
            __('If you fail to do so, the exam will be automatically submitted when the timer ends.')

          )
        }}
      </div>
    </div>

    <div v-if="hasSubmittedExam && (submission_anystatus?.data || attempts.data?.[0])"
      class="space-y-4 border p-5 rounded-md">
      <Discussions :title="'Exam Comments'" :doctype="'Exam Submission'"
        :docname="submission_anystatus?.data?.name || attempts.data?.[0]?.name"
        :key="submission_anystatus?.data?.name || attempts.data?.[0]?.name" type="single" />
    </div>

    <div v-if="exam.data.duration && !hasSubmittedExam" class="flex flex-col space-x-1 my-4">
      <div class="mb-2">
        <span class=""> {{ __('Time') }}: </span>
        <span class="font-semibold">
          {{ formatTimer(timer) }}
        </span>
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
          params: {
            examID: exam.data.name,
          },
        }" class="flex items-center text-gray-400 mb-3 mr-4 hover:text-gray-600">
          <SquarePen class="w-5 h-5 mr-2" />
          <span class="tooltip" data-tooltip="Edit this exam">Edit</span>
        </router-link>
        <div v-if="fullExamMode && !hasSubmittedExam" class="flex items-center gap-2 mb-4">
    <div v-if="isSaving" class="text-sm text-gray-500">
        {{ __('Saving...') }}
    </div>
    <div v-else-if="submissionName" class="text-sm text-green-600">
        {{ __('Draft saved') }}
    </div>
</div>
        <div v-for="(question, index) in exam.data.questions" :key="question.name"
          class="relative border rounded-md p-5 mb-4">
          <div
            class="absolute -top-3 -left-3 bg-gray-600 text-white rounded-full w-8 h-8 flex items-center justify-center text-sm">
            {{ index + 1 }}
          </div>


          <div class="text-ink-gray-9 text-sm font-semibold text-right">
            {{ question.points }} {{ question.points === 1 ? __('Point') : __('Points') }}
          </div>

          <div class="text-ink-gray-9 text-left font-semibold mt-2 leading-5">
            <div v-html="question.question_detail || __('No question detail provided.')"></div>
          </div>
          <div class="mt-4">
            <RichTextInput v-if="answers && answers[question.name] !== undefined" :content="answers[question.name]"
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
</template>

<script setup>
import { Button, call, createResource, toast } from 'frappe-ui'
import { ref, watch, inject, computed, toRaw, onMounted, onBeforeUnmount } from 'vue'
import { CheckCircle, XCircle, MinusCircle, SquarePen } from 'lucide-vue-next'
import { timeAgo } from '@/utils'
import { useRouter } from 'vue-router'
import ProgressBar from '@/components/ProgressBar.vue'
import ExamGraded from '@/components/ExamGraded.vue'
import Discussions from '@/components/Discussions.vue'
import RichTextInput from '@/components/RichTextInput.vue'

const user = inject('$user')
const timer = ref(0);
let timerInterval = null;
const elapsedTime = ref(0);
const answer = ref('');
const answers = ref({}); // Use ref instead of reactive
const questions = ref([]);
const fullExamMode = ref(false); // Always in full exam mode
const router = useRouter()
let user_is_instructor = false
let isReloading = false
const editorKey = ref({}); // This will hold unique keys for each editor instance

const ensureAnswersInitialized = (questionsList = []) => {
  const existingAnswers = { ...answers.value }
  const initialized = {}

  questionsList.forEach((question) => {
    const current = existingAnswers[question.name]
    initialized[question.name] = typeof current === 'string' ? current : ''
  })

  answers.value = initialized
}
// const socket = inject('$socket')

// if (!socket) {
//   console.error('Socket connection not found in Exam.vue. Ensure $socket is provided.');
// } else {
//   console.log('Socket connection established in Exam.vue:', socket);

//   socket.on('new_discussion_topic', (data) => {
//     console.log('New discussion topic received:', data);
//   });
// }
// Props
const props = defineProps({
  examName: {
    type: String,
    required: true,
  },

});
// console.log('Exam Name (PROPS):', props.examName); // Debugging log

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
    if (!data) {
      console.error('Exam data is null or undefined.');
      return null;
    }
    data.duration = parseInt(data.duration) || 0;
    return data;
  },
  onSuccess(data) {
    if (data) {
      // console.log('Loaded exam data:', data); // Debugging
      // console.log('Exam Name:', exam.data?.name); // Debugging log
      // console.log('User Name:', user.data?.name); // Debugging log
      data.questions = data.questions || []; // Ensure questions is always an array
      ensureAnswersInitialized(data.questions);

      populateQuestions();
      setupTimer();
    } else {
      console.error("Failed to load exam data."); // Debugging
    }
  },
  onError(err) {
    console.error("Error loading exam data:", err); // Debugging
  },
});

// Check if exam data is loaded
const isExamLoaded = computed(() => {
  // console.log('Exam data on isExamLoaded:', exam.data); // Debugging
  return !!exam.data;
});

const hasSubmittedExam = computed(() => {
  return attempts.data?.length > 0;
});

const instructors = createResource({
  url: 'seminary.seminary.utils.get_instructors',
  makeParams(values) {
    const courseName = router.currentRoute.value.params.courseName;
    if (!courseName) {
      console.error('Course name is undefined in route parameters.');
      return {};
    }
    return {
      course: courseName,
    };
  },
  auto: true,
});

watch(
  () => instructors.data,
  (list) => {
    if (!Array.isArray(list)) {
      return;
    }
    const wasInstructor = user_is_instructor;
    user_is_instructor = list.some((instructor) => instructor.user === user.data?.name);
    if (!wasInstructor && user_is_instructor && exam.data?.questions?.length) {
      ensureAnswersInitialized(exam.data.questions);
    }
  },
);

const is_instructor = () => {
  // console.log('Fetching instructors of course:', router.currentRoute.value.params.courseName); // Debugging
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
  if (!exam.data || !exam.data.questions) {
    return
  }

  const data = exam.data
  let selectedQuestions

  if (data.shuffle_questions) {
    // Work with a plain copy, not reactive
    const plainQuestions = JSON.parse(JSON.stringify(data.questions))
    const shuffled = shuffleArray(plainQuestions)
    selectedQuestions = data.limit_questions_to
      ? shuffled.slice(0, data.limit_questions_to)
      : shuffled
  } else {
    selectedQuestions = data.questions
  }

  // Replace the questions array once, not mutate it
  exam.data.questions = selectedQuestions
  ensureAnswersInitialized(selectedQuestions)
}

// Timer setup
let timerStartTime = null; // Store the start time
const startTimer = () => {
  if (exam.data.duration) {
    // If duration is set, initialize the timer with the duration
    timer.value = exam.data.duration * 60; // Total duration in seconds
    timerStartTime = Date.now(); // Record the start time
    const endTime = timerStartTime + timer.value * 1000; // Calculate the end time

    timerInterval = setInterval(() => {
      const currentTime = Date.now();
      const remainingTime = Math.max(0, Math.floor((endTime - currentTime) / 1000)); // Calculate remaining time

      timer.value = remainingTime; // Update the timer value
      elapsedTime.value = exam.data.duration * 60 - remainingTime; // Calculate elapsed time

      if (remainingTime <= 0) {
        clearInterval(timerInterval);
        submitExam(); // Automatically submit the exam when the timer ends
      }
    }, 1000);
  } else {
    // If duration is null, track elapsed time only
    timerStartTime = Date.now(); // Record the start time
    timerInterval = setInterval(() => {
      const currentTime = Date.now();
      elapsedTime.value = Math.floor((currentTime - timerStartTime) / 1000); // Calculate elapsed time in seconds
    }, 1000);
  }
};

// Format timer
const formatTimer = (seconds) => {
  const mins = Math.floor(seconds / 60).toString().padStart(2, '0');
  const secs = (seconds % 60).toString().padStart(2, '0');
  return `${mins}:${secs}`;
};

// Timer progress
const timerProgress = computed(() => {
  return (timer.value / (exam.data.duration * 60)) * 100;
});

// Shuffle array utility
const shuffleArray = (array) => {
  for (let i = array.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [array[i], array[j]] = [array[j], array[i]];
  }
  return array;
};

watch(answers, (newAnswers) => {
  //console.log('Answers updated:', newAnswers);
}, { deep: true });

const get_answers = () => {

  const rawAnswers = toRaw(answers.value); // Extract plain data from the reactive object
  return Object.entries(rawAnswers).map(([questionName, answer]) => ({
    question: questionName,
    answer: answer,
  }));
};

const updateAnswer = (questionName, value) => {
  answers.value[questionName] = value

  // Auto-save after 2 seconds of inactivity
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
      fields: ['name', 'creation'],
      order_by: 'creation desc',
    };
  },
  auto: true,
  transform(data) {

    //console.log('Fetched attempts:', data); // Debugging log
    data.forEach((submission, index) => {
      submission.creation = timeAgo(submission.creation);
      submission.idx = index + 1;
    });
  },
});

watch(
  () => attempts.data,
  (newData) => {
    console.log('Attempts data updated:', newData); // Debugging log
  }
);
// Debounced auto-save
let saveTimer = null
const isSaving = ref(false)
const submissionName = ref(null)  // Track the created submission


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
// Submit exam
const submitExam = async () => {
  try {
    // Save first, then submit
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

const startExam2 = () => {
  localStorage.removeItem(exam.data.title);
  fullExamMode.value = true; // Set full exam mode flag
  startTimer();
  ensureAnswersInitialized(exam.data?.questions || []);
  // all_questions_details.reload(); // Ensure the resource is reloaded

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
  auto: false, // Disable auto-fetch
  transform(data) {
    console.log('Fetched submission data:', data); // Debugging log
    return data;
  },
  onError(err) {
    console.error('Error fetching submission:', err); // Debugging log
  },
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
  auto: false, // Disable auto-fetch
  transform(data) {
    console.log('Fetched submission AnyStatus:', data.name); // Debugging log
    return data;
  },
  onError(err) {
    console.error('Error fetching submission:', err); // Debugging log
  },
});

const beforeUnloadHandler = (e) => {
    if (fullExamMode.value && !hasSubmittedExam.value) {
        e.preventDefault()
        e.returnValue = ''  // Required for Chrome
    }
}

// Vue Router navigation guard
const removeRouterGuard = router.beforeEach((to, from, next) => {
    if (fullExamMode.value && !hasSubmittedExam.value) {
        const confirmed = window.confirm(
            __('Leaving this page will automatically submit your exam. Are you sure you want to leave?')
        )
        if (confirmed) {
            // Auto-submit before leaving
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
    removeRouterGuard()  // Clean up the navigation guard
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