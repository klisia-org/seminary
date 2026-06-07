<template>
  <div v-if="course" class="border-2 rounded-md min-w-80 mt-2 mb-3 overflow-hidden">
    <div v-if="singleCourse" class="text-3xl font-semibold text-ink-gray-9 text-center px-5 pt-5">
      {{ __("To Do") }}
    </div>
    <div v-else-if="course.data?.course"
      class="bg-surface-gray-1 border-b px-5 py-3 text-base font-semibold text-ink-gray-8 truncate">
      {{ course.data.course }}
    </div>

    <div class="px-5 py-4">
    <!-- Student View -->
    <div v-if="course.data?.course && isStudent" class="text-ink-gray-8">
      <section v-if="missingAssessments.data?.length" class="missing-assessments mt-4">
        <h3 class="text-xl mb-3 font-semibold text-ink-gray-9">{{ __("Missing Assessments") }}</h3>
        <ul>
          <li v-for="assessment in missingAssessments.data" :key="assessment.id" class="text-ink-gray-8">
            {{ assessment.title }} ({{ __('Due') }}: {{ formatDate(assessment.due_date) }})
          </li>
        </ul>
      </section>

      <section v-if="dueSoonAssessments.length" class="due-soon mt-4">
        <h3 class="text-xl font-semibold text-ink-gray-9">{{ __('Due Soon') }}</h3>
        <ul>
          <li v-for="assessment in dueSoonAssessments" :key="assessment.id">
            {{ assessment.title }} ({{ __('Due') }}: {{ formatDate(assessment.due_date) }})
          </li>
        </ul>
      </section>

      <section v-if="!missingAssessments.data?.length && !dueSoonAssessments.length" class="no-assessments mt-4">
        <h3 class="text-xl font-semibold text-ink-gray-9">
          {{ __("Congrats! No assessments for now.") }}
        </h3>
      </section>
    </div>

    <!-- Instructor View -->
    <div v-if="course.data?.course && isInstructor && assessmentsToGrade.data?.length" class="text-ink-gray-8">
      <div v-for="assessmentTG in assessmentsToGrade.data" :key="assessmentTG.title" class="text-ink-gray-8 mt-4">
        <ul>
          <router-link v-if="assessmentTG.Type === 'Exam'"
            :to="{ name: 'ExamSubmissionCS', params: { courseName: props.course, examID: assessmentTG.assessmentID } }"
            class="text-ink-gray-8 mt-4 flex items-center space-x-2">
            <BookOpenCheck class="h-4 w-4 stroke-1.5" />
            <span>{{ assessmentTG.title }} ({{ assessmentTG.ToGrade }} {{ __(" to grade") }})</span>
          </router-link>

          <router-link v-else-if="assessmentTG.Type === 'Assignment'"
            :to="{ name: 'AssignmentSubmissionCS', params: { courseName: props.course, assignmentID: assessmentTG.assessmentID } }"
            class="text-ink-gray-8 flex items-center space-x-2">
            <FileUp class="h-4 w-4 stroke-1.5" />
            <span>{{ assessmentTG.title }} ({{ assessmentTG.ToGrade }} {{ __(" to grade") }})</span>
          </router-link>
        </ul>
      </div>
    </div>

    <div v-if="course.data?.course && isInstructor && !assessmentsToGrade.data?.length" class="text-ink-gray-8">
      <PartyPopper class="size-20 mx-auto stroke-1 text-ink-gray-5 mt-5" />
      <h3 class="text-xl text-center font-semibold text-ink-gray-5 mt-5">
        {{ __('Congrats! No assessments to grade for now.') }}
      </h3>
    </div>

    <!-- Instructor: pending disciplinary actions -->
    <div v-if="course.data?.course && isInstructor && pendingDisciplinary.data?.length"
      class="text-ink-gray-8 mt-6 border-t pt-4">
      <h3 class="text-xl mb-3 font-semibold text-ink-gray-9">{{ __('Disciplinary — Pending Actions') }}</h3>
      <ul class="space-y-3">
        <li v-for="item in pendingDisciplinary.data" :key="item.incident"
          class="flex items-start justify-between gap-2">
          <span class="text-sm">
            <span class="font-medium">{{ item.student_name || item.student }}</span>
            — {{ item.reason_label }} (#{{ item.occurrence_number }})
            <span class="block text-ink-gray-6">{{ item.recommended_actions.join(', ') }}</span>
          </span>
          <Button size="sm" variant="subtle" @click="openRecord(item)">
            {{ __('Record Action') }}
          </Button>
        </li>
      </ul>
      <ReportDisciplinaryIncidentModal
        v-if="recordItem"
        v-model="showRecordModal"
        mode="record"
        :incident="recordItem.incident"
        :student="recordItem.student"
        :student-name="recordItem.student_name"
        :reason="recordItem.reason"
        :reason-label="recordItem.reason_label"
        :occurrence-number="recordItem.occurrence_number"
        :recommended-actions="recordItem.recommended_actions"
        @recorded="onRecorded"
      />
    </div>
    </div>
  </div>
</template>

<script setup>
import { PartyPopper, BookOpenCheck, FileUp } from 'lucide-vue-next'
import { Button } from 'frappe-ui'
import { useCourseToDo } from '@/utils/useCourseToDo'
import ReportDisciplinaryIncidentModal from '@/components/Modals/ReportDisciplinaryIncidentModal.vue'
import dayjs from '@/utils/dayjs'
import { computed, inject, ref } from 'vue'

const user = inject('$user')
const props = defineProps({
  course: {
    type: String,
    required: true,
  },
  singleCourse: {
    type: Boolean,
    default: true,
  },
})

const {
  course,
  assessments,
  missingAssessments,
  assessmentsToGrade,
  pendingDisciplinary,
  isStudent,
  isInstructor,
} = useCourseToDo(props.course, user)

const showRecordModal = ref(false)
const recordItem = ref(null)

const openRecord = (item) => {
  recordItem.value = item
  showRecordModal.value = true
}

const onRecorded = () => {
  showRecordModal.value = false
  pendingDisciplinary.reload()
}

const formatDate = (date) => dayjs(date).fromNow()

const dueSoonAssessments = computed(() => {
  const now = new Date()
  return (assessments?.data ?? [])
    .filter(a => !a.submitted && a.due_date && new Date(a.due_date) >= now)
    .slice(0, 5)
})
</script>

<style scoped>
.course-card-todo {
  padding: 1rem;
  border: 1px solid #ccc;
  border-radius: 8px;
  background-color: #f9f9f9;
}

section {
  margin-bottom: 1.5rem;
}

ul {
  list-style: none;
  padding: 0;
}

li {
  margin-bottom: 0.5rem;
}
</style>