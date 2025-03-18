<template>
  <Dialog
    v-model="show"
    :options="{
      title: 'Add Course Assessment',
      size: 'lg',
      actions: [
        {
          label: 'Create',
          variant: 'solid',
          onClick: (close) => insertCriteria(close),
        },
      ],
    }"
  >
    <template #body-content>
      <div class="space-y-4 text-base">
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
        <p> {{ criteria.type }}</p>
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
        <template v-else>
          <p>Offline</p>
        </template>
        <FormControl
          v-model="criteria.weight_scac"
          :label="__('Weight')"
          class="mb-4"
          :required="true"
          maxlength="10"
        />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import {
  Button,
  createResource,
  Dialog,
  FormControl
} from 'frappe-ui'
import { reactive, watch } from 'vue'
import { showToast } from '@/utils/'
import { useRoute, useRouter } from 'vue-router'
import { useSettings } from '@/stores/settings'
import { createDialog } from '@/utils/dialogs'
import Link from '@/components/Controls/Link.vue'

const $dialog = createDialog
const route = useRoute()
const router = useRouter()
const show = defineModel()
const CourseAssessment = defineModel('CourseAssessment')
const settingsStore = useSettings()
const emit = defineEmits(['assessment-saved'])

const props = defineProps({
  courseName: {
    type: String,
    required: true,
  },
})
console.log('Course Name:', props.courseName)

const courseassess = reactive({
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

const criteria = reactive({
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

const insertCriteria = () => {
  console.log('Inserting Criteria:', criteria)
  if (criteria) {
    fetch('/api/method/seminary.seminary.api.insert_cs_assessment', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ criteria }) // Serialize criteria to JSON string
    })
    .then(response => response.json())
    .then(data => {
     
      showToast('Success', 'Course Assessment added successfully', 'check');
      emit('assessment-saved');
      close();
    })
    .catch(error => {
      console.error('Error:', error)
      showToast('Failed to add Course Assessment', 'error')
    })
  }
}
</script>
