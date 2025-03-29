<template>
  <div v-if="isExamLoaded">
    <!-- Exam Header -->
    <div class="bg-blue-200 space-y-1 py-4 px-3 mb-4 rounded-md text-lg text-ink-blue-900">
      <div class="leading-5">
        {{ `This exam consists of ${exam.data.questions.length}` }}
        {{ exam.data.questions.length === 1 ? 'question' : 'questions' }}.
      </div>
      <div v-if="exam.data?.duration" class="leading-5">
				{{
					`Please ensure that you complete all the questions in ${exam.data.duration} minutes.`
				}}
			</div>
			<div v-if="exam.data?.duration" class="leading-5">
				{{
					(
						'If you fail to do so, the exam will be automatically submitted when the timer ends.'
					)
				}}
			</div>
    </div>

  

    <!-- Full Exam Mode -->
    <div>
      <div class="border text-center p-20 rounded-md">
  <div class="font-semibold text-lg mt-3 mb-3">
    {{ exam.data.title }}
  </div>
  <router-link
    v-if="is_instructor()"
    :to="{
      name: 'ExamForm',
      params: {
        examID: exam.data.name,
      },
    }"
    class="flex items-center text-gray-400 mb-3 mr-4 hover:text-gray-600"
  >
    <SquarePen class="w-5 h-5 mr-2" />
    <span class="tooltip" data-tooltip="Edit this exam">Edit</span>
  </router-link>
  
      <div v-for="(question, index) in exam.data.questions" :key="question.name" class="border rounded-md p-5 mb-4">
        <div class="flex justify-between">
          <div class="text-sm text-ink-gray-5">
            <span class="mr-2">{{ `Question ${index + 1}` }}:</span>
          </div>
          <div class="text-ink-gray-9 text-sm font-semibold">
            {{ question.points }} {{ question.points === 1 ? 'Point' : 'Points' }}
          </div>
        </div>
        <div class="text-ink-gray-9 text-left font-semibold mt-2 leading-5">
          <div v-html="question.question_detail || 'No question detail provided.'"></div>
        </div>
        <div class="mt-4">
          <textarea
            v-model="answers[question.name]"
            class="border rounded-md p-2 w-full"
            placeholder="Type your answer here"
            @change="(val) => updateAnswer(question.name, val)" 
          />
        </div>
      </div>
      <div class="text-center mt-4">
        <Button @click="submitExam">
          <span>{{ 'Submit Your Exam' }}</span>
        </Button>
      </div>
    </div>
  </div>
  </div>
</template>

<script setup>
import {Badge, Button, call, createResource, TextEditor, FormControl, frappeRequest} from 'frappe-ui'
import { ref, watch, reactive, inject, computed, toRaw } from 'vue'
import { createToast, showToast } from '@/utils/'
import { CheckCircle, XCircle, MinusCircle, SquarePen } from 'lucide-vue-next'
import { timeAgo } from '@/utils'
import { useRouter } from 'vue-router'
import ProgressBar from '@/components/ProgressBar.vue'
const user = inject('$user')
const timer = ref(0);
let timerInterval = null;
const elapsedTime = ref(0);
const answer = ref('');
const answers = ref({}); // Use ref instead of reactive
const questions = ref([]);
const fullExamMode = ref(true); // Always in full exam mode
const router = useRouter()
let user_is_instructor = false
// Props
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
  if (!data) {
    console.error('Exam data is null or undefined.');
    return null;
  }
  data.duration = parseInt(data.duration) || 0;
  return data;
},
onSuccess(data) {
      if (data) {
        console.log('Loaded exam data:', data); // Debugging
        data.questions = data.questions || []; // Ensure questions is always an array
          // populateQuestions();
          // setupTimer();
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
console.log('Exam data on isExamLoaded:', exam.data); // Debugging
return !!exam.data;
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

const is_instructor = () => {
  console.log('Fetching instructors of course:', router.currentRoute.value.params.courseName); // Debugging
  if (instructors.data) {
    instructors.data.forEach((instructor) => {
      if (instructor.user === user.data?.name) {
        user_is_instructor = true;
      }
    });
  }
  return user_is_instructor;
};

// // Populate questions (shuffle and limit)
// const populateQuestions = () => {
//   if (!exam.data || !exam.data.questions) {
//     console.warn('No questions found in exam data.'); // Debugging
//     return;
//   }

//   const data = exam.data;
//   if (data.shuffle_questions) {
//         // Shuffle the questions
//         const shuffledQuestions = shuffleArray([...data.questions]); // Use a copy of the array
//         // Limit the number of questions if required
//         questions.value = data.limit_questions_to
//             ? shuffledQuestions.slice(0, data.limit_questions_to)
//             : shuffledQuestions;
//     } else {
//         // Use the original questions if no shuffle is required
//         questions.value = data.questions;
//     }
  
// 	console.log("Populated questions:", questions)
// };

// Timer setup
const setupTimer = () => {
  if (exam.data.duration) {
    timer.value = exam.data.duration * 60;
    timerInterval = setInterval(() => {
      timer.value--;
      elapsedTime.value++;
      if (timer.value <= 0) {
        clearInterval(timerInterval);
        submitExam();
      }
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
console.log('Answers updated:', newAnswers);
}, { deep: true });

const get_answers = () => {

const rawAnswers = toRaw(answers.value); // Extract plain data from the reactive object
return Object.entries(rawAnswers).map(([questionName, answer]) => ({
  question: questionName,
  answer: answer,
}));
};

const updateAnswer = (questionName, value) => {
answers[questionName] = value;
};

// Submit exam
const submitExam = async () => {
try {
  const submittedAnswers = get_answers();
  console.log('Submitting exam with answers:', submittedAnswers);
  console.log("Course Name:", router.currentRoute.value.params.courseName);

  //  API call
  await call('seminary.seminary.doctype.exam_submission.exam_submission.create_exam_submission', {
    exam: props.examName,
    course: router.currentRoute.value.params.courseName,
    member: user.data?.name,
    answers: submittedAnswers,
  });

  showToast('Success', 'Your exam was submitted successfully.', 'check');
  clearInterval(timerInterval);
} catch (error) {
  console.error('Error during exam submission:', error);
  showToast('Error', 'Failed to submit the exam.', 'x');
}
};


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