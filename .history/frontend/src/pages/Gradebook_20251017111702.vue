<template>
    <div class="gradebook">
        <header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
			
		</header>
        <h1 class="text-2xl font-bold mt-5 mb-4">Gradebook for {{ course?.data?.course }}</h1>

       
         <!-- No Students Message -->
        <div v-if="students.length === 0" class="text-gray-500 text-center mt-4">
            There are no students enrolled in this course.
        </div>

        <!-- Gradebook Table -->
        <div v-else class="overflow-auto">
            <table class="table-auto border-collapse border border-gray-300  w-full">
                <thead>
                    <tr>
                        <th class="border border-gray-300 px-4 py-2 bg-gray-100">Student</th>
                        <th
                            v-for="assessment in sortedAssessments"
                            :key="assessment.assessment_criteria"
                            class="border border-gray-300 px-4 py-2 bg-gray-100"
                        >
                            <router-link
                                v-if="assessment.type === 'Exam'"
                                :to="{ name: 'ExamSubmissionCS', params: { courseName: props.courseName, examID: assessment.exam } }"
                                class="underline"
                            >
                                {{ assessment.title }}
                                <span v-if="assessment.due_date" class="block text-gray-500 text-sm">
                                    ({{ formatDueDate(assessment.due_date) }})
                                </span>
                            </router-link>
                            <router-link
                                v-else-if="assessment.type === 'Assignment'"
                                :to="{ name: 'AssignmentSubmissionCS', params: { courseName: props.courseName, assignmentID: assessment.assignment } }"
                                class="underline"
                            >
                                {{ assessment.title }}
                                <span v-if="assessment.due_date" class="block text-gray-500 text-sm">
                                    ({{ formatDueDate(assessment.due_date) }})
                                </span>
                            </router-link>
                            <router-link
                                v-else-if="assessment.type === 'Quiz'"
                                :to="{ name: 'QuizSubmissionCS', params: { courseName: props.courseName, quizID: assessment.quiz } }"
                                class="underline"
                            >
                                {{ assessment.title }}
                                <span v-if="assessment.due_date" class="block text-gray-500 text-sm">
                                    ({{ formatDueDate(assessment.due_date) }})
                                </span>
                            </router-link>
                            <router-link
                                v-else-if="assessment.type === 'Discussion'"
                                :to="{ name: 'DiscussionActivitySubmissionList', params: { discussionID: assessment.discussion } }"
                                class="underline"
                            >
                                {{ assessment.title }}
                                <span v-if="assessment.due_date" class="block text-gray-500 text-sm">
                                    ({{ formatDueDate(assessment.due_date) }})
                                </span>
                            </router-link>
                            <span v-else>
                                {{ assessment.title }}
                                <span v-if="assessment.due_date" class="block text-gray-500 text-sm">
                                    ({{ formatDueDate(assessment.due_date) }})
                                </span>
                            </span>
                        </th>
                    </tr>
                </thead>
                <tbody>
                    <tr v-for="student in students" :key="student.student_card">
                         <!-- Student Name with Send Icon -->
            <td class="border border-gray-300 px-4 py-2 relative">
                <Tooltip 
                :text="`Program: ${student.program_std_scr}\nAudit: ${student.audit_bool ? 'Yes' : 'No'} \n Active: ${student.active ? 'Yes' : 'No'}`"
                placement="bottom"
                arrow-class="fill-surface-white"
                
              >
              <span>{{ student.stuname_roster }}</span>
              </Tooltip>
             <Tooltip :text="`Send Email to ${student.stuname_roster}`" placement="bottom" arrow-class="fill-surface-white">
                <a :href="`mailto:${student.stuemail_rc}`">
                  <Send
                    class="absolute right-2 top-2 text-blue-300 cursor-pointer"
                  />
                </a>
              </Tooltip>
           
            </td>
                        <td
                            v-for="assessment in assessments"
                            :key="assessment.assessment_criteria"
                            :class="assessment.extracredit_scac ? 'bg-blue-100' : ''"
                            class="border border-gray-300 px-4 py-2 text-center relative"
                        >
                            <!-- Extra Credit Field -->
                            <div v-if="assessment.extracredit_scac">
                                <input
                                    type="number"
                                    class="w-full text-center border border-gray-300 rounded"
                                    :value="getExtraCredit(student, assessment)"
                                    @input="markExtraCreditAsChanged(student, assessment, $event.target.value)"
                                />
                            </div>
                            <!-- Regular Grade Field -->
                            <div v-else>
                                <input
                                    type="number"
                                    class="w-full text-center border border-gray-300 rounded"
                                    :value="getRegularGrade(student, assessment)"
                                    @input="markRegularGradeAsChanged(student, assessment, $event.target.value)"
                                />
                            </div>
                            <Save
                                v-if="isCellChanged(student, assessment)"
                                class="absolute right-12 top-4 text-blue-300"
                                @click="saveCell(student, assessment)"
                            >
                                
                            </Save>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
     
    </div>
</template>

<script setup>
import { Button, Breadcrumbs, createResource, createDocumentResource,  Tooltip, Dialog, call, toast } from 'frappe-ui'
import { getCurrentInstance, inject, ref, computed, watch } from 'vue'
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/vue'
import {
	Check,
    Send,
	CircleChevronRight,
    Save,
	FileText,
	FilePenLine,
	CircleHelp,
	MonitorPlay,
	BookOpenCheck,
	Trash2,
	FileUp,
} from 'lucide-vue-next'
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
const course = createResource({
	url: 'seminary.seminary.utils.get_course_details',
	cache: ['course', props.courseName],
	params: {
		course: props.courseName,
	},
	auto: true,
}) //Neded for the breadcrumbs

// Gradebook resource
const gradebook = createResource({
  url: 'seminary.seminary.utils.get_gradebook',
  cache: ['gradebook', props.courseName],
  params: {
    course: props.courseName,
  },
  auto: true,
  onSuccess(data) {
    students.value = data.map((student) => ({
      ...student,
      assessments: student.assessments.map((assessment) => ({
        ...assessment,
        rawscore_card: assessment.rawscore_card || 0,
        actualextrapt_card: assessment.actualextrapt_card || 0, // Default to 0 if undefined
      })),
    }));
    assessments.value = data[0]?.assessments || [];
  },
  onError(err) {
    console.error('Error loading gradebook:', err);
  },
});

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

// Save an individual cell
const saveCell = async (student, assessment) => {
  const cell = student.assessments.find(
    (a) => a.assessment_criteria === assessment.assessment_criteria
  );
  if (!cell) return;

  try {
    const fieldToUpdate = assessment.extracredit_scac ? 'actualextrapt_card' : 'rawscore_card';
    const valueToUpdate = assessment.extracredit_scac ? cell.actualextrapt_card : cell.rawscore_card;

    console.log('Saving cell:', cell.name, 'with value:', valueToUpdate); // Debugging

    // Call the backend to save the updated value
    await call('frappe.client.set_value', {
      doctype: 'Course Assess Results Detail',
      name: cell.name,
      fieldname: fieldToUpdate,
      value: valueToUpdate,
    });

    // Remove the cell from the changedCells tracker
    delete changedCells.value[cell.name];
    toast.success(__('Grade saved successfully'));
  } catch (error) {
    console.error('Error saving cell:', error);
    toast.error(err.messages?.[0] || err)
  }
};

watch(
  () => route.fullPath,
  (newVal, oldVal) => {
    // Call your data loading function here
    gradebook.reload();
  },
  { immediate: true }
);
const formatDueDate = (dateString) => {
  if (!dateString) return ''; // Handle empty or undefined dates

  const date = new Date(dateString); // Parse the date string
  if (isNaN(date)) return ''; // Handle invalid dates

  // Format the date to show only day and month
  return new Intl.DateTimeFormat(undefined, { day: '2-digit', month: 'short' }).format(date);
};

const breadcrumbs = computed(() => {
	let items = [{ label: 'Courses', route: { name: 'Courses' } }]
	items.push({
		label: course?.data?.course,
		route: { name: 'CourseDetail', params: { courseName: props.courseName } },
	})
    items.push({
        label: 'Gradebook',
        route: { name: 'Gradebook', params: { courseName: props.courseName} },
    })
	return items
})
</script>