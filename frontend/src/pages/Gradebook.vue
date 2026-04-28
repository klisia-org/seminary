<template>
  <div class="gradebook">
    <header class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
      <Breadcrumbs class="h-7" :items="breadcrumbs" />

    </header>
    <h1 class="text-2xl font-bold mt-5 mb-4 ml-5">{{ __('Gradebook for') }} {{ course?.data?.course }}</h1>
    <div v-if="isFinalized" class="mx-5 mb-4 rounded-md bg-surface-blue-1 px-4 py-3 text-sm text-ink-blue-3">
      {{ finalizedMessage }}
    </div>
    <div class="flex items-center gap-2 mb-4 ml-5">
      <Button v-if="hasUnsavedChanges && !isFinalized" variant="solid" @click="saveAllChanges">
        <template #prefix>
          <Save class="h-4 w-4" />
        </template>
        {{ __('Save All Changes') }} ({{ Object.keys(changedCells).length }})
      </Button>
      <span v-if="hasUnsavedChanges && !isFinalized" class="text-sm text-ink-gray-5">
        {{ __('or press Ctrl+S') }}
      </span>
      <Button
        v-if="canSendGrades"
        variant="solid"
        theme="blue"
        :disabled="hasNullGrades || hasUnsavedChanges || sendingGrades"
        @click="sendGrades"
      >
        <template #prefix>
          <Send class="h-4 w-4" />
        </template>
        {{ __('Send Grades') }}
      </Button>
      <span v-if="canSendGrades && hasNullGrades" class="text-sm text-ink-gray-6">
        {{ __('Fill in all grades before sending.') }}
      </span>
      <span v-else-if="canSendGrades && hasUnsavedChanges" class="text-sm text-ink-gray-6">
        {{ __('Save changes before sending.') }}
      </span>
    </div>
    <!-- No Students Message -->
    <div v-if="students.length === 0" class="text-ink-gray-5 text-center mt-4">
      {{ __('There are no students enrolled in this course.') }}
    </div>

    <!-- Gradebook Table -->
    <div v-else class="overflow-x-auto mx-2 sm:mx-5">
      <table class="min-w-full border-collapse border border-outline-gray-2">
        <thead>
          <!-- Assessment Titles Row -->
          <tr>
            <th class="sticky left-0 z-10 border border-outline-gray-2 bg-surface-gray-2 px-2 py-2 sm:px-4 min-w-[180px]">
              {{ __('Student') }}
            </th>
            <th v-for="assessment in sortedAssessments" :key="assessment.assessment_criteria"
              :class="assessment.extracredit_scac ? 'bg-surface-blue-1' : 'bg-surface-gray-2'"
              class="border border-outline-gray-2 px-2 py-2 sm:px-4 min-w-[120px] text-sm">
              <div class="flex flex-col items-center gap-0.5">
                <router-link v-if="assessment.type === 'Exam' && assessment.exam"
                  :to="{ name: 'ExamSubmissionCS', params: { courseName: props.courseName, examID: assessment.exam } }"
                  class="text-ink-blue-link hover:text-ink-blue-3 underline text-center">
                  {{ assessment.title }}
                </router-link>
                <router-link v-else-if="assessment.type === 'Assignment' && assessment.assignment"
                  :to="{ name: 'AssignmentSubmissionCS', params: { courseName: props.courseName, assignmentID: assessment.assignment } }"
                  class="text-ink-blue-link hover:text-ink-blue-3 underline text-center">
                  {{ assessment.title }}
                </router-link>
                <router-link v-else-if="assessment.type === 'Quiz' && assessment.quiz"
                  :to="{ name: 'QuizSubmissionCS', params: { courseName: props.courseName, quizID: assessment.quiz } }"
                  class="text-ink-blue-link hover:text-ink-blue-3 underline text-center">
                  {{ assessment.title }}
                </router-link>
                <router-link v-else-if="assessment.type === 'Discussion' && assessment.discussion"
                  :to="{ name: 'DiscussionActivitySubmissionCS', params: { courseName: props.courseName, discussionID: assessment.discussion } }"
                  class="text-ink-blue-link hover:text-ink-blue-3 underline text-center">
                  {{ assessment.title }}
                </router-link>
                <span v-else class="text-center">
                  {{ assessment.title }}
                </span>

                <span v-if="assessment.due_date" class="text-xs text-ink-gray-4">
                  {{ formatDueDate(assessment.due_date) }}
                </span>
              </div>
            </th>
          </tr>

          <!-- Weight Row -->
          <tr>
            <td
              class="sticky left-0 z-10 border border-outline-gray-2 bg-surface-gray-1 px-2 py-1 sm:px-4 text-xs text-ink-gray-5 font-medium">
              {{ __('Weight') }}
            </td>
            <td v-for="assessment in sortedAssessments" :key="'weight-' + assessment.assessment_criteria"
              :class="assessment.extracredit_scac ? 'bg-surface-blue-1' : 'bg-surface-gray-1'"
              class="border border-outline-gray-2 px-2 py-1 text-center text-xs text-ink-gray-5 font-medium">
              <span v-if="assessment.extracredit_scac" class="italic">
                {{ __('Max Extra: ') }} {{ assessment.fudgepoints_scac }}
              </span>
              <span v-else>
                {{ assessment.weight_scac }}%
              </span>
            </td>
          </tr>
        </thead>

        <tbody>
          <tr v-for="student in students" :key="student.student_card" class="hover:bg-surface-gray-1 transition-colors">
            <!-- Student Name -->
            <td class="sticky left-0 z-10 border border-outline-gray-2 bg-surface-white px-2 py-2 sm:px-4">
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
                    class="shrink-0 rounded p-1 text-ink-gray-4 transition-colors hover:bg-surface-blue-1 hover:text-ink-blue-2">
                    <Send class="h-3.5 w-3.5 sm:h-4 sm:w-4" />
                  </a>
                </Tooltip>
              </div>
            </td>

            <!-- Grade Cells -->
            <td v-for="assessment in sortedAssessments" :key="assessment.assessment_criteria"
              :class="assessment.extracredit_scac ? 'bg-surface-blue-1' : ''"
              class="border border-outline-gray-2 px-1 py-1.5 sm:px-2">
              <div class="flex items-center gap-1">
                <input type="number"
                  :disabled="isFinalized"
                  class="w-full min-w-[50px] text-center text-sm border border-outline-gray-1 bg-surface-white text-ink-gray-9 rounded px-1 py-1 focus:border-outline-blue-1 focus:ring-1 focus:ring-outline-blue-1 outline-none transition-colors disabled:bg-surface-gray-1 disabled:text-ink-gray-6 disabled:cursor-not-allowed"
                  :class="isCellChanged(student, assessment) ? 'border-outline-blue-1 !bg-surface-blue-1 text-ink-blue-2' : ''"
                  :value="assessment.extracredit_scac ? getExtraCredit(student, assessment) : getRegularGrade(student, assessment)"
                  @input="assessment.extracredit_scac
                    ? markExtraCreditAsChanged(student, assessment, $event.target.value)
                    : markRegularGradeAsChanged(student, assessment, $event.target.value)" />
                <button v-if="isCellChanged(student, assessment) && !isFinalized"
                  class="shrink-0 rounded p-0.5 text-ink-blue-2 hover:text-ink-blue-3 hover:bg-surface-blue-2 transition-colors"
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
import { ref, computed, watch, onMounted, onBeforeUnmount, inject } from 'vue'
import { Send, Save } from 'lucide-vue-next'
import { useRoute } from 'vue-router';
const route = useRoute();
const user = inject('$user');
const props = defineProps({
  courseName: {
    type: String,
    required: true,
  },
})

const students = ref([]); // Array of students
const assessments = ref([]); // Array of assessment criteria
const changedCells = ref({}); // Track changed cells
const sendingGrades = ref(false);

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

const courseSchedule = createResource({
  url: 'frappe.client.get_value',
  params: {
    doctype: 'Course Schedule',
    fieldname: 'workflow_state',
    filters: { name: props.courseName },
  },
  auto: true,
})

const canSendGrades = computed(() => {
  if (!user?.data) return false;
  const hasRole =
    user.data.is_evaluator ||
    user.data.is_instructor ||
    user.data.is_moderator;
  return hasRole && courseSchedule.data?.workflow_state === 'Grading';
})

const isFinalized = computed(() => {
  const state = courseSchedule.data?.workflow_state;
  return state === 'Closed' || state === 'Cancelled';
})

const finalizedMessage = computed(() => {
  if (courseSchedule.data?.workflow_state === 'Cancelled') {
    return __('This course has been cancelled. The gradebook is read-only.');
  }
  return __('Grades for this course have already been sent. The gradebook is read-only.');
})

const hasNullGrades = computed(() => {
  for (const student of students.value) {
    if (!student.active || student.audit_bool) continue;
    for (const def of assessments.value) {
      const cell = student.assessments.find(
        (a) => a.assessment_criteria === def.assessment_criteria
      );
      if (!cell || !cell.graded_card) return true;
    }
  }
  return false;
})

const sendGrades = async () => {
  if (!confirm(__('Send all grades and close the course? This finalizes grades on the transcript and cannot be undone.'))) return;
  sendingGrades.value = true;
  try {
    await call('seminary.seminary.api.send_grades', {
      doc: JSON.stringify({ name: props.courseName }),
    });
    toast.success(__('Grades sent successfully'));
    courseSchedule.reload();
    gradebook.reload();
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || __('Failed to send grades'));
  } finally {
    sendingGrades.value = false;
  }
}

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
        rawscore_card: assessment.rawscore_card ?? null,
        actualextrapt_card: assessment.actualextrapt_card ?? null,
        graded_card: assessment.graded_card ? 1 : 0,
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

// Empty input renders as blank when the cell isn't graded; an actual graded
// zero renders as "0". The graded_card flag is the source of truth (the Float
// column on CARD is NOT NULL DEFAULT 0 — see ADR 013).
const cellInputValue = (cell, field) => {
  if (!cell || !cell.graded_card) return '';
  const raw = cell[field];
  return raw === null || raw === undefined ? '' : raw;
};

const parseGradeInput = (value) => {
  if (value === '' || value === null || value === undefined) return null;
  const num = parseFloat(value);
  return isNaN(num) ? null : num;
};

// Get extra credit for a specific student and assessment
const getExtraCredit = (student, assessment) => {
  const cell = student.assessments.find(
    (a) => a.assessment_criteria === assessment.assessment_criteria
  );
  return cellInputValue(cell, 'actualextrapt_card');
};

// Get regular grade for a specific student and assessment
const getRegularGrade = (student, assessment) => {
  const cell = student.assessments.find(
    (a) => a.assessment_criteria === assessment.assessment_criteria
  );
  return cellInputValue(cell, 'rawscore_card');
};

const applyCellChange = (cell, field, value) => {
  const parsed = parseGradeInput(value);
  cell[field] = parsed;
  cell.graded_card = parsed === null ? 0 : 1;
  changedCells.value[cell.name] = true;
};

// Mark a cell as changed
const markCellAsChanged = (student, assessment, value) => {
  const cell = student.assessments.find(
    (a) => a.assessment_criteria === assessment.assessment_criteria
  );
  if (cell) {
    const field = assessment.extracredit_scac ? 'actualextrapt_card' : 'rawscore_card';
    applyCellChange(cell, field, value);
  }
};

// Mark extra credit as changed
const markExtraCreditAsChanged = (student, assessment, value) => {
  const cell = student.assessments.find(
    (a) => a.assessment_criteria === assessment.assessment_criteria
  );
  if (cell) {
    applyCellChange(cell, 'actualextrapt_card', value);
  }
};

// Mark regular grade as changed
const markRegularGradeAsChanged = (student, assessment, value) => {
  const cell = student.assessments.find(
    (a) => a.assessment_criteria === assessment.assessment_criteria
  );
  if (cell) {
    applyCellChange(cell, 'rawscore_card', value);
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
    // CARD's grade column is NOT NULL DEFAULT 0; coerce null to 0 at the
    // boundary and let graded_card carry the real "ungraded" signal.
    const dbValue = valueToUpdate === null || valueToUpdate === undefined ? 0 : valueToUpdate

    await call('frappe.client.set_value', {
      doctype: 'Course Assess Results Detail',
      name: cell.name,
      fieldname: {
        [fieldToUpdate]: dbValue,
        graded_card: cell.graded_card,
      },
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
        const dbValue = valueToUpdate === null || valueToUpdate === undefined ? 0 : valueToUpdate

        await call('frappe.client.set_value', {
          doctype: 'Course Assess Results Detail',
          name: cell.name,
          fieldname: {
            [fieldToUpdate]: dbValue,
            graded_card: cell.graded_card,
          },
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