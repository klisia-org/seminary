<template>
	<div v-if="isQuizLoaded">

		<!-- Instructor View -->
		<div v-if="isInstructorView" class="space-y-6">
			<!-- Quiz Dashboard -->
			<div v-if="courseName">
				<h3 class="text-lg font-semibold mb-4 text-ink-gray-9">{{ __('Quiz Dashboard') }}</h3>
				<div v-if="quizDashboard.student_count > 0" class="grid grid-cols-2 gap-4">
					<div class="border rounded-lg p-4 text-center">
						<div class="text-2xl font-bold text-ink-gray-9">{{ quizDashboard.student_count }}</div>
						<div class="text-xs text-ink-gray-5 mt-1">{{ __('Students Who Attempted') }}</div>
					</div>
					<div class="border rounded-lg p-4 text-center">
						<div class="text-2xl font-bold text-ink-gray-9">{{ quizDashboard.avg_attempts }}</div>
						<div class="text-xs text-ink-gray-5 mt-1">{{ __('Average Attempts per Student') }}</div>
					</div>
				</div>
				<div v-else class="text-sm text-ink-gray-5">
					{{ __('No students have attempted this quiz yet.') }}
				<!-- Edit Quiz only if no submissions -->
					<router-link :to="{ name: 'QuizForm', params: { quizID: props.quizName } }">
						<Button variant="solid" class="w-full mt-3">{{ __('Edit Quiz') }}</Button>
					</router-link>
				</div>
			</div>



			<!-- Grading criteria info + link -->
			<div v-if="courseName">
				<div v-if="!isGradedQuiz"
					class="bg-surface-blue-1 border border-outline-blue-1 rounded-md p-3 mb-3 text-sm text-ink-blue-2">
					{{ __('This quiz is currently not associated with a grading criteria.') }}
				</div>
				<router-link :to="{ name: 'CourseAssessment', params: { courseName: courseName } }">
					<Button variant="outline" class="w-full">{{ __('Edit Course Assessments') }}</Button>
				</router-link>
			</div>
		</div>

		<!-- Student / quiz-taking view -->
		<template v-else>
		<!-- Quiz Header -->
		<div class="bg-surface-blue-2 space-y-1 py-4 px-3 mb-4 rounded-md text-lg text-ink-blue-2">
			<div class="leading-5">
				{{
					__(`This quiz consists of ${questions.length} questions`)
				}}
			</div>
			<div v-if="quiz.data?.duration" class="leading-5">
				{{
					__(`Please ensure that you complete all the questions in ${quiz.data.duration} minutes.`)
				}}
			</div>
			<div v-if="quiz.data?.duration" class="leading-5">
				{{
					__(
						'If you fail to do so, the quiz will be automatically submitted when the timer ends.'
					)
				}}
			</div>
			<div v-if="quiz.data.passing_percentage" class="leading-relaxed">
				{{ __(
					`You will have to get ${quiz.data.passing_percentage}% correct answers in order to pass the quiz.`
				) }}
			</div>
			<div v-if="quiz.data.max_attempts && !attemptsExhausted" class="leading-relaxed">
				{{
					__(`You can attempt this quiz ${quiz.data.max_attempts === 1 ? __('1 time') : `${quiz.data.max_attempts}
				times`
						}.`)
				}}
			</div>
		</div>

		<div v-if="quiz.data.duration" class="flex flex-col space-x-1 my-4">
			<div class="mb-2">
				<span class=""> {{ __('Time') }}: </span>
				<span class="font-semibold">
					{{ formatTimer(timer) }}
				</span>
			</div>
			<ProgressBar :progress="timerProgress" />
		</div>

		<!-- Start Screen -->
		<div v-if="!fullQuizMode && !quizSubmission.data">
			<div class="border text-center p-20 rounded-md">
				<div class="font-semibold text-lg">
					{{ quiz.data.title }}
				</div>
				<Button
					v-if="(!quiz.data.max_attempts || attempts.data?.length < quiz.data.max_attempts) && quiz.data.qbyquestion"
					@click="startQuiz" class="mt-2">
					<span>{{ __('Start') }}</span>
				</Button>
				<Button v-else-if="(!quiz.data.max_attempts || attempts.data?.length < quiz.data.max_attempts)"
					@click="startQuiz2" class="mt-2">
					<span>{{ ('Start full quiz') }}</span>
				</Button>
				<div v-else>
					{{ __('You have already exceeded the maximum number of attempts allowed for this quiz.') }}
				</div>
			</div>
		</div>

		<!-- Question-by-Question Mode -->
		<div v-if="fullQuizMode === false && activeQuestion !== 0 && !quizSubmission.data && quiz.data.qbyquestion">
			<div v-for="(question, qtidx) in questions">
				<div v-if="qtidx == activeQuestion - 1 && questionDetails.data" class="border rounded-md p-5">
					<div class="flex justify-between">
						<div class="text-sm text-ink-gray-5">
							<span class="mr-2">
								{{ __('Question') }} {{ activeQuestion }}:
							</span>
							<span>
								{{ getInstructions(questionDetails.data) }}
							</span>
						</div>
						<div class="text-ink-gray-9 text-sm font-semibold item-left">
							{{ question.points }}
							{{ question.points == 1 ? __('Point') : __('Points') }}
						</div>
					</div>
					<div class="text-ink-gray-9 font-semibold mt-2 leading-5" v-html="questionDetails.data.question">
					</div>
					<div v-if="questionDetails.data.type == 'Choices'" v-for="index in 4">
						<label v-if="questionDetails.data[`option_${index}`]"
							class="flex items-center bg-surface-gray-3 rounded-md p-3 mt-4 w-full cursor-pointer focus:border-blue-600">
							<input v-if="!showAnswers.length && !questionDetails.data.multiple" type="radio"
								:name="encodeURIComponent(questionDetails.data.question)"
								class="w-3.5 h-3.5 text-ink-gray-9 focus:ring-outline-gray-modals"
								@change="markAnswer(index)" />

							<input v-else-if="!showAnswers.length && questionDetails.data.multiple" type="checkbox"
								:name="encodeURIComponent(questionDetails.data.question)"
								class="w-3.5 h-3.5 text-ink-gray-9 rounded-sm focus:ring-outline-gray-modals"
								@change="markAnswer(index)" />
							<div v-else-if="quiz.data.show_answers" v-for="(answer, idx) in showAnswers">
								<div v-if="index - 1 == idx">
									<CheckCircle v-if="answer == 1" class="w-4 h-4 text-ink-green-3" />
									<MinusCircle v-else-if="answer == 2" class="w-4 h-4 text-ink-green-2" />
									<XCircle v-else-if="answer == 0" class="w-4 h-4 text-ink-red-3" />
									<MinusCircle v-else class="w-4 h-4" />
								</div>
							</div>
							<span class="ml-2" v-html="questionDetails.data[`option_${index}`]">
							</span>
						</label>
						<div v-if="questionDetails.data[`explanation_${index}`]" class="mt-2 text-xs"
							v-show="showAnswers.length">
							{{ questionDetails.data[`explanation_${index}`] }}
						</div>
					</div>
					<div v-else-if="questionDetails.data.type == 'User Input'">
						<FormControl v-model="possibleAnswer" type="textarea"
							:disabled="showAnswers.length ? true : false" class="my-2" />
						<div v-if="showAnswers.length">
							<Badge v-if="showAnswers[0]" :label="__('Correct')" theme="green">
								<template #prefix>
									<CheckCircle class="w-4 h-4 text-ink-green-2 mr-1" />
								</template>
							</Badge>
							<Badge v-else theme="red" :label="__('Incorrect')">
								<template #prefix>
									<XCircle class="w-4 h-4 text-ink-red-3 mr-1" />
								</template>
							</Badge>
						</div>
					</div>
					<div v-else-if="questionDetails.data.type == 'Reading Report'">
						<div class="flex items-center gap-2 my-2">
							<FormControl type="number" min="0" :max="questionDetails.data.pages_total"
								:modelValue="possibleAnswer"
								@update:modelValue="(val) => (possibleAnswer = clampPages(val, questionDetails.data.pages_total))"
								:disabled="showAnswers.length ? true : false" class="w-28" />
							<span class="text-sm text-ink-gray-5">
								{{ __('of') }} {{ questionDetails.data.pages_total }} {{ __('pages read') }}
							</span>
						</div>
						<div v-if="showAnswers.length">
							<Badge v-if="showAnswers[0]" :label="__('Fully read')" theme="green">
								<template #prefix>
									<CheckCircle class="w-4 h-4 text-ink-green-2 mr-1" />
								</template>
							</Badge>
							<Badge v-else theme="orange" :label="__('Partially read')">
								<template #prefix>
									<MinusCircle class="w-4 h-4 mr-1" />
								</template>
							</Badge>
						</div>
					</div>
					<div v-else-if="questionDetails.data.type == 'Scripture Matching'">
						<ScriptureMatching
							:key="`sm-${currentQuestion}`"
							:items="questionDetails.data.matching_items || []"
							:readOnly="showAnswers.length > 0"
							@update:answer="(payload) => (possibleAnswer = JSON.stringify(payload))"
						/>
					</div>
					<div v-else-if="questionDetails.data.type == 'Scripture Memorization'">
						<ScriptureMemorization
							:key="`sn-${currentQuestion}`"
							:text="questionDetails.data.memorization_text || ''"
							:hideCount="questionDetails.data.hide_word_count || 3"
							:minWordLength="questionDetails.data.min_word_length || 4"
							:referenceLabel="questionDetails.data.memorization_ref || questionDetails.data.memorization_resolved_ref || ''"
							:readOnly="showAnswers.length > 0"
							@update:answer="(payload) => (possibleAnswer = JSON.stringify(payload))"
						/>
					</div>
					<div v-else>
						<TextEditor class="mt-4" :content="possibleAnswer" @change="(val) => (possibleAnswer = val)"
							:editable="true" :fixedMenu="true"
							editorClass="prose-sm max-w-none border-b border-x bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[7rem]" />
					</div>
					<div class="flex items-center justify-between mt-4">
						<div class="text-sm text-ink-gray-5">
							{{ __('Question') }} {{ activeQuestion }} {{ __('of') }} {{ questions.length }}
						</div>
						<Button v-if="
							quiz.data.show_answers &&
							!showAnswers.length
						" @click="checkAnswer()">
							<span>
								{{ __('Check') }}
							</span>
						</Button>
						<Button v-else-if="activeQuestion != questions.length" @click="nextQuestion()">
							<span>
								{{ __('Next') }}
							</span>
						</Button>
						<Button v-else @click="submitQuiz()">
							<span>
								{{ __('Submit') }}
							</span>
						</Button>
					</div>
				</div>
			</div>
		</div>

		<!-- Full Quiz Mode: All questions at once -->
		<div v-if="fullQuizMode && all_questions_details.data && all_questions_details.data.length > 0">
			<div v-for="(question, qtidx) in all_questions_details.data" :key="question.name"
				class="border rounded-md p-5 mb-4">
				<!-- Render each question header, text, and answer options -->
				<div class="flex justify-between">
					<div class="text-sm text-ink-gray-5">
						<span class="mr-2">{{ __('Question') }} {{ qtidx + 1 }}:</span>
						<span>{{ getInstructions(question) }}</span>
					</div>
					<div class="text-ink-gray-9 text-sm font-semibold item-left">
						{{ question.points || 0 }} {{ question.points == 1 ? __('Point') : __('Points') }}
					</div>
				</div>
				<div class="text-ink-gray-9 font-semibold mt-2 leading-5" v-html="question.question_detail"></div>
				<!-- Answer Options -->
				<div v-if="question.type == 'Choices'" v-for="index in 4">
					<label v-if="question[`option_${index}`]"
						class="flex items-center bg-surface-gray-3 rounded-md p-3 mt-4 w-full cursor-pointer focus:border-blue-600">
						<input v-if="!question.multiple" type="radio" :name="`question_${qtidx}`"
							class="w-3.5 h-3.5 text-ink-gray-9 focus:ring-outline-gray-modals"
							@change="recordAnswer(qtidx, question[`option_${index}`])" />
						<input v-else-if="question.multiple" type="checkbox" :name="`question_${qtidx}`"
							class="w-3.5 h-3.5 text-ink-gray-9 rounded-sm focus:ring-outline-gray-modals"
							@change="toggleAnswer(qtidx, question[`option_${index}`])" />
						<span class="ml-2" v-html="question[`option_${index}`]"></span>
					</label>
				</div>
				<!-- User Input Option -->
				<div v-else-if="question.type == 'User Input'">
					<FormControl type="textarea" :modelValue="answers[qtidx]?.[0]"
						@update:modelValue="(val) => recordAnswer(qtidx, val)" class="my-2" />
				</div>
				<!-- Reading Report Option -->
				<div v-else-if="question.type == 'Reading Report'">
					<div class="flex items-center gap-2 my-2">
						<FormControl type="number" min="0" :max="question.pages_total"
							:modelValue="answers[qtidx]?.[0]"
							@update:modelValue="(val) => recordAnswer(qtidx, clampPages(val, question.pages_total))"
							class="w-28" />
						<span class="text-sm text-ink-gray-5">
							{{ __('of') }} {{ question.pages_total }} {{ __('pages read') }}
						</span>
					</div>
				</div>
				<!-- Scripture Matching -->
				<div v-else-if="question.type == 'Scripture Matching'">
					<ScriptureMatching
						:items="question.matching_items || []"
						@update:answer="(payload) => recordAnswer(qtidx, JSON.stringify(payload))"
					/>
				</div>
				<!-- Scripture Memorization -->
				<div v-else-if="question.type == 'Scripture Memorization'">
					<ScriptureMemorization
						:text="question.memorization_text || ''"
						:hideCount="question.hide_word_count || 3"
						:minWordLength="question.min_word_length || 4"
						:referenceLabel="question.memorization_ref || ''"
						@update:answer="(payload) => recordAnswer(qtidx, JSON.stringify(payload))"
					/>
				</div>
			</div>
			<!-- Submit Button -->
			<div class="text-center mt-4">
				<Button @click="submitQuizComplete()">
					<span>{{ __('Submit Your Quiz') }}</span>
				</Button>
			</div>
		</div>

		<!-- Quiz Summary (if quizSubmission.data exists) -->
		<div v-else-if="quizSubmission.data" class="border rounded-md p-20 text-center space-y-4">
			<div class="text-lg font-semibold">{{ __('Quiz Summary') }}</div>
			<div class="text-ink-gray-9">
				{{ __(`You got ${Math.ceil(quizSubmission.data.percentage)}% correct answers with a score of
				${Math.round(quizSubmission.data.score * 100) / 100} out of ${quizSubmission.data.score_out_of}`) }}
			</div>
			<div class="mt-6">
				<div v-for="(question, qtidx) in detailedQuestions" :key="question.question_name"
					class="border rounded-md p-5 mb-4">
					<!-- Question Header -->
					<div class="flex justify-between items-start gap-4">
						<div class="text-lg text-ink-gray-5">
							<span class="mr-2">{{ __('Question') }} {{ qtidx + 1 }}:</span>
							<span v-html="question.question_detail"></span>
						</div>
						<div v-if="question.points_out_of != null"
							class="text-sm font-semibold text-ink-gray-7 whitespace-nowrap shrink-0">
							{{ __('Score') }}: {{ question.points ?? 0 }} / {{ question.points_out_of }}
						</div>
					</div>

					<!-- Scripture Matching: card-based result -->
					<ScriptureMatchingResult
						v-if="question.type === 'Scripture Matching'"
						:items="question.matching_items || []"
						:userAnswer="question.user_answer || ''"
						class="mt-4"
					/>
					<!-- Scripture Memorization: dual-verse result -->
					<ScriptureMemorizationResult
						v-else-if="question.type === 'Scripture Memorization'"
						:text="question.memorization_text || ''"
						:userAnswer="question.user_answer || ''"
						:referenceLabel="question.memorization_ref || question.memorization_resolved_ref || ''"
						class="mt-4"
					/>
					<!-- Generic User Answer / Correct Answer (other types) -->
					<template v-else>
						<div class="bg-surface-gray-3 rounded-md p-3 mt-4">
							<strong>{{ __('Your Answer:') }}</strong> {{ question.user_answer || __('No Answer') }}
						</div>
						<div v-if="question.type !== 'Reading Report'" class="bg-surface-gray-3 rounded-md p-3 mt-4">
							<strong>{{ __('Correct Answer:') }}</strong> {{ question.correct_answer ||
								__('No Correct Answer') }}
						</div>
					</template>

					<!-- Explanation -->
					<div v-if="question.explanation" class="bg-surface-gray-3 rounded-md p-3 mt-4">
						<strong>{{ __('Explanation:') }}</strong> {{ question.explanation }}
					</div>

					<!-- Correct/Incorrect Indicator -->
					<div class="mt-4">
						<Badge v-if="quizResults[qtidx]?.is_correct?.[0] === 1" :label="__('Correct')" theme="green">
							<template #prefix>
								<CheckCircle class="w-4 h-4 text-ink-green-2 mr-1" />
							</template>
						</Badge>
						<Badge v-else-if="question.type !== 'Reading Report'" :label="__('Incorrect')" theme="red">
							<template #prefix>
								<XCircle class="w-4 h-4 text-ink-red-3 mr-1" />
							</template>
						</Badge>
					</div>
				</div>
			</div>
			<Button v-if="!attemptsExhausted" @click="resetQuiz()" class="mt-4">
				<span>{{ __('Try Again') }}</span>
			</Button>
		</div>
		</template>
	</div>
	<div v-else>
		<p>Loading quiz data...</p>
	</div>
</template>
<script setup>
import { Badge, Button, call, createResource, ListView, TextEditor, FormControl, toast } from 'frappe-ui'
import { ref, watch, reactive, inject, computed } from 'vue'
import { createToast } from '@/utils/'
import { CheckCircle, XCircle, MinusCircle } from 'lucide-vue-next'
import { timeAgo } from '@/utils'
import { useRouter } from 'vue-router'
import ProgressBar from '@/components/ProgressBar.vue'
import ScriptureMatching from '@/components/QuestionTypes/ScriptureMatching.vue'
import ScriptureMemorization from '@/components/QuestionTypes/ScriptureMemorization.vue'
import ScriptureMatchingResult from '@/components/QuestionTypes/ScriptureMatchingResult.vue'
import ScriptureMemorizationResult from '@/components/QuestionTypes/ScriptureMemorizationResult.vue'

const user = inject('$user')
const fullQuizMode = ref(false);
const activeQuestion = ref(0)
const currentQuestion = ref('')
const selectedOptions = reactive([0, 0, 0, 0])
const showAnswers = reactive([])
let questions = reactive([])
const possibleAnswer = ref(null)
const timer = ref(0)
let timerInterval = null
const router = useRouter()
const elapsedTime = ref(0); // Tracks the time taken in seconds
const answers = reactive({}); // Stores the answers for each question


const props = defineProps({
	quizName: {
		type: String,
		required: true,
	},
})

// Ensure `quiz.data` is properly initialized and loaded
const quiz = createResource({
	url: 'frappe.client.get',
	makeParams(values) {
		return {
			doctype: 'Quiz',
			name: props.quizName,
		};
	},
	cache: ['quiz', props.quizName],
	auto: true,
	transform(data) {
		if (!data) {
			console.error("Quiz data is null or undefined."); // Debugging
			return null;
		}
		data.duration = parseInt(data.duration) || 0; // Ensure duration is a valid number
		return data;
	},
	onSuccess(data) {
		if (data) {
			populateQuestions();
			setupTimer();
			lastSubmission.reload();
			if (isInstructorView.value && courseName.value) {
				quizDashboardResource.reload();
				gradingCriteriaResource.reload();
			}
		} else {
			console.error("Failed to load quiz data."); // Debugging
		}
	},
	onError(err) {
		console.error("Error loading quiz data:", err); // Debugging
	},
});

// Add a computed property to check if `quiz.data` is loaded
const isQuizLoaded = computed(() => !!quiz.data);

// Instructors/moderators/evaluators see the management view instead of the quiz.
const isInstructorView = computed(
	() => user.data?.is_moderator || user.data?.is_evaluator || user.data?.is_instructor
)
const courseName = computed(() => router.currentRoute.value.params.courseName)

const populateQuestions = () => {
	let data = quiz.data;
	if (data.shuffle_questions) {
		// Shuffle the questions
		const shuffledQuestions = shuffleArray([...data.questions]); // Use a copy of the array
		// Limit the number of questions if required
		questions = data.limit_questions_to
			? shuffledQuestions.slice(0, data.limit_questions_to)
			: shuffledQuestions;
	} else {
		// Use the original questions if no shuffle is required
		questions = data.questions;
	}

}

const setupTimer = () => {
	if (quiz.data.duration) {
		timer.value = quiz.data.duration * 60
	}
}

const startTimer = () => {
	timerInterval = setInterval(() => {
		if (quiz.data.duration) {
			timer.value--;
			if (timer.value == 0) {
				clearInterval(timerInterval);
				submitQuiz();
			}
		}
		elapsedTime.value++; // Always increment elapsed time
	}, 1000);
};

const formatTimer = (seconds) => {
	const hrs = Math.floor(seconds / 3600)
		.toString()
		.padStart(2, '0')
	const mins = Math.floor((seconds % 3600) / 60)
		.toString()
		.padStart(2, '0')
	const secs = (seconds % 60).toString().padStart(2, '0')
	return hrs != '00' ? `${hrs}:${mins}:${secs}` : `${mins}:${secs}`
}

const timerProgress = computed(() => {
	return (timer.value / (quiz.data.duration * 60)) * 100
})

const shuffleArray = (array) => {
	for (let i = array.length - 1; i > 0; i--) {
		const j = Math.floor(Math.random() * (i + 1))
			;[array[i], array[j]] = [array[j], array[i]]
	}
	return array
}

const attempts = createResource({
	url: 'frappe.client.get_list',
	makeParams(values) {
		return {
			doctype: 'Quiz Submission',
			filters: {
				member: user.data?.name,
				quiz: quiz.data?.name,
			},
			fields: [
				'name',
				'creation',
				'score',
				'score_out_of',
				'percentage',
				'passing_percentage',
			],
			order_by: 'creation desc',
		}
	},
	transform(data) {
		data.forEach((submission, index) => {
			submission.creation = timeAgo(submission.creation)
			submission.idx = index + 1
		})
	},
})

// True once the student has used up every allowed attempt.
const attemptsExhausted = computed(
	() =>
		!!quiz.data?.max_attempts &&
		attempts.data?.length >= quiz.data.max_attempts
)

// --- Instructor view: dashboard stats and grading-criteria status ---
const quizDashboard = ref({ student_count: 0, avg_attempts: 0 })

const quizDashboardResource = createResource({
	url: 'seminary.seminary.api.get_quiz_dashboard',
	makeParams() {
		return { course_name: courseName.value, quiz_id: quiz.data?.name }
	},
	onSuccess(data) {
		quizDashboard.value = data || { student_count: 0, avg_attempts: 0 }
	},
})

const gradingCriteriaResource = createResource({
	url: 'seminary.seminary.api.GradeableQuiz',
	makeParams() {
		return { courseName: courseName.value, quizID: quiz.data?.name }
	},
})
const isGradedQuiz = computed(() => !!gradingCriteriaResource.data)

watch(
	() => quiz.data,
	(newData) => {
		if (newData) {
			populateQuestions()
			lastSubmission.reload()
		}
		if (newData && quiz.data.max_attempts) {
			attempts.reload()
			resetQuiz()
		}
	}
)

const quizSubmission = createResource({
	url: 'seminary.seminary.doctype.quiz.quiz.quiz_summary',
	makeParams(values) {
		// Add null-safe checks for `quiz.data`
		if (!quiz.data) {
			return {}; // Return an empty object to avoid errors
		}
		const timeTaken = quiz.data.duration
			? quiz.data.duration * 60 - (timer.value || 0) // Use timer when duration is set
			: elapsedTime.value || 0; // Use elapsedTime when duration is not set



		return {
			quiz: quiz.data.name,
			course: router.currentRoute.value.params.courseName,
			results: values?.results || localStorage.getItem(`${quiz.data.name}_results`), // Ensure `results` is properly initialized
			time_taken: timeTaken, // Pass the correct time_taken
		};
	},
	onSuccess(data) {

		if (data.corrected_answers) {
			all_questions_details.data = data.corrected_answers.map((question) => ({
				...question,
				user_answer: question.user_answer || null, // Ensure user_answer is included
				correct_answer: question.correct_answer || null, // Ensure correct_answer is included
			}));
		}
	},
	onError(err) {
		console.error("Error loading quiz summary:", err); // Debugging
	},
	// No auto-fetch: quiz_summary CREATES a Quiz Submission, so it must run
	// only on an explicit submit — never on page load.
});

const questionDetails = createResource({
	url: 'seminary.seminary.utils.get_question_details',
	makeParams(values) {
		return {
			question: currentQuestion.value,
		}
	},

})

watch(activeQuestion, (value) => {
	if (value > 0) {
		currentQuestion.value = quiz.data.questions[value - 1].question
		questionDetails.reload()
	}
})

watch(
	() => props.quizName,
	(newName) => {
		if (newName) {
			quiz.reload()
		}
	}
)

const all_questions_details = createResource({
	url: 'seminary.seminary.utils.get_all_questions_details',
	makeParams(values) {
		return {
			questions: questions.map((q) => q.name), // Ensure only question names are sent
		}
	},
})



const startQuiz = () => {
	activeQuestion.value = 1
	localStorage.removeItem(quiz.data.title)
	startTimer()
}

const startQuiz2 = () => {
	localStorage.removeItem(quiz.data.title);
	fullQuizMode.value = true; // Set full quiz mode flag
	startTimer();
	all_questions_details.reload(); // Ensure the resource is reloaded

}


const markAnswer = (index) => {
	if (!questionDetails.data.multiple)
		selectedOptions.splice(0, selectedOptions.length, ...[0, 0, 0, 0])
	selectedOptions[index - 1] = selectedOptions[index - 1] ? 0 : 1
}

const getAnswers = () => {
	let answers = []
	const type = questionDetails.data.type

	if (type == 'Choices') {
		selectedOptions.forEach((value, index) => {
			if (selectedOptions[index])
				answers.push(questionDetails.data[`option_${index + 1}`])
		})
	} else {
		answers.push(possibleAnswer.value)
	}

	return answers
}

const checkAnswer = () => {
	let answers = getAnswers();
	if (!answers.length) {
		createToast({
			title: __('Please select an option'),
			icon: 'alert-circle',
			iconClasses: 'text-ink-amber-3 bg-surface-amber-2 rounded-full',
			position: 'top-center',
		});
		return;
	}

	createResource({
		url: 'seminary.seminary.doctype.quiz.quiz.check_answer',
		params: {
			question: currentQuestion.value,
			type: questionDetails.data.type,
			answers: JSON.stringify(answers),
		},
		auto: true,
		onSuccess(data) {
			let type = questionDetails.data.type;
			if (type === 'Choices') {
				selectedOptions.forEach((option, index) => {
					if (option) {
						showAnswers[index] = option && data[index];
					} else if (data[index] === 2) {
						showAnswers[index] = 2;
					} else {
						showAnswers[index] = undefined;
					}
				});
			} else {
				showAnswers.push(data);
			}
			addToLocalStorage();
			if (!quiz.data.show_answers) {
				resetQuestion();
			}
		},
	});
};

const addToLocalStorage = () => {
	let quizData = JSON.parse(localStorage.getItem(quiz.data.title)) || [];
	let questionData = {
		question_name: currentQuestion.value,
		answer: getAnswers().join(),
		is_correct: showAnswers.filter((answer) => {
			return answer != undefined
		}),
	};

	// Check if the question already exists in localStorage
	const existingIndex = quizData.findIndex(
		(item) => item.question_name === questionData.question_name
	);

	if (existingIndex !== -1) {
		// Update the existing question data
		quizData[existingIndex] = questionData;
	} else {
		// Add the new question data
		quizData ? quizData.push(questionData) : (quizData = [questionData])
	}


	localStorage.setItem(quiz.data.title, JSON.stringify(quizData));
	localStorage.setItem(`${quiz.data.name}_results`, JSON.stringify(quizData)); // Save results for submission

};

const nextQuestion = () => {
	if (!quiz.data.show_answers) {
		checkAnswer()
	} else {
		addToLocalStorage()
		resetQuestion()
	}
}

const resetQuestion = () => {
	if (activeQuestion.value == quiz.data.questions.length) return
	activeQuestion.value = activeQuestion.value + 1
	selectedOptions.splice(0, selectedOptions.length, ...[0, 0, 0, 0])
	showAnswers.length = 0
	possibleAnswer.value = null
}

const submitQuiz = () => {

	if (!quiz.data.show_answers) {
		checkAnswer()
		setTimeout(() => {
			createSubmission()
		}, 500)
		return
	}
	createSubmission()
	console.log('Quiz submitted with Submit Quiz button and asnwers shown')
}

const submitQuizComplete = async () => {
	const results = [];
	const detailedQuestions = []; // Array to store detailed question data

	// Iterate through all questions and collect answers
	for (let i = 0; i < all_questions_details.data.length; i++) {
		const question = all_questions_details.data[i];
		const answer = answers[i]?.[0] || ""; // Get the first recorded answer or an empty string



		// Call the backend to validate the answer
		const response = await call('seminary.seminary.doctype.quiz.quiz.check_answer', {
			question: question.question, // Pass the unique question identifier
			type: question.type,
			answers: JSON.stringify([answer]), // Send the answer as an array
		});

		// Extract only the relevant value for `is_correct`
		const is_correct = Array.isArray(response) ? [response.find((val) => val === 1) || 0] : [response];

		results.push({
			question_name: question.question, // Use the unique question identifier
			answer: answer, // Use the single answer string
			is_correct: is_correct, // Ensure this contains only the relevant value
		});

		// Add detailed question data (correct_answer will be fetched later)
		detailedQuestions.push({
			question_name: question.question,
			question_detail: question.question_detail,
			type: question.type,
			user_answer: answer,
			correct_answer: null, // Placeholder for correct answer
			explanation: question.explanation || null,
			// Scripture-specific extras for rich result cards
			matching_items: question.matching_items,
			memorization_text: question.memorization_text,
			memorization_ref: question.memorization_ref,
			memorization_resolved_ref: question.memorization_resolved_ref,
		});
	}


	// Submit the quiz results
	quizSubmission.submit(
		{ results: JSON.stringify(results) }, // Ensure results is passed as a string
		{
			onSuccess: async (data) => {


				// Pull the authoritative graded result (per-question points + correct answers)
				const saved = await call('seminary.seminary.doctype.quiz.quiz.get_last_submission', {
					quiz: quiz.data.name,
				});
				const savedRows = saved?.result || [];

				// Merge per-question score, correct answers and explanations
				detailedQuestions.forEach((question) => {
					const row = savedRows.find((r) => r.question_name === question.question_name);
					if (row) {
						question.correct_answer = row.correct_answer;
						question.explanation = row.explanation || question.explanation;
						question.points = row.points;
						question.points_out_of = row.points_out_of;
						// Server is authoritative for the Scripture data too,
						// in case the question was re-saved between attempt and grading.
						if (row.matching_items) question.matching_items = row.matching_items;
						if (row.memorization_text) question.memorization_text = row.memorization_text;
						if (row.memorization_ref) question.memorization_ref = row.memorization_ref;
						if (row.memorization_resolved_ref) question.memorization_resolved_ref = row.memorization_resolved_ref;
					}
				});

				// Server is authoritative for is_correct too — the frontend
				// computed it as an object for Scripture types (response was
				// {correct, total}), which broke the bottom Correct/Incorrect
				// badge. Overwrite with the saved row's 1/0.
				results.forEach((r) => {
					const row = savedRows.find((sr) => sr.question_name === r.question_name);
					if (row) r.is_correct = [row.is_correct];
				});

				// Store detailed question data in localStorage
				localStorage.setItem(`${quiz.data.name}_questions`, JSON.stringify(detailedQuestions));


				// Store results in localStorage for use in `makeParams`
				localStorage.setItem(`${quiz.data.name}_results`, JSON.stringify(results));

				// Store the quiz summary in localStorage
				localStorage.setItem(`${quiz.data.name}_summary`, JSON.stringify(data));


				quizSubmission.reload(); // Reload the quiz summary and corrected answers
				if (quiz.data && quiz.data.max_attempts) attempts.reload()
				fullQuizMode.value = false; // Exit full quiz mode to show the summary
			},
			onError(err) {
				console.error("Error submitting quiz:", err);
			},
		}
	);
};

const createSubmission = () => {
	const results = localStorage.getItem(`${quiz.data.name}_results`); // Retrieve results from localStorage
	if (!results) {
		console.error("No results found to submit."); // Debugging
		return;
	}

	quizSubmission.submit(
		{ results }, // Pass results to the backend
		{
			onSuccess(data) {
				markLessonProgress()
				if (quiz.data && quiz.data.max_attempts) attempts.reload()
				if (quiz.data.duration) clearInterval(timerInterval)
				// Build the detailed result cards from the saved submission.
				lastSubmission.reload()
			},
			onError(err) {
				const errorTitle = err?.message || ''
				if (errorTitle.includes('MaximumAttemptsExceededError')) {
					const errorMessage = err.messages?.[0] || err
					toast.error(err.messages?.[0] || err)
					setTimeout(() => {
						window.location.reload()
					}, 3000)
				}
			},
		}
	)
}

const resetQuiz = () => {
	activeQuestion.value = 0
	selectedOptions.splice(0, selectedOptions.length, ...[0, 0, 0, 0])
	showAnswers.length = 0
	isReviewingSubmission.value = false
	quizSubmission.reset()
	populateQuestions()
	setupTimer()
	elapsedTime.value = 0 // Reset elapsed time
}

const getInstructions = (question) => {
	if (question.type == 'Choices')
		if (question.multiple) return (__('Choose all answers that apply'))
		else return (__('Choose one answer'))
	else if (question.type == 'Reading Report')
		return (__('Enter the number of pages you read'))
	else return (__('Type your answer'))
}

// Keep page counts within [0, pages_total] so out-of-range values are rejected.
const clampPages = (val, max) => {
	let n = parseInt(val)
	max = parseInt(max) || 0
	if (isNaN(n)) return ''
	if (n < 0) n = 0
	if (max && n > max) n = max
	return n
}

const markLessonProgress = () => {

	if (router.currentRoute.value.name === 'Lesson') {
		call('seminary.seminary.api.mark_lesson_progress', {
			course: router.currentRoute.value.params.courseName,
			chapter_number: router.currentRoute.value.params.chapterNumber,
			lesson_number: router.currentRoute.value.params.lessonNumber,
		}).then(() => {
			if (fullQuizMode.value) {
				quizSubmission.reload(); // Ensure the quiz summary is reloaded for full quiz mode
			}
		});
	}
};

const getSubmissionColumns = () => {
	return [
		{
			label: __('No.'),
			key: 'idx',
		},
		{
			label: __('Date'),
			key: 'creation',
		},
		{
			label: __('Score'),
			key: 'score',
			align: 'center',
		},
		{
			label: __('Score out of'),
			key: 'score_out_of',
			align: 'center',
		},
		{
			label: __('Percentage'),
			key: 'percentage',
			align: 'center',
		}
	]
}

const recordAnswer = (qtidx, answer) => {
	// Ensure `answers` is reactive and stores the selected answer
	answers[qtidx] = [answer];

};

const toggleAnswer = (qtidx, answer) => {
	// Ensure `answers` is reactive and handles multiple answers
	if (!answers[qtidx]) {
		answers[qtidx] = [];
	}
	const index = answers[qtidx].indexOf(answer);
	if (index === -1) {
		answers[qtidx].push(answer); // Add the answer if not already selected
	} else {
		answers[qtidx].splice(index, 1); // Remove the answer if already selected
	}

};

watch(
	() => all_questions_details.data,
	(newData) => {
		if (newData) {
			console.log("All questions details updated"); // Debugging
		} else {
			console.warn("No data available in all_questions_details."); // Debugging
		}
	}
)

// Load detailed question data and results from localStorage
const detailedQuestions = ref([]);
const quizResults = ref([]);
// True while showing a previously saved submission (loaded read-only) so the
// localStorage sync below doesn't overwrite the reconstructed result.
const isReviewingSubmission = ref(false);

watch(
	() => quizSubmission.data,
	() => {
		if (isReviewingSubmission.value) return
		if (quizSubmission.data) {
			const questions = localStorage.getItem(`${quiz.data.name}_questions`);
			const results = localStorage.getItem(`${quiz.data.name}_results`);
			detailedQuestions.value = questions ? JSON.parse(questions) : [];
			quizResults.value = results ? JSON.parse(results) : [];
		}
	}
);

// Read-only: when revisiting a quiz, show the student's most recent result
// instead of silently re-running quiz_summary (which would create a duplicate
// submission). Populated via the quiz.data watch above.
const lastSubmission = createResource({
	url: 'seminary.seminary.doctype.quiz.quiz.get_last_submission',
	makeParams() {
		return { quiz: quiz.data?.name }
	},
	onSuccess(data) {
		// No prior submission — leave the start screen as-is.
		if (!data) return
		isReviewingSubmission.value = true
		detailedQuestions.value = (data.result || []).map((row) => ({
			question_name: row.question_name,
			question_detail: row.question_detail,
			type: row.type,
			user_answer: row.answer,
			correct_answer: row.correct_answer,
			explanation: row.explanation,
			points: row.points,
			points_out_of: row.points_out_of,
			// Scripture-specific extras passed through for the rich result cards
			matching_items: row.matching_items,
			memorization_text: row.memorization_text,
			memorization_ref: row.memorization_ref,
			memorization_resolved_ref: row.memorization_resolved_ref,
		}))
		quizResults.value = (data.result || []).map((row) => ({
			is_correct: [row.is_correct],
		}))
		quizSubmission.data = {
			score: data.score,
			score_out_of: data.score_out_of,
			percentage: data.percentage,
			submission: data.submission,
			pass: data.percentage >= data.passing_percentage,
		}
	},
});
</script>