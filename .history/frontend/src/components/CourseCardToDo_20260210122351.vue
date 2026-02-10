<template>
    <div v-if="course" class="border-2 rounded-md min-w-80 p-5">
      <div v-if="singleCourse" class="text-3xl font-semibold text-ink-gray-9 text-center">
        {{ __("To Do") }}
      </div>

      <!-- Student View -->
      <div v-if="course.data?.course && isStudent" class="text-ink-gray-7">
        <section v-if="missingAssessments.data?.length" class="missing-assessments mt-4">
          <h3 class="text-xl font-semibold text-ink-gray-9">{{ __("Missing Assessments") }}</h3>
          <ul>
            <li
              v-for="assessment in missingAssessments.data"
              :key="assessment.id"
              class="text-ink-gray-7"
            >
              {{ assessment.title }} (__Due: {{ formatDate(assessment.due_date) }})
            </li>
          </ul>
        </section>

        <section v-if="assessments?.data?.length" class="due-soon mt-4">
          <h3>Due Soon</h3>
          <ul>
            <li
              v-for="assessment in assessments.data.filter(a => new Date(a.due_date) >= new Date()).slice(0, 5)"
              :key="assessment.id"
            >
              {{ assessment.title }} (Due: {{ formatDate(assessment.due_date) }})
            </li>
          </ul>
        </section>

        <section
          v-if="!missingAssessments.data?.length && !assessments.data?.length"
          class="no-assessments mt-4"
        >
          <h3 class="text-xl font-semibold text-ink-gray-9">
            {{ __("Congrats! No assessments for now.") }}
          </h3>
        </section>
      </div>

      <!-- Instructor View -->
      <div v-if="course.data?.course && isInstructor && assessmentsToGrade.data?.length" class="text-ink-gray-7">
        <div
          v-for="assessmentTG in assessmentsToGrade.data"
          :key="assessmentTG.title"
          class="text-ink-gray-7 mt-4"
        >
          <ul>
            <router-link
              v-if="assessmentTG.Type === 'Exam'"
              :to="{ name: 'ExamSubmissionCS', params: { courseName: props.course, examID: assessmentTG.assessmentID } }"
              class="text-ink-gray-7 mt-4 flex items-center space-x-2"
            >
              <BookOpenCheck class="h-4 w-4 stroke-1.5" />
              <span>{{ assessmentTG.title }} ({{ assessmentTG.ToGrade }} {{ __(" to grade") }})</span>
            </router-link>

            <router-link
              v-else-if="assessmentTG.Type === 'Assignment'"
              :to="{ name: 'AssignmentSubmissionCS', params: { courseName: props.course, assignmentID: assessmentTG.assessmentID } }"
              class="text-ink-gray-7 flex items-center space-x-2"
            >
              <FileUp class="h-4 w-4 stroke-1.5" />
              <span>{{ assessmentTG.title }} ({{ assessmentTG.ToGrade }} {{ __(" to grade") }})</span>
            </router-link>
          </ul>
        </div>
      </div>

      <div v-if="course.data?.course && isInstructor && !assessmentsToGrade.data?.length" class="text-ink-gray-7">
        <PartyPopper class="size-20 mx-auto stroke-1 text-gray-500 mt-5" />
        <h3 class="text-xl text-center font-semibold text-gray-500 mt-5">
          {{ __("Congrats! No assessments to grade for now.") }}
        </h3>
      </div>
    </div>
  </template>

  <script setup>
  import { PartyPopper, BookOpenCheck, FileUp } from 'lucide-vue-next'
  import { useCourseToDo } from '@/utils/useCourseToDo'
  import dayjs from '@/utils/dayjs'
  import { inject } from 'vue'

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
    isStudent,
    isInstructor,
  } = useCourseToDo(props.course, user)

  const formatDate = (date) => dayjs(date).fromNow()
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
