<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs v-if="submisisonDetails.doc" :items="breadcrumbs" />
		<div class="space-x-2">
			<Badge
				v-if="submisisonDetails.isDirty"
				:label="__('Not Saved')"
				variant="subtle"
				theme="orange"
			/>
			<Button variant="solid" @click="validateSubmission()">
				{{ __('Save') }}
			</Button>
		</div>
	</header>
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
								Out of {{ submisisonDetails.doc.score_out_of }} Points
							</div>
						</div>
						<div class="text-center mr-5">
							<div class="text-3xl font-semibold text-ink-gray-9 mt-2">
								{{ formatTime(submisisonDetails.doc.time_taken) }}
							</div>
							<div class="text-sm text-ink-gray-5">
								Time taken
							</div>
						</div>
					</div>
				</div>

				<!-- Questions Section -->
				<div
					v-for="(row, index) in submisisonDetails.doc.result"
					:key="index"
					class="border p-5 rounded-md space-y-4"
				>
					  <!-- Question Title -->
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
      <Button
        variant="solid"
        theme="green"
        size="sm"
        @click="setPoints(row, row.points_out_of)"
      >
        <Check class="w-4 h-4" />
      </Button>
      <Button
        variant="solid"
        theme="red"
        size="sm"
        @click="setPoints(row, 0)"
      >
        <X class="w-4 h-4" />
      </Button>
    </div>

    <!-- Points Input -->
	<div class="flex items-center space-x-2">
  <FormControl
    v-model="row.points"
    type="number"
    class="w-20 text-right"
	@change="(val) => onPointsChange(row, val)"
    
  />
  <span class="text-sm text-ink-gray-7">
    / {{ parseInt(row.points_out_of, 10) }} {{ __('Points') }}
  </span>
</div>
  </div>
						<TextEditor
							v-model="row.comments"
							:label="__('Comment')"
							:placeholder="__('Add a comment')"
							:fixedMenu="true"
							:editorClass="'h-32'"
							@change="(val) => onCommentChange(row, val)" <!-- Pass the updated value -->
						</TextEditor>
						/>
					</div>
				</div>
			

			<!-- Right Section (1/3 width) -->
			<div class="col-span-1 space-y-4">
				<div class="space-y-4 border p-5 rounded-md">
					<FormControl
						v-model="submisisonDetails.doc.fudge_points"
						:label="__('Fudge Points')"
						:disabled="false"
					/>
					<FormControl
						v-model="submisisonDetails.doc.status"
						:label="__('Status')"
						type="select"
						:options="[
							{
								label: 'Not Graded',
								value: 'Not Graded',
							},
							{
								label: 'Graded',
								value: 'Graded',
							},
						]"
						:disabled="false"
					/>
				</div>
				<div class="space-y-4 border p-5 rounded-md">
					<Discussions
						:title="'Exam Comments'"
						:doctype="'Exam Submission'"
						:docname="submisisonDetails.doc.name"
						:key="submisisonDetails.doc.name"
						type="single"
						/>
				</div>
			</div>
		</div>
	</div>
</template>
<script setup>
import {
	createDocumentResource,
	Breadcrumbs,
	FormControl,
	Button,
	Badge,
	TextEditor
} from 'frappe-ui'
import { computed, onBeforeUnmount, onMounted, inject, watch, watchEffect } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from '@/utils'
import Discussions from '@/components/Discussions.vue'
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
})

const submisisonDetails = createDocumentResource({
  doctype: 'Exam Submission',
  name: props.submission,
  auto: true, // Automatically fetch the document
  save: {
    async submit() {
      try {
        // Send the document to the backend for saving
        const response = await frappe.call('frappe.client.save', {
          doc: submisisonDetails.doc, // Pass the entire document, including child records
        });

        // Update the local document with the saved data
        submisisonDetails.doc = response.message;

        // Mark the document as not dirty
        submisisonDetails.isDirty = false;

        // Show a success message
        showToast(__('Success'), __('Submission saved successfully'), 'check-circle');
      } catch (err) {
        // Handle errors
        console.error('Error saving submission:', err);
        throw err; // Re-throw the error to be handled by the caller
      }
    },
  },
});

const breadcrumbs = computed(() => {
	return [
		{
			label: __('Exam Submissions'),
			route: {
				name: 'ExamSubmissionList',
				params: {
					examID: submisisonDetails.doc.exam,
				},
			},
		},
		{
			label: submisisonDetails.doc.exam_title,
		},
	]
})

const formatTime = (seconds) => {
  if (!seconds) return '00:00:00'; // Handle null or undefined values
  const hrs = Math.floor(seconds / 3600).toString().padStart(2, '0');
  const mins = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
  const secs = (seconds % 60).toString().padStart(2, '0');
  return `${hrs}:${mins}:${secs}`;
};
const setPoints = (row, points) => {
  row.points = points;
  row.graded = true; // Mark the question as graded
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

// Watch for changes in row.points or fudge_points
const pointsArray = computed(() => {
  return submisisonDetails.doc.result ? submisisonDetails.doc.result.map((row) => row.points) : [];
});

watchEffect(() => {
  if (submisisonDetails.doc && submisisonDetails.doc.result) {
    updateScoreAndPercentage(); // Recalculate score and percentage
  }
});

// Watch for changes in fudge_points
watchEffect(() => {
  if (submisisonDetails.doc && typeof submisisonDetails.doc.fudge_points !== 'undefined') {
    updateScoreAndPercentage(); // Recalculate score and percentage
  }
});

const onCommentChange = (row, value) => {
  row.comments = value; // Update the row.comments field
  
};

const validateSubmission = async () => {
  // Find ungraded questions
  const ungradedQuestions = submisisonDetails.doc.result
    .map((row, index) => (!row.graded ? `Question ${index + 1}` : null))
    .filter((question) => question !== null);

  if (ungradedQuestions.length > 0) {
    // Show confirmation dialog for ungraded questions
    const confirmSave = confirm(
      `The following questions need grading: ${ungradedQuestions.join(', ')}. Do you want to save anyway?`
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
  await saveSubmission();
};

const onPointsChange = (row, value) => {
  row.graded = true; // Mark the question as graded
  console.log(`Updated Points for Question: ${row.points}`); // Debugging log
};

const saveSubmission = async () => {
  try {
    console.log('Saving submission:', submisisonDetails.doc); // Debugging log
    await submisisonDetails.save.submit(); // Save the document
    showToast(__('Success'), __('Submission saved successfully'), 'check');
  } catch (err) {
    console.error('Error saving submission:', err); // Debugging log
    showToast(__('Error'), __(err.messages?.[0] || 'An error occurred while saving'), 'x');
  }
};
</script>
