<template>
    <div v-if="isExamLoaded">
      <!-- Exam Header -->
      <div class="bg-blue-200 space-y-1 py-4 px-3 mb-4 rounded-md text-lg text-ink-blue-900">
        <div class="leading-5">
          {{ `This exam consists of ${questions.length}` }}
          {{ questions.length === 1 ? 'question' : 'questions' }}.
        </div>
        <div v-if="exam.data?.duration" class="leading-5">
          {{
            `Please ensure that you complete all the questions in ${exam.data.duration} minutes.`
          }}
        </div>
      </div>
  
      <!-- Timer -->
      <div v-if="exam.data.duration" class="flex flex-col space-x-1 my-4">
        <div class="mb-2">
          <span>{{ 'Time' }}: </span>
          <span class="font-semibold">{{ formatTimer(timer) }}</span>
        </div>
        <ProgressBar :progress="timerProgress" />
      </div>
  
      <!-- Full Exam Mode -->
      <div>
        <div v-for="(question, index) in questions" :key="question.name" class="border rounded-md p-5 mb-4">
          <div class="flex justify-between">
            <div class="text-sm text-ink-gray-5">
              <span class="mr-2">{{ `Question ${index + 1}` }}:</span>
            </div>
            <div class="text-ink-gray-9 text-sm font-semibold">
              {{ question.points }} {{ question.points === 1 ? 'Point' : 'Points' }}
            </div>
          </div>
          <div class="text-ink-gray-9 font-semibold mt-2 leading-5">
            {{ question.question_detail || 'No question detail provided.' }}
          </div>
          <div class="mt-4">
            <TextEditor
              v-model="answers[index]"
              :content="answers[index]"
              @change="(val) => (answers[index] = val)"
              :editable="true"
              :fixedMenu="true"
              editorClass="prose-sm max-w-none border-b border-x bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[7rem]"
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
  </template>

<script setup>
import {Badge, Button, call, createResource, ListView, TextEditor, FormControl} from 'frappe-ui'
import { ref, watch, reactive, inject, computed } from 'vue'
import { createToast, showToast } from '@/utils/'
import { CheckCircle, XCircle, MinusCircle } from 'lucide-vue-next'
import { timeAgo } from '@/utils'
import { useRouter } from 'vue-router'
import ProgressBar from '@/components/ProgressBar.vue'

const timer = ref(0);
let timerInterval = null;
const elapsedTime = ref(0);
const answers = ref([]);
const questions = ref([]);
const fullExamMode = ref(true); // Always in full exam mode
const router = useRouter()
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
    console.log('Exam data loaded:', data);
    populateQuestions();
    setupTimer();
  },
  onError(err) {
    console.error('Error loading exam data:', err);
  },
});

// Check if exam data is loaded
const isExamLoaded = computed(() => {
  console.log('Exam data:', exam.data); // Debugging
  return !!exam.data;
});

// Populate questions (shuffle and limit)
const populateQuestions = () => {
  if (!exam.data || !exam.data.questions) {
    console.warn('No questions found in exam data.'); // Debugging
    return;
  }

  const data = exam.data;
  if (data.shuffle_questions) {
        // Shuffle the questions
        const shuffledQuestions = shuffleArray([...data.questions]); // Use a copy of the array
        // Limit the number of questions if required
        questions.value = data.limit_questions_to
            ? shuffledQuestions.slice(0, data.limit_questions_to)
            : shuffledQuestions;
    } else {
        // Use the original questions if no shuffle is required
        questions.value = data.questions;
    }
    answers.value = new Array(questions.value.length).fill('');
	console.log("Populated questions:", questions.value)
};

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

// Submit exam
const submitExam = async () => {
  try {
    console.log('Submitting exam with answers:', answers.value);
    showToast('Success', 'Your exam was submitted successfully.', 'check');
    clearInterval(timerInterval);
  } catch (error) {
    console.error('Error during exam submission:', error);
    showToast('Error', 'Failed to submit the exam.', 'x');
  }
};
</script>