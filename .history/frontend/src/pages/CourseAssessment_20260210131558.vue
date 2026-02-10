<template>

  <header
    class="sticky top-0 z-10 flex flex-col md:flex-row md:items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
    <Breadcrumbs class="h-7" :items="breadcrumbs" />
    <div v-if="totalPoints !== 100" class="flex items-center mt-3 md:mt-0">
      <Tooltip :text="__('Save is only allowed when Total Points = 100')" placement="bottom">
        <Button variant="subtle" class="ml-2">
          <span>
            {{ __('Save only allowed when Total Points = 100') }}
          </span>
        </Button>
      </Tooltip>
    </div>
    <div v-else class="flex items-center mt-3 md:mt-0">
      <Button variant="solid" @click="submitCourseAssessment()" class="ml-2">
        <span>
          {{ __('Save') }}
        </span>
      </Button>
    </div>
  </header>
  <div class="mt-5 mb-10 w-full px-5">
    <div class="container max-w-full mb-5 ">
      <div v-if="!course.data" class="text-lg font-semibold mb-4">
        {{ __('Assessment Criteria') }}
      </div>
      <div v-else class="text-lg font-semibold mb-4">
        {{ __('Assessment Criteria for ' + course.data.course) }}
      </div>
      <div
        :class="{ 'max-w-full flex justify-between mb-4 mt-5 text-xl': true, 'bg-red-400 rounded': totalPoints !== 100 }">
        <div>
          <strong>{{ __('Total Points') }}:</strong> {{ totalPoints }}
        </div>
        <div>
          <strong>{{ __('Max Fudge Points') }}:</strong> {{ maxFudgePoints }}
        </div>
      </div>
    </div>
  </div>
  <table class="min-w-full table-auto border-collapse overflow-auto">
    <thead>
      <tr>
        <th class="p-2 border">{{ __('Title') }}</th>
        <th class="p-2 border">{{ __('Assessment Type') }}</th>
        <th class="p-2 border">{{ __('Activity Selection') }}</th>
        <th class="p-2 border">{{ __('Extra Credit?') }}</th>
        <th class="p-2 border">{{ __('Points') }}</th>
        <th class="p-2 border">{{ __('Due Date') }}</th>
        <th class="p-2 border">{{ __('In Lesson') }}</th>
        <th class="p-2 border">{{ __('Delete') }}</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="(criteria, index) in assessmentCriteria" :key="index">
        <td class="p-2 border">
          <FormControl v-model="criteria.title" class="mb-4 overflow-visible" :required="false" />
        </td>
        <td class="p-2 border">
          <Link v-model="criteria.assesscriteria_scac" class="mb-4" doctype="Assessment Criteria" :required="true"
            @update:modelValue="() => fetchType(criteria)" />
        </td>
        <td class="p-2 border">
          <template v-if="criteria.type === 'Quiz'">
            <Link v-model="criteria.quiz" doctype="Quiz" :label="__('Select a Quiz')" :required="true"
              :filters="{ course: course.data.course }" :onCreate="(value, close) => redirectToForm('quiz', close)" />
          </template>
          <template v-else-if="criteria.type === 'Exam'">
            <Link v-model="criteria.exam" doctype="Exam Activity" :label="__('Select an Exam')" :required="true"
              :filters="{ course: course.data.course }" :onCreate="(value, close) => redirectToForm('exam', close)" />
          </template>
          <template v-else-if="criteria.type === 'Assignment'">
            <Link v-model="criteria.assignment" doctype="Assignment Activity" :label="__('Select an Assignment')"
              :required="true" :filters="{ course: course.data.course }"
              :onCreate="(value, close) => redirectToForm('assignment', close)" />
          </template>
          <template v-else-if="criteria.type === 'Discussion'">
            <Link v-model="criteria.discussion" doctype="Discussion Activity"
              :label="__('Select a Discussion Activity')" :required="true" :filters="{ course: course.data.course }"
              :onCreate="(value, close) => redirectToForm('discussion', close)" />
          </template>
          <template v-else>
            <p>{{ __('Offline') }}</p>
          </template>
        </td>
        <td class="p-2 border text-center">
          <FormControl v-model="criteria.extracredit_scac" type="checkbox" :required="false" class="mb-4 inline-block"
            :default="false" />
        </td>
        <td class="p-2 border" style="width: 10%;">
          <div v-if="criteria.extracredit_scac" class="mb-4 light-blue-bg p-2 rounded">
            <FormControl v-model="criteria.fudgepoints_scac" :label="__('Fudge Points')" type="float" class="max-w-14ch"
              :required="true" />
          </div>
          <div v-else class="mb-4">
            <FormControl v-model="criteria.weight_scac" :label="__('Weight')" type="float" class="max-w-14ch"
              :required="true" />
          </div>
        </td>
        <td class="p-2 border">
          <DateTimePicker v-model="criteria.due_date" variant="subtle" :required="false" class="date-column"
            :formatter="formatDate" />
        </td>
        <td class="p-2 border text-center">
          <span v-if="criteria.lesson" class="checkmark">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 text-green-500" fill="none" viewBox="0 0 24 24"
              stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </span>
          <span v-else class="text-red-500">
            ✘
          </span>
        </td>
        <td class="p-2 border text-center align-middle">
          <Button variant="ghost" size="sm" theme="red" @click="removeCriteria(index)">
            <Trash2 class="h-4 w-4 stroke-1.5" />
          </Button>
        </td>
      </tr>
    </tbody>
  </table>

  <div class="mt-5 mb-10 max-w-full px-15">


    <br>
    <Button class="mb-4" size="sm" @click="openCourseAssessmentModal">
      {{ __('Add Evaluation') }}
    </Button>



    <CourseAssessmentModal v-model="showCourseAssessmentModal" v-model:modalcriteria="modalcriteria"
      :courseName="props.courseName" @assessment-saved="onAssessmentSaved" />
  </div>
</template>

<script setup>
import { createResource, Breadcrumbs, Button, FormControl, Tooltip, toast } from 'frappe-ui'
import { computed, reactive, onMounted, inject, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Trash2 } from 'lucide-vue-next'
import { updateDocumentTitle } from '@/utils'
import CourseAssessmentModal from '@/components/Modals/CourseAssessmentModal.vue'
import { useSettings } from '@/stores/settings'
import Link from '@/components/Controls/Link.vue'
import DateTimePicker from 'frappe-ui/src/components/DatePicker/DateTimePicker.vue'


const route = useRoute()
const router = useRouter()
const user = inject('$user')
const settingsStore = useSettings()
const showCourseAssessmentModal = ref(false)
const show = defineModel()

const props = defineProps({
  courseName: {
    type: String,
    required: true,
  },
})

const modalcriteria = reactive({
  title: '',
  assesscriteria_scac: '',
  type: '',
  weight_scac: '',
  quiz: '',
  exam: '',
  assignment: '',
  discussion: '',
  extracredit_scac: 0,
  fudgepoints_scac: '',
  parent: props.courseName,
  parenttype: 'Course Schedule',
  parentfield: 'courseassescrit_sc'
})

const course = createResource({
  url: 'seminary.seminary.utils.get_course_details',
  cache: ['course', props.courseName],
  params: {
    course: props.courseName,
  },
  auto: true,
})

const assessments = createResource({
  url: 'seminary.seminary.utils.get_assessments',
  cache: ['assessments', props.courseName],
  params: {
    course: props.courseName,
  },
  auto: true,
})

const breadcrumbs = computed(() => {
  let items = [{ label: __('Courses'), route: { name: 'Courses' } }]
  items.push({
    label: course?.data?.course,
    route: { name: 'CourseDetail', params: { courseName: props.courseName } },
  })
  items.push({
    label: __('Assessment'),
    route: { name: 'CourseAssessment', params: { courseName: props.courseName } }
  })
  return items
})

const pageMeta = computed(() => {
  return {
    title: course?.data?.title,
    description: __("Assessment Configuration for the course"),
  }
})

updateDocumentTitle(pageMeta)

const assessmentCriteria = reactive([]);

const totalPoints = computed(() => {
  return assessmentCriteria.reduce((sum, criteria) => {
    return criteria.extracredit_scac === 0 ? sum + parseFloat(criteria.weight_scac || 0) : sum;
  }, 0);
});

const maxFudgePoints = computed(() => {
  return assessmentCriteria.reduce((sum, criteria) => {
    return criteria.extracredit_scac ? sum + parseFloat(criteria.fudgepoints_scac || 0) : sum;
  }, 0);
});

onMounted(() => {
  watch(() => assessments.data, (newVal) => {
    if (newVal) {
      loadAssessmentCriteria();
    }
  });
  assessments.reload();
})

function loadAssessmentCriteria() {
  assessmentCriteria.length = 0; // Clear the array before populating it
  if (assessments.data) {
    if (Array.isArray(assessments.data)) {
      assessments.data.forEach(item => {
        assessmentCriteria.push({
          name: item.name || '',
          title: item.title || '',
          assesscriteria_scac: item.assesscriteria_scac || '',
          type: item.type || '',
          weight_scac: item.weight_scac || 0,
          quiz: item.quiz || '',
          exam: item.exam || '',
          assignment: item.assignment || '',
          discussion: item.discussion || '',
          creator: item.creator || '',
          extracredit_scac: item.extracredit_scac || 0,
          fudgepoints_scac: item.fudgepoints_scac || '',
          name: item.name || '',
          parent: item.parent || '',
          parenttype: item.parenttype || '',
          parentfield: item.parentfield || '',
          due_date: item.due_date || '',
          lesson: item.lesson || ''
        });
      });
    } else {
      assessmentCriteria.push({
        name: assessments.data.name || '',
        title: assessments.data.title || '',
        assesscriteria_scac: assessments.data.assesscriteria_scac || '',
        type: assessments.data.type || '',
        weight_scac: assessments.data.weight_scac || 0,
        quiz: assessments.data.quiz || '',
        exam: assessments.data.exam || '',
        assignment: assessments.data.assignment || '',
        discussion: assessments.data.discussion || '',
        creator: assessments.data.creator || '',
        extracredit_scac: assessments.data.extracredit_scac || 0,
        fudgepoints_scac: assessments.data.fudgepoints_scac || '',
        name: assessments.data.name || '',
        parent: assessments.data.parent || '',
        parenttype: assessments.data.parenttype || '',
        parentfield: assessments.data.parentfield || '',
        due_date: assessments.data.due_date || '',
        lesson: assessments.data.lesson || ''
      });
    }
  } else {
    console.log('No assessments data found');
  }
}

function addCriteria() {
  const newCriteria = reactive({
    name: '',
    title: '',
    assesscriteria_scac: '',
    type: '',
    weight_scac: 0,
    quiz: '',
    exam: '',
    assignment: '',
    discussion: '',
    extracredit_scac: 0,
    fudgepoints_scac: '',
    parent: props.courseName,
    parenttype: 'Course Schedule',
    parentfield: 'courseassescrit_sc',
    due_date: '',
    lesson: ''
  });

  // Add the new criteria to the reactive array.
  assessmentCriteria.push(newCriteria);

  // Attach a watcher to this new criteria.
  watch(
    () => newCriteria.assesscriteria_scac,
    (newVal) => {
      if (newVal) {
        fetchType(newCriteria)
      }
    }
  );
}

async function removeCriteria(index) {
  const criteria = assessmentCriteria[index];

  // Confirm deletion (optional)
  if (!confirm(__('Are you sure you want to delete this record?'))) {
    return;
  }

  // Check if the criteria has a `name` (only delete from backend if it exists)
  if (criteria.name) {
    try {
      // Call the deleteAssessmentResource to delete the record from the backend
      await deleteAssessmentResource.reload([criteria.name]);
      console.log(`Record with name ${criteria.name} deleted from backend.`);
      toast.success(__('Assessment criteria deleted successfully'));
    } catch (error) {
      console.error('Error deleting assessment criteria:', error);
      toast.error(__('Failed to delete assessment criteria'));
      return; // Stop further execution if backend deletion fails
    }
  }

  // Remove the record from the frontend array
  assessmentCriteria.splice(index, 1);
  console.log(`Record at index ${index} removed from frontend.`);
}

const deleteAssessmentResource = createResource({
  url: 'seminary.seminary.api.delete_documents',
  makeParams(values) {
    return {
      doctype: 'Scheduled Course Assess Criteria',
      documents: values, // Pass the array of document names
    };
  },
  onSuccess(data) {
    console.log('Delete successful:', data);
  },
  onError(err) {
    console.error('Error deleting documents:', err);
  },
});

function openCourseAssessmentModal() {
  showCourseAssessmentModal.value = true;
}

function validateCriteria() {
  for (const criteria of assessmentCriteria) {
    if (!criteria.assesscriteria_scac) {
      return false;
    }
    if (criteria.type === 'Quiz' && !criteria.quiz) {
      return false;
    }
    if (criteria.type === 'Exam' && !criteria.exam) {
      return false;
    }
    if (criteria.type === 'Assignment' && !criteria.assignment) {
      return false;
    }
    if (criteria.type === 'Discussion' && !criteria.discussion) {
      return false;
    }
    if (!criteria.extracredit_scac && !criteria.weight_scac) {
      return false;
    }
    if (criteria.extracredit_scac && !criteria.fudgepoints_scac) {
      return false;
    }
  }
  return true;
}


function submitCourseAssessment() {
  if (!validateCriteria()) {
    toast.error(__('Please fill in all required fields'));
    return;
  }

  // Handle form submission logic here
  fetch('/api/method/seminary.seminary.api.save_course_assessment', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      course: props.courseName,
      assessment_data: assessmentCriteria,
    }),
  })
    .then(response => response.json())
    .then(data => {
      console.log('Success:', data);
      if (data.message) {
        toast.success(__('Course updated successfully'));
      }
    })
    .catch((error) => {
      console.error('Error:', error);
    });
}

async function fetchType(criteria) {
  if (criteria.assesscriteria_scac) {
    try {
      const response = await fetch(`/api/resource/Assessment Criteria/${criteria.assesscriteria_scac}`);
      const data = await response.json();
      const resolvedType = data?.data?.type || '';
      criteria.type = resolvedType;
      if (resolvedType !== 'Quiz') {
        criteria.quiz = '';
      }
      if (resolvedType !== 'Exam') {
        criteria.exam = '';
      }
      if (resolvedType !== 'Assignment') {
        criteria.assignment = '';
      }
      if (resolvedType !== 'Discussion') {
        criteria.discussion = '';
      }
    } catch (error) {
      console.error('Error fetching type:', error);
    }
  } else {
    criteria.type = '';
    criteria.quiz = '';
    criteria.exam = '';
    criteria.assignment = '';
    criteria.discussion = '';
  }
}

function formatDate(value) {
  if (!value) return '';
  const date = new Date(value);
  const month = String(date.getMonth() + 1).padStart(2, '0'); // Month (MM)
  const day = String(date.getDate()).padStart(2, '0'); // Day (DD)
  const hours = String(date.getHours()).padStart(2, '0'); // Hours (HH)
  const minutes = String(date.getMinutes()).padStart(2, '0'); // Minutes (mm)
  return `${month}/${day} ${hours}:${minutes}`; // Format: MM/DD HH:mm
}

function onAssessmentSaved() {
  // Reload the parent's resource (e.g., assessments)
  assessments.reload()
  // Now, close the Modal
  showCourseAssessmentModal.value = false;
}

function redirectToForm(type, close) {
  const routeMap = {
    quiz: '/seminary/quizzes/new',
    exam: '/seminary/exams/new',
    assignment: '/seminary/assignments/new',
    discussion: '/seminary/discussion-activities/new',
  }
  const target = routeMap?.[String(type || '').toLowerCase()]
  if (typeof close === 'function') {
    close()
  }
  if (target) {
    window.open(target, '_blank')
  }
}
</script>

<style scoped>
.input {
  display: block;
  width: 100%;
  padding: 0.5rem;
  margin-bottom: 0.5rem;
}

.btn {
  margin-right: 0.5rem;
}

.light-blue-bg {
  background-color: #E6F4FF;
}

.date-column {
  max-width: 10ch;
  /* Adjust as needed */
}

.checkmark {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #46B37E !important;
  /* Tailwind's green-500 color */
}
</style>