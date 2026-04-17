<template>
  <div>
    <header class="sticky top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5">
      <Breadcrumbs :items="breadcrumbs" />
    </header>

    <div v-if="!allowWithdrawal" class="px-5 py-10">
      <p class="text-ink-gray-5">{{ __('Course withdrawal requests are not available on the Portal. Please contact the registrar.') }}</p>
    </div>

    <div v-else-if="submitted" class="px-5 py-10 text-center space-y-4">
      <div class="text-ink-green-3">
        <CheckCircle class="w-16 h-16 mx-auto" />
      </div>
      <h2 class="text-xl font-bold text-ink-gray-8">{{ __('Withdrawal Request Submitted') }}</h2>
      <p class="text-ink-gray-6">{{ __('Your request has been submitted and is pending review.') }}</p>
      <Button variant="solid" @click="goBack">{{ __('Back to Course Status') }}</Button>
    </div>

    <div v-else class="px-5 py-4 max-w-2xl space-y-6">

      <!-- Course Info (read-only) -->
      <div class="rounded-lg border border-outline-gray-1 bg-surface-gray-1 p-4 space-y-2">
        <h3 class="font-semibold text-ink-gray-8">{{ __('Course Information') }}</h3>
        <div class="grid grid-cols-2 gap-2 text-sm">
          <div>
            <span class="text-ink-gray-5">{{ __('Student') }}:</span>
            <span class="ml-1 text-ink-gray-8">{{ user.data?.full_name }}</span>
          </div>
          <div>
            <span class="text-ink-gray-5">{{ __('Course') }}:</span>
            <span class="ml-1 text-ink-gray-8">{{ course.data?.title || courseName }}</span>
          </div>
        </div>
      </div>

      <!-- Withdrawal Reason -->
      <div class="space-y-2">
        <label class="block text-sm font-medium text-ink-gray-7">{{ __('Reason for Withdrawal') }} *</label>
        <FormControl type="select" v-model="form.withdrawal_reason" :options="reasonOptions"
          :placeholder="__('Select a reason...')" />
        <div v-if="selectedReasonDetails?.student_instructions"
          class="text-sm text-ink-blue-2 bg-surface-blue-1 rounded-lg p-3 border border-outline-blue-1"
          v-html="selectedReasonDetails.student_instructions">
        </div>
      </div>

      <!-- Documentation Upload -->
      <div v-if="selectedReasonDetails?.requires_documentation" class="space-y-2">
        <label class="block text-sm font-medium text-ink-gray-7">
          {{ selectedReasonDetails.documentation_label || __('Required Documentation') }} *
        </label>
        <FormControl type="file" v-model="form.student_documentation" />
      </div>

      <!-- Comment -->
      <div class="space-y-2">
        <label class="block text-sm font-medium text-ink-gray-7">{{ __('Comment (optional)') }}</label>
        <FormControl type="textarea" v-model="form.student_comment" rows="4"
          :placeholder="__('Any additional information you would like to share...')" />
      </div>

      <!-- Withdrawal Scope -->
      <div class="space-y-2">
        <label class="block text-sm font-medium text-ink-gray-7">{{ __('Withdrawal Scope') }} *</label>
        <FormControl type="select" v-model="form.withdrawal_scope" :options="scopeOptions" />
        <p class="text-xs text-ink-gray-5">
          <span v-if="form.withdrawal_scope === 'Single Course'">{{ __('Only this course will be affected.') }}</span>
          <span v-else-if="form.withdrawal_scope === 'All Courses This Term'">{{ __('A withdrawal request will be created for all your courses this term.') }}</span>
          <span v-else>{{ __('You will be withdrawn from all courses and your program enrollment will be deactivated.') }}</span>
        </p>
      </div>

      <!-- Submit -->
      <div class="flex gap-3 pt-2">
        <Button variant="solid" theme="red" @click="submitRequest" :loading="submitting"
          :disabled="!canSubmit">
          {{ __('Submit Withdrawal Request') }}
        </Button>
        <Button variant="subtle" @click="goBack">{{ __('Cancel') }}</Button>
      </div>

      <div v-if="errorMessage" class="text-ink-red-3 text-sm">{{ errorMessage }}</div>
    </div>
  </div>
</template>

<script setup>
import { Breadcrumbs, Button, FormControl, createResource } from 'frappe-ui'
import { ref, computed, inject, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { call } from 'frappe-ui'
import { CheckCircle } from 'lucide-vue-next'

const props = defineProps({
  courseName: { type: String, required: true },
})

const user = inject('$user')
const router = useRouter()
const route = useRoute()

const submitted = ref(false)
const submitting = ref(false)
const errorMessage = ref('')

const form = ref({
  withdrawal_reason: '',
  student_documentation: null,
  student_comment: '',
  withdrawal_scope: 'Single Course',
})

const scopeOptions = [
  { label: __('Single Course'), value: 'Single Course' },
  { label: __('All Courses This Term'), value: 'All Courses This Term' },
  { label: __('Full Program Withdrawal'), value: 'Full Program Withdrawal' },
]

const course = createResource({
  url: 'seminary.seminary.utils.get_course_details',
  cache: ['course', props.courseName],
  params: { course: props.courseName },
  auto: true,
})

const seminarySettings = createResource({
  url: 'frappe.client.get_value',
  params: {
    doctype: 'Seminary Settings',
    fieldname: 'allow_portal_withdrawal',
  },
  auto: true,
})

const allowWithdrawal = computed(() => {
  return seminarySettings.data?.allow_portal_withdrawal === 1
})

const reasons = createResource({
  url: 'frappe.client.get_list',
  params: {
    doctype: 'Withdrawal Reasons',
    fields: ['name', 'label', 'description', 'requires_documentation', 'documentation_label', 'student_instructions'],
    limit_page_length: 0,
  },
  auto: true,
})

const reasonOptions = computed(() => {
  if (!reasons.data) return []
  return reasons.data.map(r => ({
    label: r.label,
    value: r.name,
  }))
})

const selectedReasonDetails = computed(() => {
  if (!form.value.withdrawal_reason || !reasons.data) return null
  return reasons.data.find(r => r.name === form.value.withdrawal_reason)
})

const canSubmit = computed(() => {
  if (!form.value.withdrawal_reason) return false
  if (selectedReasonDetails.value?.requires_documentation && !form.value.student_documentation) return false
  return true
})

const breadcrumbs = computed(() => {
  return [
    { label: __('Courses'), route: { name: 'Courses' } },
    { label: course.data?.title || props.courseName, route: { name: 'CourseDetail', params: { courseName: props.courseName } } },
    { label: __('My Status'), route: { name: 'CourseStatus', params: { courseName: props.courseName } } },
    { label: __('Request Withdrawal') },
  ]
})

async function submitRequest() {
  submitting.value = true
  errorMessage.value = ''

  try {
    const cei = route.query.cei
    const pe = route.query.pe

    if (!cei || !pe) {
      errorMessage.value = __('Missing enrollment information. Please go back and try again.')
      submitting.value = false
      return
    }

    await call('frappe.client.insert', {
      doc: {
        doctype: 'Course Withdrawal Request',
        student: user.data?.student,
        program_enrollment: pe,
        course_enrollment_individual: cei,
        withdrawal_reason: form.value.withdrawal_reason,
        withdrawal_scope: form.value.withdrawal_scope,
        student_comment: form.value.student_comment,
        withdrawal_effective_date: new Date().toISOString().split('T')[0],
      },
    })

    submitted.value = true
  } catch (e) {
    errorMessage.value = e.messages?.[0] || e.message || __('An error occurred. Please try again.')
  } finally {
    submitting.value = false
  }
}

function goBack() {
  router.push({ name: 'CourseStatus', params: { courseName: props.courseName } })
}
</script>
