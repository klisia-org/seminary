<template>
	<Dialog
		v-model="show"
        :options="{
            title='Add Course Assessment',
            size: 'lg',
            actions: [
                {
                    label: 'Create',
                    variant: 'solid',
                    onClick: (close) => addCourseAssessment(close),
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
                  />
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
        </template>

</Dialog>
</template>
<script setup>
import {
	Button,
	createResource,
	Dialog,
	FormControl,
	Switch,
    createDocumentResource
} from 'frappe-ui'
import { reactive, watch } from 'vue'
import { showToast, getFileSize } from '@/utils/'
import { capture } from '@/telemetry'
import { useSettings } from '@/stores/settings'
import {createDialog} from '@/utils/dialogs'

const $dialog = createDialog

const show = defineModel()
const CourseAssessment = defineModel('CourseAssessment')
const settingsStore = useSettings()

const props = defineProps({
  courseName: {
    type: String,
    required: true,
  },
})

const courseassess = reactive({
	title: '',
	assesscriteria_scac: '',
    type: '',
    weight_scac: '',
    quiz: '',
    exam: '',
    assignment: '',
    extracredit_scac: '',
    fudgepoints_scac: ''

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

const courseAssessmentResource = createDocumentResource({
    doctype: 'Scheduled Course Assess Criteria',
    parent: props.courseName,
    parentType: 'Course Schedule',
    parentField: 'courseassescrit_sc',
    title: courseassess.title,
    assesscriteria_scac: courseassess.assesscriteria_scac,
    type: courseassess.type,
    weight_scac: courseassess.weight_scac,
    quiz: courseassess.quiz,
    exam: courseassess.exam,
    assignment: courseassess.assignment,
    extracredit_scac: courseassess.extracredit_scac,
    fudgepoints_scac: courseassess.fudgepoints_scac,
    course: props.courseName,
   })


const addCourseAssessment = async (close) => {
    try {
        await courseAssessmentResource.save()
        showToast('Course Assessment added successfully')
        close()
    } catch (error) {
        showToast('Failed to add Course Assessment', 'error')
    }
}

</script>
