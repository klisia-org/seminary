<template>
  <div class="gradebook">
    <header class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
      <Breadcrumbs class="h-7" :items="breadcrumbs" />

    </header>
    <h1 class="text-2xl font-bold mt-5 mb-4 ml-5">{{ __('Gradebook for') }} {{ course?.data?.course }}</h1>
    <div class="flex items-center gap-2 mb-4 ml-5">
      <Button v-if="hasUnsavedChanges" variant="solid" @click="saveAllChanges">
        <template #prefix>
          <Save class="h-4 w-4" />
        </template>
        {{ __('Save All Changes') }} ({{ Object.keys(changedCells).length }})
      </Button>
      <span v-if="hasUnsavedChanges" class="text-sm text-gray-500">
        {{ __('or press Ctrl+S') }}
      </span>
    </div>
    <!-- No Students Message -->
    <div v-if="students.length === 0" class="text-gray-500 text-center mt-4">
      {{ __('There are no students enrolled in this course.') }}
    </div>

    <!-- Gradebook Table -->
    <div v-else class="overflow-x-auto mx-2 sm:mx-5">
      <table class="min-w-full border-collapse border border-gray-300">
        <thead>
          <!-- Assessment Titles Row -->
          <tr>
            <th class="sticky left-0 z-10 border border-gray-300 bg-gray-100 px-2 py-2 sm:px-4 min-w-[180px]">
              {{ __('Student') }}
            </th>
            <th v-for="assessment in sortedAssessments" :key="assessment.assessment_criteria"
              :class="assessment.extracredit_scac ? 'bg-blue-50' : 'bg-gray-100'"
              class="border border-gray-300 px-2 py-2 sm:px-4 min-w-[120px] text-sm">
              <div class="flex flex-col items-center gap-0.5">
                <router-link v-if="assessment.type === 'Exam'"
                  :to="{ name: 'ExamSubmissionCS', params: { courseName: props.courseName, examID: assessment.exam } }"
                  class="text-blue-600 hover:text-blue-800 underline text-center">
                  {{ assessment.title }}
                </router-link>
                <router-link v-else-if="assessment.type === 'Assignment'"
                  :to="{ name: 'AssignmentSubmissionCS', params: { courseName: props.courseName, assignmentID: assessment.assignment } }"
                  class="text-blue-600 hover:text-blue-800 underline text-center">
                  {{ assessment.title }}
                </router-link>
                <router-link v-else-if="assessment.type === 'Quiz'"
                  :to="{ name: 'QuizSubmissionCS', params: { courseName: props.courseName, quizID: assessment.quiz } }"
                  class="text-blue-600 hover:text-blue-800 underline text-center">
                  {{ assessment.title }}
                </router-link>
                <router-link v-else-if="assessment.type === 'Discussion'"
                  :to="{ name: 'DiscussionActivitySubmissionCS', params: { courseName: props.courseName, discussionID: assessment.discussion } }"
                  class="text-blue-600 hover:text-blue-800 underline text-center">
                  {{ assessment.title }}
                </router-link>
                <span v-else class="text-center">
                  {{ assessment.title }}
                </span>

                <span v-if="assessment.due_date" class="text-xs text-gray-400">
                  {{ formatDueDate(assessment.due_date) }}
                </span>
              </div>
            </th>
          </tr>

          <!-- Weight Row -->
          <tr>
            <td
              class="sticky left-0 z-10 border border-gray-300 bg-gray-50 px-2 py-1 sm:px-4 text-xs text-gray-500 font-medium">
              {{ __('Weight') }}
            </td>
            <td v-for="assessment in sortedAssessments" :key="'weight-' + assessment.assessment_criteria"
              :class="assessment.extracredit_scac ? 'bg-blue-50' : 'bg-gray-50'"
              class="border border-gray-300 px-2 py-1 text-center text-xs text-gray-500 font-medium">
              <span v-if="assessment.extracredit_scac" class="italic">
                {{ __('Extra') }}
              </span>
              <span v-else>
                {{ assessment.weight_scac }}%
              </span>
            </td>
          </tr>
        </thead>

        <tbody>
          <tr v-for="student in students" :key="student.student_card" class="hover:bg-gray-50 transition-colors">
            <!-- Student Name -->
            <td class="sticky left-0 z-10 border border-gray-300 bg-white px-2 py-2 sm:px-4">
              <div class="flex items-center justify-between gap-1">
                <Tooltip
                  :text="`${__('Program')}: ${student.program_std_scr}\n${__('Audit')}: ${student.audit_bool ? __('Yes') : __('No')}\n${__('Active')}: ${student.active ? __('Yes') : __('No')}`"
                  placement="bottom" arrow-class="fill-surface-white">
                  <span class="truncate text-sm font-medium max-w-[140px]">
                    {{ student.stuname_roster }}
                  </span>
                </Tooltip>

                <Tooltip :text="`${__('Send Email to')} ${student.stuname_roster}`" placement="bottom"
                  arrow-class="fill-surface-white">
                  <a :href="`mailto:${student.stuemail_rc}`"
                    class="shrink-0 rounded p-1 text-gray-400 transition-colors hover:bg-blue-50 hover:text-blue-500">
                    <Send class="h-3.5 w-3.5 sm:h-4 sm:w-4" />
                  </a>
                </Tooltip>
              </div>
            </td>

            <!-- Grade Cells -->
            <td v-for="assessment in sortedAssessments" :key="assessment.assessment_criteria"
              :class="assessment.extracredit_scac ? 'bg-blue-50' : ''"
              class="border border-gray-300 px-1 py-1.5 sm:px-2">
              <div class="flex items-center gap-1">
                <input type="number"
                  class="w-full min-w-[50px] text-center text-sm border border-gray-200 rounded px-1 py-1 focus:border-blue-400 focus:ring-1 focus:ring-blue-200 outline-none transition-colors"
                  :class="isCellChanged(student, assessment) ? 'border-blue-400 bg-blue-50' : ''"
                  :value="assessment.extracredit_scac ? getExtraCredit(student, assessment) : getRegularGrade(student, assessment)"
                  @input="assessment.extracredit_scac
                    ? markExtraCreditAsChanged(student, assessment, $event.target.value)
                    : markRegularGradeAsChanged(student, assessment, $event.target.value)" />
                <button v-if="isCellChanged(student, assessment)"
                  class="shrink-0 rounded p-0.5 text-blue-400 hover:text-blue-600 hover:bg-blue-100 transition-colors"
                  @click="saveCell(student, assessment)">
                  <Save class="h-3.5 w-3.5" />
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>


  </div>
</template>

<script setup>
import { Breadcrumbs, Button, createResource, Tooltip, call, toast } from 'frappe-ui'
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { Send, Save } from 'lucide-vue-next'
import { useRoute } from 'vue-router';
const route = useRoute();
const props = defineProps({
  courseName: {
    type: String,
    required: true,
  },
})

const students = ref([]); // Array of students
const assessments = ref([]); // Array of assessment criteria
const changedCells = ref({}); // Track changed cells

// onMounted(() => {
//   if (!user.data?.is_moderator && !user.data?.is_instructor) {
//     window.location.href = '/login'
//   }
//   capture('gradebook_opened')
//   window.addEventListener('keydown', keyboardShortcut)
// })

const course = createResource({
  url: 'seminary.seminary.utils.get_course_details',
  params: {
    course: props.courseName,
  },
  auto: true,
})

const gradebook = createResource({
  url: 'seminary.seminary.utils.get_gradebook',
  params: {
    course: props.courseName,
  },
  auto: true,
  onSuccess(data) {
    if (!data || data.length === 0) {
      students.value = []
      assessments.value = []
      return
    }
    students.value = data.map((student) => ({
      ...student,
      assessments: student.assessments.map((assessment) => ({
        ...assessment,
        rawscore_card: assessment.rawscore_card || 0,
        actualextrapt_card: assessment.actualextrapt_card || 0,
      })),
    }))
    assessments.value = data[0]?.assessments || []
  },
  onError(err) {
    console.error('Error loading gradebook:', err)
  },
})

//Sort Assessments by due_date and alphabetically
const sortedAssessments = computed(() => {
  return [...assessments.value].sort((a, b) => {
    // Sort by due_date (earlier dates first, null dates last)
    if (!a.due_date && b.due_date) return 1; // `a` has no due_date, move it to the right
    if (a.due_date && !b.due_date) return -1; // `b` has no due_date, move it to the right
    if (a.due_date && b.due_date) {
      const dateA = new Date(a.due_date);
      const dateB = new Date(b.due_date);
      if (dateA < dateB) return -1; // Earlier date first
      if (dateA > dateB) return 1; // Later date last
    }

    // If due_date is the same or null, sort alphabetically by title
    return a.title.localeCompare(b.title);
  });
});

// Get cell data for a specific student and assessment
const getCellData = (student, assessment) => {
  const cell = student.assessments.find(
    (a) => a.assessment_criteria === assessment.assessment_criteria
  );
  return assessment.extracredit_scac ? cell.actualextrapt_card : cell.rawscore_card;
};

// Get extra credit for a specific student and assessment
const getExtraCredit = (student, assessment) => {
  const cell = student.assessments.find(
    (a) => a.assessment_criteria === assessment.assessment_criteria
  );
  return cell ? cell.actualextrapt_card : 0;
};

// Get regular grade for a specific student and assessment
const getRegularGrade = (student, assessment) => {
  const cell = student.assessments.find(
    (a) => a.assessment_criteria === assessment.assessment_criteria
  );
  return cell ? cell.rawscore_card : 0;
};

// Mark a cell as changed
const markCellAsChanged = (student, assessment, value) => {
  const cell = student.assessments.find(
    (a) => a.assessment_criteria === assessment.assessment_criteria
  );
  if (cell) {
    if (assessment.extracredit_scac) {
      cell.actualextrapt_card = parseFloat(value) || 0; // Update extra credit points
    } else {
      cell.rawscore_card = parseFloat(value) || 0; // Update regular score
    }
    changedCells.value[cell.name] = true; // Mark the cell as changed
  }
};

// Mark extra credit as changed
const markExtraCreditAsChanged = (student, assessment, value) => {
  const cell = student.assessments.find(
    (a) => a.assessment_criteria === assessment.assessment_criteria
  );
  if (cell) {
    cell.actualextrapt_card = parseFloat(value) || 0; // Update extra credit points
    changedCells.value[cell.name] = true; // Mark the cell as changed
  }
};

// Mark regular grade as changed
const markRegularGradeAsChanged = (student, assessment, value) => {
  const cell = student.assessments.find(
    (a) => a.assessment_criteria === assessment.assessment_criteria
  );
  if (cell) {
    cell.rawscore_card = parseFloat(value) || 0; // Update regular score
    changedCells.value[cell.name] = true; // Mark the cell as changed
  }
};

// Check if a cell is changed
const isCellChanged = (student, assessment) => {
  const cell = student.assessments.find(
    (a) => a.assessment_criteria === assessment.assessment_criteria
  );
  return cell && changedCells.value[cell.name];
};

// Save a single cell (existing - for individual save button)
const saveCell = async (student, assessment) => {
  const cell = student.assessments.find(
    (a) => a.assessment_criteria === assessment.assessment_criteria
  )
  if (!cell) return

  try {
    const fieldToUpdate = assessment.extracredit_scac ? 'actualextrapt_card' : 'rawscore_card'
    const valueToUpdate = assessment.extracredit_scac ? cell.actualextrapt_card : cell.rawscore_card

    await call('frappe.client.set_value', {
      doctype: 'Course Assess Results Detail',
      name: cell.name,
      fieldname: fieldToUpdate,
      value: valueToUpdate,
    })

    delete changedCells.value[cell.name]
    toast.success(__('Grade saved successfully'))
  } catch (error) {
    console.error('Error saving cell:', error)
    toast.error(error.messages?.[0] || error)
  }
}

// Save ALL changed cells at once
const saveAllChanges = async () => {
  const changedKeys = Object.keys(changedCells.value)
  if (changedKeys.length === 0) {
    toast.info(__('No changes to save'))
    return
  }

  let savedCount = 0
  let errors = []

  for (const student of students.value) {
    for (const cell of student.assessments) {
      if (!changedCells.value[cell.name]) continue

      try {
        // Determine which field to save
        const isExtraCredit = assessments.value.find(
          (a) => a.assessment_criteria === cell.assessment_criteria
        )?.extracredit_scac

        const fieldToUpdate = isExtraCredit ? 'actualextrapt_card' : 'rawscore_card'
        const valueToUpdate = isExtraCredit ? cell.actualextrapt_card : cell.rawscore_card

        await call('frappe.client.set_value', {
          doctype: 'Course Assess Results Detail',
          name: cell.name,
          fieldname: fieldToUpdate,
          value: valueToUpdate,
        })

        delete changedCells.value[cell.name]
        savedCount++
      } catch (error) {
        console.error('Error saving cell:', cell.name, error)
        errors.push(cell.name)
      }
    }
  }

  if (errors.length > 0) {
    toast.error(__('Failed to save {0} grade(s)', [errors.length]))
  } else {
    toast.success(__('Saved {0} grade(s) successfully', [savedCount]))
  }
}

// Check if there are unsaved changes
const hasUnsavedChanges = computed(() => {
  return Object.keys(changedCells.value).length > 0
})

// Keyboard shortcut: Ctrl+S to save all
const keyboardShortcut = (e) => {
  if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault()
    saveAllChanges()
  }
}

onMounted(() => {
  window.addEventListener('keydown', keyboardShortcut)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', keyboardShortcut)
})

// Only reload if route changes (e.g., different course)
watch(
  () => route.params.courseName,
  (newVal) => {
    if (newVal) {
      students.value = []
      assessments.value = []
      changedCells.value = {}
      gradebook.reload()
    }
  }
)


const formatDueDate = (dateString) => {
  if (!dateString) return ''; // Handle empty or undefined dates

  const date = new Date(dateString); // Parse the date string
  if (isNaN(date)) return ''; // Handle invalid dates

  // Format the date to show only day and month
  return new Intl.DateTimeFormat(undefined, { day: '2-digit', month: 'short' }).format(date);
};

const breadcrumbs = computed(() => {
  let items = [{ label: __('Courses'), route: { name: 'Courses' } }]
  items.push({
    label: course?.data?.course,
    route: { name: 'CourseDetail', params: { courseName: props.courseName } },
  })
  items.push({
    label: __('Gradebook'),
    route: { name: 'Gradebook', params: { courseName: props.courseName } },
  })
  return items
})
</script>