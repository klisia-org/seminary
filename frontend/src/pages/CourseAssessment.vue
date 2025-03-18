<template>
  <div class="">
    <div class="grid md:grid-cols-[70%,30%] h-full">
      <div>
        <header
          class="sticky top-0 z-10 flex flex-col md:flex-row md:items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
        >
          <Breadcrumbs class="h-7" :items="breadcrumbs" />
          <div class="flex items-center mt-3 md:mt-0">
            <Button variant="solid" @click="submitCourseAssessment()" class="ml-2">
              <span>
                {{ __('Save') }}
              </span>
            </Button>
          </div>
        </header>
        <div class="mt-5 mb-10">
          <div class="container mb-5">
            <div class="text-lg font-semibold mb-4">
              {{ __('Assessment Criteria for this course') }}
            </div>
            <div class="border border-gray-300 p-4 rounded-md">
              <div v-for="(criteria, index) in assessmentCriteria" :key="index" class="border border-gray-300 p-4 mb-4 rounded-md flex items-center">
                <div class="flex-1 grid grid-cols-1 md:grid-cols-5 gap-4">
                  <FormControl
                    v-model="criteria.title"
                    :label="__('Title')"
                    class="mb-4"
                    :required="false"
                  />
                  <Link
                    v-model="criteria.assesscriteria_scac"
                    :label="__('Assessment Criteria')"
                    class="mb-4"
                    doctype="Assessment Criteria"
                    :required="true"
                    @update:modelValue="(val) => { console.log('update:modelValue triggered:', val); fetchType(criteria); }"
                  />
                  <p>Type: {{ criteria.type }}</p>
                  <Link
                    v-if="criteria.type === 'Quiz'"
                    v-model="criteria.quiz"
                    doctype="Quiz"
                    :label="__('Select a Quiz')"
                    :onCreate="(value, close) => redirectToForm()"
                  />
                  <Link
                    v-else-if="criteria.type === 'Exam'"
                    v-model="criteria.exam"
                    doctype="Exam"
                    :label="__('Select an Exam')"
                  />
                  <Link
                    v-else-if="criteria.type === 'Assignment'"
                    v-model="criteria.assignment"
                    doctype="Assignment Activity"
                    :label="__('Select an Assignment')"
                    :onCreate="(value, close) => redirectToForm()"
                  />
                  <Link
                    v-else-if="criteria.type === 'Offline'"
                    v-model="criteria.creator"
                    doctype="User"
                  />
                  <FormControl
                    v-model="criteria.weight_scac"
                    :label="__('Weight')"
                    class="mb-4"
                    :required="true"
                    maxlength="10"
                  />
                </div>
              </div>
            </div>
            <br>
            <Button size="sm" @click="openCourseAssessmentModal">
              {{ __('Add Evaluation') }}
            </Button>
          </div>
        </div>
      </div>
    </div>
  </div>
  <CourseAssessmentModal
    v-model="showCourseAssessmentModal"
    v-model:modalcriteria="modalcriteria"
    :courseName="props.courseName"
    @assessment-saved="onAssessmentSaved" 
  />
</template>

<script setup>
import { createResource, Breadcrumbs, Button, FormControl } from 'frappe-ui'
import { computed, reactive, onMounted, inject, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showToast, updateDocumentTitle } from '@/utils'
import CourseAssessmentModal from '@/components/Modals/CourseAssessmentModal.vue'
import { useSettings } from '@/stores/settings'
import Link from '@/components/Controls/Link.vue'

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
  extracredit_scac: '',
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
console.log(course)

const assessments = createResource({
  url: 'seminary.seminary.utils.get_assessments',
  cache: ['assessments', props.courseName],
  params: {
    course: props.courseName,
  },
  auto: true,
})
console.log(assessments)

const breadcrumbs = computed(() => {
  let items = [{ label: 'Courses', route: { name: 'Courses' } }]
  items.push({
    label: course?.data?.course,
    route: { name: 'CourseDetail', params: { courseName: props.courseName } },
  })
  items.push({
    label: 'Assessment',
    route: { name: 'CourseAssessment', params: { courseName: props.courseName } }
  })
  return items
})

const pageMeta = computed(() => {
  return {
    title: course?.data?.title,
    description: "Assessment Configuration for the course",
  }
})

updateDocumentTitle(pageMeta)

const assessmentCriteria = reactive([]);

onMounted(() => {
  console.log('Assessment data on Mount:', assessments)
  watch(() => assessments.data, (newVal) => {
    if (newVal) {
      loadAssessmentCriteria();
    }
  });
  assessments.reload();
})

function loadAssessmentCriteria() {
  console.log('Assessments data:', assessments.data)
  assessmentCriteria.length = 0; // Clear the array before populating it
  if (assessments.data) {
    if (Array.isArray(assessments.data)) {
      assessments.data.forEach(item => {
        assessmentCriteria.push({
          title: item.title || '',
          assesscriteria_scac: item.assesscriteria_scac || '',
          type: item.type || '',
          weight_scac: item.weight_scac || 0,
          quiz: item.quiz || '',
          exam: item.exam || '',
          assignment: item.assignment || '',
          creator: item.creator || '',
          extracredit_scac: item.extracredit_scac || '',
          fudgepoints_scac: item.fudgepoints_scac || '',
          name: item.name || '',
          parent: item.parent || '',
          parenttype: item.parenttype || '',
          parentfield: item.parentfield || ''
        });
      });
    } else {
      assessmentCriteria.push({
        title: assessments.data.title || '',
        assesscriteria_scac: assessments.data.assesscriteria_scac || '',
        type: assessments.data.type || '',
        weight_scac: assessments.data.weight_scac || 0,
        quiz: assessments.data.quiz || '',
        exam: assessments.data.exam || '',
        assignment: assessments.data.assignment || '',
        creator: assessments.data.creator || '',
        extracredit_scac: assessments.data.extracredit_scac || '',
        fudgepoints_scac: assessments.data.fudgepoints_scac || '',
        name: assessments.data.name || '',
        parent: assessments.data.parent || '',
        parenttype: assessments.data.parenttype || '',
        parentfield: assessments.data.parentfield || ''
      });
    }
  } else {
    console.log('No assessments data found');
  }
  console.log('Assessment criteria:', assessmentCriteria)
  addCriteria();
}

function addCriteria() {
  const newCriteria = reactive({
    title: '',
    assesscriteria_scac: '',
    type: '',
    weight_scac: 0,
    quiz: '',
    exam: '',
    assignment: '',
    extracredit_scac: '',
    fudgepoints_scac: '',
    parent: props.courseName,
    parenttype: 'Course Schedule',
    parentfield: 'courseassescrit_sc'
  });
  
  // Add the new criteria to the reactive array.
  assessmentCriteria.push(newCriteria);
  
  // Attach a watcher to this new criteria.
  watch(
    () => newCriteria.assesscriteria_scac,
    (newVal) => {
      if (newVal) {
        fetchType(newCriteria);
        console.log('New Criteria:', newCriteria);
      }
    }
  );
}

function removeCriteria(index) {
  assessmentCriteria.splice(index, 1);
}

function openCourseAssessmentModal() {
  showCourseAssessmentModal.value = true;
}

function submitCourseAssessment() {
  // Handle form submission logic here
  console.log('Form submitted:', assessmentCriteria);
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
        showToast('Success', 'Course updated successfully', 'check');
      }
    })
    .catch((error) => {
      console.error('Error:', error);
    });
}

async function fetchType(criteria) {
  if (criteria.assesscriteria_scac) {
    console.log('Fetching type for:', criteria.assesscriteria_scac);
    try {
      const response = await fetch(`/api/resource/Assessment Criteria/${criteria.assesscriteria_scac}`);
      const data = await response.json();
      criteria.type = data.data.type;
      console.log('Type:', criteria.type);
    } catch (error) {
      console.error('Error fetching type:', error);
    }
  }
}


function onAssessmentSaved() {
  // Reload the parent's resource (e.g., assessments)
  assessments.reload()
  // Now, close the Modal
  showCourseAssessmentModal.value = false;
  console.log('Parent page reloaded after saving assessment')
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
</style>