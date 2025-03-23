<template>
	<div v-if="isExamLoaded">
		<!-- Exam Header -->
		<div
			class="bg-blue-200 space-y-1 py-4 px-3 mb-4 rounded-md text-lg text-ink-blue-900"
		>
			<div class="leading-5">
				{{
					`This exam consists of ${questions.length} questions.`
				}}
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
			<div v-if="exam.data.passing_percentage" class="leading-relaxed">
				{{
					`You will have to get ${exam.data.passing_percentage}% correct answers in order to pass the exam.`
				}}
			</div>
			<div v-if="exam.data.max_attempts" class="leading-relaxed">
				{{
					`You can attempt this exam ${
						exam.data.max_attempts === 1 ? '1 time' : `${exam.data.max_attempts} times`
					}.`
				}}
			</div>
		</div>

		<div v-if="exam.data.duration" class="flex flex-col space-x-1 my-4">
			<div class="mb-2">
				<span class=""> {{ ('Time') }}: </span>
				<span class="font-semibold">
					{{ formatTimer(timer) }}
				</span>
			</div>
			<ProgressBar :progress="timerProgress" />
		</div>

		<!-- Start Screen -->
<div v-if="!fullExamMode">
  <div class="border text-center p-20 rounded-md">
    <div class="font-semibold text-lg">
      {{ exam.data.title }}
    </div>
    <Button
      v-if="(!exam.data.max_attempts || attempts.data?.length < exam.data.max_attempts) && exam.data.qbyquestion"
      @click="startExam"
      class="mt-2"
    >
      <span>{{ ('Start') }}</span>
    </Button>
    <Button
      v-else-if="(!exam.data.max_attempts || attempts.data?.length < exam.data.max_attempts)"
      @click="startExam2"
      class="mt-2"
    >
      <span>{{ ('Start full exam') }}</span>
    </Button>
    <div v-else>
      {{ 'You have already exceeded the maximum number of attempts allowed for this exam.' }}
    </div>
  </div>
</div>

<!-- Question-by-Question Mode -->
<div v-if="fullExamMode === false && activeQuestion !== 0 && !examSubmission.data && exam.data.qbyquestion">
	<div v-for="(question, qtidx) in questions">
				<div
					v-if="qtidx == activeQuestion - 1 && questionDetails.data"
					class="border rounded-md p-5"
				>
					<div class="flex justify-between">
						<div class="text-sm text-ink-gray-5">
							<span class="mr-2">
								{{ `Question ${activeQuestion}` }}:
							</span>
							<span>
								{{ getInstructions(questionDetails.data) }}
							</span>
						</div>
						<div class="text-ink-gray-9 text-sm font-semibold item-left">
							{{ question.points }}
							{{ question.points == 1 ? ('Point') : ('Points') }}
						</div>
					</div>
					<div
						class="text-ink-gray-9 font-semibold mt-2 leading-5"
						v-html="questionDetails.data.question"
					></div>
					<div v-if="questionDetails.data.type == 'Choices'" v-for="index in 4">
						<label
							v-if="questionDetails.data[`option_${index}`]"
							class="flex items-center bg-surface-gray-3 rounded-md p-3 mt-4 w-full cursor-pointer focus:border-blue-600"
						>
							<input
								v-if="!showAnswers.length && !questionDetails.data.multiple"
								type="radio"
								:name="encodeURIComponent(questionDetails.data.question)"
								class="w-3.5 h-3.5 text-ink-gray-9 focus:ring-outline-gray-modals"
								@change="markAnswer(index)"
							/>

							<input
								v-else-if="!showAnswers.length && questionDetails.data.multiple"
								type="checkbox"
								:name="encodeURIComponent(questionDetails.data.question)"
								class="w-3.5 h-3.5 text-ink-gray-9 rounded-sm focus:ring-outline-gray-modals"
								@change="markAnswer(index)"
							/>
							<div
								v-else-if="exam.data.show_answers"
								v-for="(answer, idx) in showAnswers"
							>
								<div v-if="index - 1 == idx">
									<CheckCircle
										v-if="answer == 1"
										class="w-4 h-4 text-green-800"
									/>
									<MinusCircle
										v-else-if="answer == 2"
										class="w-4 h-4 text-ink-green-2"
									/>
									<XCircle
										v-else-if="answer == 0"
										class="w-4 h-4 text-red-600"
									/>
									<MinusCircle v-else class="w-4 h-4" />
								</div>
							</div>
							<span
								class="ml-2"
								v-html="questionDetails.data[`option_${index}`]"
							>
							</span>
						</label>
						<div
							v-if="questionDetails.data[`explanation_${index}`]"
							class="mt-2 text-xs"
							v-show="showAnswers.length"
						>
							{{ questionDetails.data[`explanation_${index}`] }}
						</div>
					</div>
					<div v-else-if="questionDetails.data.type == 'User Input'">
						<FormControl
							v-model="possibleAnswer"
							type="textarea"
							:disabled="showAnswers.length ? true : false"
							class="my-2"
						/>
						<div v-if="showAnswers.length">
							<Badge v-if="showAnswers[0]" :label="('Correct')" theme="green">
								<template #prefix>
									<CheckCircle class="w-4 h-4 text-ink-green-2 mr-1" />
								</template>
							</Badge>
							<Badge v-else theme="red" :label="('Incorrect')">
								<template #prefix>
									<XCircle class="w-4 h-4 text-ink-red-3 mr-1" />
								</template>
							</Badge>
						</div>
					</div>
					<div v-else>
						<TextEditor
							class="mt-4"
							:content="possibleAnswer"
							@change="(val) => (possibleAnswer = val)"
							:editable="true"
							:fixedMenu="true"
							editorClass="prose-sm max-w-none border-b border-x bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[7rem]"
						/>
					</div>
					<div class="flex items-center justify-between mt-4">
						<div class="text-sm text-ink-gray-5">
							{{ `Question ${activeQuestion} of ${questions.length}` }}
						</div>
						<Button
							v-if="
								exam.data.show_answers &&
								!showAnswers.length 
							"
							@click="checkAnswer()"
						>
							<span>
								{{ ('Check') }}
							</span>
						</Button>
						<Button
							v-else-if="activeQuestion != questions.length"
							@click="nextQuestion()"
						>
							<span>
								{{ ('Next') }}
							</span>
						</Button>
						<Button v-else @click="submitExam()">
							<span>
								{{ ('Submit') }}
							</span>
						</Button>
					</div>
				</div>
			</div>
		</div>

<!-- Full Exam Mode: All questions at once -->
<div v-if="fullExamMode && all_questions_details.data && all_questions_details.data.length > 0">
  <div v-for="(question, qtidx) in all_questions_details.data" :key="question.name" class="border rounded-md p-5 mb-4">
    <!-- Render each question header, text, and answer options -->
    <div class="flex justify-between">
      <div class="text-sm text-ink-gray-5">
        <span class="mr-2">{{ `Question ${qtidx + 1}` }}:</span>
        <span>{{ getInstructions(question) }}</span>
      </div>
      <div class="text-ink-gray-9 text-sm font-semibold item-left">
        {{ question.points || 0 }} {{ question.points == 1 ? ('Point') : ('Points') }}
      </div>
    </div>
    <div class="text-ink-gray-9 font-semibold mt-2 leading-5" v-html="question.question_detail"></div>
    <!-- Answer Options -->
    <div v-if="question.type == 'Choices'" v-for="index in 4">
      <label
        v-if="question[`option_${index}`]"
        class="flex items-center bg-surface-gray-3 rounded-md p-3 mt-4 w-full cursor-pointer focus:border-blue-600"
      >
        <input
          v-if="!question.multiple"
          type="radio"
          :name="`question_${qtidx}`"
          class="w-3.5 h-3.5 text-ink-gray-9 focus:ring-outline-gray-modals"
          @change="recordAnswer(qtidx, question[`option_${index}`])"
        />
        <input
          v-else-if="question.multiple"
          type="checkbox"
          :name="`question_${qtidx}`"
          class="w-3.5 h-3.5 text-ink-gray-9 rounded-sm focus:ring-outline-gray-modals"
          @change="toggleAnswer(qtidx, question[`option_${index}`])"
        />
        <span class="ml-2" v-html="question[`option_${index}`]"></span>
      </label>
    </div>
    <!-- User Input Option -->
    <div v-else-if="question.type == 'User Input'">
      <FormControl v-model="answers[qtidx]" type="textarea" class="my-2" />
    </div>
  </div>
  <!-- Submit Button -->
  <div class="text-center mt-4">
    <Button @click="submitExamComplete()">
      <span>{{ ('Submit Your Exam') }}</span>
    </Button>
  </div>
</div>

<!-- Exam Summary (if examSubmission.data exists) -->
<div v-else-if="examSubmission.data" class="border rounded-md p-20 text-center space-y-4">
  <div class="text-lg font-semibold">{{ ('Exam Summary') }}</div>
  <div class="text-ink-gray-9">
    {{ `You got ${Math.ceil(examSubmission.data.percentage)}% correct answers with a score of ${examSubmission.data.score} out of ${examSubmission.data.score_out_of}` }}
  </div>
  <div class="mt-6">
    <div v-for="(question, qtidx) in detailedQuestions" :key="question.question_name" class="border rounded-md p-5 mb-4">
      <!-- Question Header -->
      <div class="flex justify-between">
        <div class="text-lg text-ink-gray-5">
          <span class="mr-2">{{ `Question ${qtidx + 1}` }}:</span>
		  <span v-html="question.question_detail"></span>
        </div>
      </div>

      <!-- User Answer -->
      <div class="bg-surface-gray-3 rounded-md p-3 mt-4">
        <strong>{{ ('Your Answer:') }}</strong> {{ question.user_answer || 'No Answer' }}
      </div>

      <!-- Correct Answer -->
      <div class="bg-surface-gray-3 rounded-md p-3 mt-4">
        <strong>{{ ('Correct Answer:') }}</strong> {{ question.correct_answer || 'No Correct Answer' }}
      </div>

      <!-- Explanation -->
      <div v-if="question.explanation" class="bg-surface-gray-3 rounded-md p-3 mt-4">
        <strong>{{ ('Explanation:') }}</strong> {{ question.explanation }}
      </div>

      <!-- Correct/Incorrect Indicator -->
      <div class="mt-4">
        <Badge v-if="examResults[qtidx]?.is_correct?.[0] === 1" :label="('Correct')" theme="green">
          <template #prefix>
            <CheckCircle class="w-4 h-4 text-ink-green-2 mr-1" />
          </template>
        </Badge>
        <Badge v-else :label="('Incorrect')" theme="red">
          <template #prefix>
            <XCircle class="w-4 h-4 text-ink-red-3 mr-1" />
          </template>
        </Badge>
      </div>
    </div>
  </div>
  <Button @click="resetExam()" class="mt-4">
    <span>{{ ('Try Again') }}</span>
  </Button>
</div>
	</div>
	<div v-else>
		<p>Loading exam data...</p>
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

const user = inject('$user')
const fullExamMode = ref(false);
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
	examName: {
		type: String,
		required: true,
	},
})

// Ensure `exam.data` is properly initialized and loaded
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
            console.error("Exam data is null or undefined."); // Debugging
            return null;
        }
        data.duration = parseInt(data.duration) || 0; // Ensure duration is a valid number
        return data;
    },
    onSuccess(data) {
        if (data) {
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

// Add a computed property to check if `exam.data` is loaded
const isExamLoaded = computed(() => !!exam.data);

const populateQuestions = () => {
    let data = exam.data;
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
	if (exam.data.duration) {
		timer.value = exam.data.duration * 60
	}
}

const startTimer = () => {
    timerInterval = setInterval(() => {
        if (exam.data.duration) {
            timer.value--;
            if (timer.value == 0) {
                clearInterval(timerInterval);
                submitExam();
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
	return (timer.value / (exam.data.duration * 60)) * 100
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
			doctype: 'Exam Submission',
			filters: {
				member: user.data?.name,
				exam: exam.data?.name,
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

watch(
	() => exam.data,
	() => {
		if (exam.data) {
			populateQuestions()
		}
		if (exam.data && exam.data.max_attempts) {
			attempts.reload()
			resetExam()
		}
	}
)

const examSubmission = createResource({
    url: 'seminary.seminary.doctype.exam.exam.exam_summary',
    makeParams(values) {
        // Add null-safe checks for `exam.data`
        if (!exam.data) {
        
            return {}; // Return an empty object to avoid errors
        }

        const timeTaken = exam.data.duration
            ? exam.data.duration * 60 - (timer.value || 0) // Use timer when duration is set
            : elapsedTime.value || 0; // Use elapsedTime when duration is not set

       

        return {
            exam: exam.data.name,
            course: router.currentRoute.value.params.courseName,
            results: values?.results || localStorage.getItem(`${exam.data.name}_results`), // Ensure `results` is properly initialized
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
        console.error("Error loading exam summary:", err); // Debugging
    },
    auto: true, // Re-enable auto-fetch
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
		currentQuestion.value = exam.data.questions[value - 1].question
		questionDetails.reload()
	}
})

watch(
	() => props.examName,
	(newName) => {
		if (newName) {
			exam.reload()
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
	onSuccess(data) {
		console.log("All questions details loaded:", data); // Debugging
	},
	onError(err) {
		console.error("Error loading all questions details:", err); // Debugging
	},
})



const startExam = () => {
	activeQuestion.value = 1
	localStorage.removeItem(exam.data.title)
	startTimer()
}

const startExam2 = () => {
    localStorage.removeItem(exam.data.title);
    fullExamMode.value = true; // Set full exam mode flag
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
            title: 'Please select an option',
            icon: 'alert-circle',
            iconClasses: 'text-yellow-600 bg-yellow-100 rounded-full',
            position: 'top-center',
        });
        return;
    }

    createResource({
        url: 'seminary.seminary.doctype.exam.exam.check_answer',
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
            if (!exam.data.show_answers) {
                resetQuestion();
            }
        },
    });
};

const addToLocalStorage = () => {
    let examData = JSON.parse(localStorage.getItem(exam.data.title)) || [];
    let questionData = {
        question_name: currentQuestion.value,
        answer: getAnswers().join(),
        is_correct: showAnswers.filter((answer) => {
			return answer != undefined
		}),
    };

    // Check if the question already exists in localStorage
    const existingIndex = examData.findIndex(
        (item) => item.question_name === questionData.question_name
    );

    if (existingIndex !== -1) {
        // Update the existing question data
        examData[existingIndex] = questionData;
    } else {
        // Add the new question data
        examData ? examData.push(questionData) : (examData = [questionData])
    }

    localStorage.setItem(exam.data.title, JSON.stringify(examData));
};

const nextQuestion = () => {
	if (!exam.data.show_answers) {
		checkAnswer()
	} else {
		addToLocalStorage()
		resetQuestion()
	}
}

const resetQuestion = () => {
	if (activeQuestion.value == exam.data.questions.length) return
	activeQuestion.value = activeQuestion.value + 1
	selectedOptions.splice(0, selectedOptions.length, ...[0, 0, 0, 0])
	showAnswers.length = 0
	possibleAnswer.value = null
}

const submitExam = () => {
	
	if (!exam.data.show_answers) {
		checkAnswer()
		setTimeout(() => {
			createSubmission()
		}, 500)
		return
	}
	createSubmission()
}

const submitExamComplete = async () => {
	const results = [];
	const detailedQuestions = []; // Array to store detailed question data

	// Iterate through all questions and collect answers
	for (let i = 0; i < all_questions_details.data.length; i++) {
		const question = all_questions_details.data[i];
		const answer = answers[i]?.[0] || ""; // Get the first recorded answer or an empty string

		

		// Call the backend to validate the answer
		const response = await call('seminary.seminary.doctype.exam.exam.check_answer', {
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
			user_answer: answer,
			correct_answer: null, // Placeholder for correct answer
			explanation: question.explanation || null,
		});
	}


	// Submit the exam results
	examSubmission.submit(
		{ results: JSON.stringify(results) }, // Ensure results is passed as a string
		{
			onSuccess: async (data) => {
				

				// Fetch correct answers from the backend
				const correctAnswers = await call('seminary.seminary.doctype.exam.exam.get_all_question_results', {
					questions: questions.map(q => q.question),
				});

				// Update detailedQuestions with correct answers and explanations
				detailedQuestions.forEach((question) => {
					const correctAnswer = correctAnswers.find((item) => item.name === question.question_name);
					if (correctAnswer) {
						question.correct_answer = correctAnswer.correct_option;
						question.explanation = correctAnswer.correct_explanation || question.explanation;
					}
				});

				// Store detailed question data in localStorage
				localStorage.setItem(`${exam.data.name}_questions`, JSON.stringify(detailedQuestions));
				

				// Store results in localStorage for use in `makeParams`
				localStorage.setItem(`${exam.data.name}_results`, JSON.stringify(results));

				// Store the exam summary in localStorage
				localStorage.setItem(`${exam.data.name}_summary`, JSON.stringify(data));
				

				examSubmission.reload(); // Reload the exam summary and corrected answers
				fullExamMode.value = false; // Exit full exam mode to show the summary
			},
			onError(err) {
				console.error("Error submitting exam:", err);
			},
		}
	);
};

const createSubmission = () => {
	examSubmission.submit(
		{},
		{
			onSuccess(data) {
				markLessonProgress()
				if (exam.data && exam.data.max_attempts) attempts.reload()
				if (exam.data.duration) clearInterval(timerInterval)
			},
			onError(err) {
				const errorTitle = err?.message || ''
				if (errorTitle.includes('MaximumAttemptsExceededError')) {
					const errorMessage = err.messages?.[0] || err
					showToast(('Error'), (errorMessage), 'x')
					setTimeout(() => {
						window.location.reload()
					}, 3000)
				}
			},
		}
	)
}

const resetExam = () => {
	activeQuestion.value = 0
	selectedOptions.splice(0, selectedOptions.length, ...[0, 0, 0, 0])
	showAnswers.length = 0
	examSubmission.reset()
	populateQuestions()
	setupTimer()
	elapsedTime.value = 0 // Reset elapsed time
}

const getInstructions = (question) => {
	if (question.type == 'Choices')
		if (question.multiple) return ('Choose all answers that apply')
		else return ('Choose one answer')
	else return ('Type your answer')
}

const markLessonProgress = () => {
	
	if (router.currentRoute.value.name === 'Lesson') {
		call('seminary.seminary.api.mark_lesson_progress', {
			course: router.currentRoute.value.params.courseName,
			chapter_number: router.currentRoute.value.params.chapterNumber,
			lesson_number: router.currentRoute.value.params.lessonNumber,
		}).then(() => {
			if (fullExamMode.value) {
				examSubmission.reload(); // Ensure the exam summary is reloaded for full exam mode
			}
		});
	}
};

const getSubmissionColumns = () => {
	return [
		{
			label: 'No.',
			key: 'idx',
		},
		{
			label: 'Date',
			key: 'creation',
		},
		{
			label: 'Score',
			key: 'score',
			align: 'center',
		},
		{
			label: 'Score out of',
			key: 'score_out_of',
			align: 'center',
		},
		{
			label: 'Percentage',
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
const examResults = ref([]);

watch(
  () => examSubmission.data,
  () => {
    if (examSubmission.data) {
      const questions = localStorage.getItem(`${exam.data.name}_questions`);
      const results = localStorage.getItem(`${exam.data.name}_results`);
      detailedQuestions.value = questions ? JSON.parse(questions) : [];
      examResults.value = results ? JSON.parse(results) : [];
    }
  }
);
</script>
