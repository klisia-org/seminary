<template>
  <div v-if="submisisonDetails.loading" class="text-center py-5">
    <p>Loading submission details...</p>
  </div>
  <div v-else-if="submisisonDetails.doc" class="space-y-5">
    <div class="grid grid-cols-3 gap-3">
      <!-- Left Section (2/3 width) -->
      <div class="col-span-2 space-y-4">
        <div class="space-y-4 border p-2 rounded-md">
          <div class="flex items-center justify-between py-4">
            <!-- Exam Percentage -->
            <div class="text-center ml-5">
              <div class="text-3xl font-bold text-ink-gray-9">
                {{ submisisonDetails.doc.percentage || 0 }}%
              </div>
              <div class="text-sm text-ink-gray-5">Score</div>
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
              <div class="text-sm text-ink-gray-5">Time taken</div>
            </div>
          </div>
        </div>

        <!-- Questions Section -->
        <div
          v-for="(row, index) in submisisonDetails.doc.result"
          :key="index"
          class="border p-5 rounded-md space-y-4 "
        >
          <!-- Question Title -->
          <div class="space-y-1">
            <div class="font-semibold text-ink-gray-9 text-left">
              {{ __('Question') }} {{ index + 1 }}:
            </div>
            <div class="leading-5 text-ink-gray-9 text-left" v-html="row.question_name"></div>
          </div>
          <!-- Answer -->
          <div class="leading-5 text-ink-gray-7 space-x-1 text-left">
            <span> {{ __('Your Answer') }}: </span>
            <span v-html="row.answer"></span>
          </div>
          <!-- Points -->
          <div class="flex justify-end items-center space-x-2">
            <span class="text-sm text-ink-gray-7 text-xl">
              {{ row.points }} / {{ parseInt(row.points_out_of, 10) }} {{ __('Points') }}
            </span>
          </div>
          <!-- Comments -->
          <div v-if="row.comments" class="leading-5 text-ink-gray-7 text-xl space-x-1 text-left">
            <span> {{ __('Comments') }}: </span>
            <span v-html="row.comments"></span>
          </div>
        </div>
      </div>

      <!-- Right Section (1/3 width) -->
      <div class="col-span-1 space-y-4">
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
  <div v-else>
    <p>Debug: No submission details found.</p>
  </div>
</template>

<script setup>
import { createDocumentResource } from 'frappe-ui';
import { watch, inject } from 'vue';
import Discussions from '@/components/Discussions.vue'

const socket = inject('$socket')
const props = defineProps({
  submission: {
    type: Object,
    required: true,
  },
});

console.log('ExamGraded received submission:', props.submission); // Debugging log

const submisisonDetails = createDocumentResource({
  doctype: 'Exam Submission',
  name: props.submission,
  auto: true,
});
console.log('ExamGraded submisisonDetails:', submisisonDetails); // Debugging log

watch(
  () => submisisonDetails.doc,
  (newDoc) => {
    submisisonDetails.loading = false;
    console.log('ExamGraded updated with new submission details:', newDoc); // Debugging log
  }
);

const formatTime = (seconds) => {
  if (!seconds) return '00:00:00'; // Handle null or undefined values
  const hrs = Math.floor(seconds / 3600).toString().padStart(2, '0');
  const mins = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
  const secs = (seconds % 60).toString().padStart(2, '0');
  return `${hrs}:${mins}:${secs}`;
};
</script>