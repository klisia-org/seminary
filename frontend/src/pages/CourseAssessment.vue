<template>
  <div class="">
    <div class="grid md:grid-cols-[70%,30%] h-full">
      <div>
        <header
          class="sticky top-0 z-10 flex flex-col md:flex-row md:items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
        >
          <Breadcrumbs class="h-7" :items="breadcrumbs" />
          <div v-if="totalPoints !== 100" class="flex items-center mt-3 md:mt-0">
            <Tooltip 
              :text="__('Save only allowed when Total Points = 100')" placement="bottom">
              <Button variant="subtle" class="ml-2">
                <span>
                  {{ __('Adjust totals to save') }}
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
        <div class="mt-5 mb-10">
          <div class="container mb-5">
            <div v-if="!course.data" class="text-lg font-semibold mb-4">
              {{ __('Assessment Criteria') }}
            </div>
            <div v-else class="text-lg font-semibold mb-4">
              {{ __('Assessment Criteria for ' + course.data.course) }}
            </div>
            <div :class="{'flex justify-between mb-4 p-3 text-xl': true, 'bg-red-400 rounded': totalPoints !== 100}">
              <div>
                <strong>{{ __('Total Points') }}:</strong> {{ totalPoints }}
              </div>
              <div>
                <strong>{{ __('Max Fudge Points') }}:</strong> {{ maxFudgePoints }}
              </div>
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
                  
                  <Link
                    v-if="criteria.type === 'Quiz'"
                    v-model="criteria.quiz"
                    doctype="Quiz"
                    :label="__('Select a Quiz')"
                    :required="true"
                    :onCreate="(value, close) => redirectToForm()"
                  />
                  <Link
                    v-else-if="criteria.type === 'Exam'"
                    v-model="criteria.exam"
                    doctype="Exam Activity"
                    :label="__('Select an Exam')"
                    :required="true"
                  />
                  <Link
                    v-else-if="criteria.type === 'Assignment'"
                    v-model="criteria.assignment"
                    doctype="Assignment Activity"
                    :label="__('Select an Assignment')"
                    :required="true"
                    :onCreate="(value, close) => redirectToForm()"
                  />
                  <template v-else>
                    <p>Offline</p>
                  </template>
                 
                  <FormControl
                    v-model="criteria.extracredit_scac"
                    :label="__('Is Extra Credit?')"
                    type="checkbox"
                    :required="false"
                    class="mb-4"
                    :default="false"
                    />
                    
                    <div v-if="criteria.extracredit_scac" class="mb-4 light-blue-bg p-2 rounded">
                    <FormControl
                      v-model="criteria.fudgepoints_scac"
                      :label="__('Fudge Points')"
                      type="float"
                      :required="true"
                    />
                  </div>
                  <div v-else class="mb-4">
                    <FormControl
                      v-model="criteria.weight_scac"
                      :label="__('Weight')"
                      type="float"
                      class="max-w-14ch"
                      :required="true"
                    />
                  </div>
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
import { createResource, Breadcrumbs, Button, FormControl, Tooltip } from 'frappe-ui'
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
          title: item.title || '',
          assesscriteria_scac: item.assesscriteria_scac || '',
          type: item.type || '',
          weight_scac: item.weight_scac || 0,
          quiz: item.quiz || '',
          exam: item.exam || '',
          assignment: item.assignment || '',
          creator: item.creator || '',
          extracredit_scac: item.extracredit_scac || 0,
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
        extracredit_scac: assessments.data.extracredit_scac || 0,
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
    extracredit_scac: 0,
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
    showToast('Error', 'Please fill in all required fields', 'error');
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
        showToast('Success', 'Course updated successfully', 'check');
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
      criteria.type = data.data.type;
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
</style>