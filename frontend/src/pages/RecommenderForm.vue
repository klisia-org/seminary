<template>
  <div class="min-h-screen bg-surface-gray-1 py-10 px-4">
    <div class="max-w-2xl mx-auto bg-surface-white rounded-lg shadow p-6">
      <h1 class="text-xl font-bold text-ink-gray-8 mb-2">{{ __('Recommendation Letter') }}</h1>

      <div v-if="request.loading" class="py-12 flex justify-center">
        <LoadingIndicator class="w-8 h-8" />
      </div>

      <div v-else-if="request.error" class="text-sm text-ink-red-3">
        {{ request.error.messages?.[0] || request.error.message || __('Unable to load this request.') }}
      </div>

      <div v-else-if="request.data?.already_submitted" class="text-sm text-ink-green-3">
        {{ __('Thank you. Your recommendation has already been submitted.') }}
      </div>

      <div v-else-if="request.data">
        <p class="text-sm text-ink-gray-6 mb-4">
          {{ __('Dear') }} <span class="font-medium">{{ request.data.recommender_name }}</span>,
          <span v-if="request.data.recommender_role">({{ request.data.recommender_role }})</span>
        </p>
        <p class="text-sm text-ink-gray-6 mb-4">
          {{ __('You have been asked to recommend') }}
          <span class="font-medium">{{ request.data.student_name }}</span>
          {{ __('for') }}
          <span class="font-medium">{{ request.data.program }}</span>.
        </p>
        <p v-if="request.data.token_expires_on" class="text-xs text-ink-gray-4 italic mb-4">
          {{ __('This link expires on') }} {{ request.data.token_expires_on }}.
        </p>

        <label class="block text-sm font-medium text-ink-gray-7 mb-2">{{ __('Your Letter') }}</label>
        <textarea v-model="body" rows="10"
          class="w-full border border-outline-gray-2 rounded-md p-3 text-sm bg-surface-white text-ink-gray-9 mb-4"
          :placeholder="__('Write your recommendation here...')"></textarea>

        <div class="mb-4">
          <label class="block text-sm font-medium text-ink-gray-7 mb-2">
            {{ __('Or attach a signed letter (optional)') }}
          </label>
          <input ref="fileInput" type="file" class="hidden" @change="onFilePicked" />
          <button class="text-ink-blue-3 hover:underline text-sm"
            :disabled="uploading"
            @click="fileInput?.click()">
            {{ uploading ? __('Uploading...') : (attachmentUrl ? __('Replace attachment') : __('Choose file')) }}
          </button>
          <span v-if="attachmentUrl" class="text-xs text-ink-gray-5 ml-3">
            {{ attachmentUrl.split('/').pop() }}
          </span>
        </div>

        <button @click="submit"
          :disabled="submitting || (!body.trim() && !attachmentUrl)"
          class="bg-surface-blue-3 hover:bg-surface-blue-4 text-ink-white px-4 py-2 rounded text-sm font-medium disabled:opacity-50">
          {{ submitting ? __('Submitting...') : __('Submit Recommendation') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { LoadingIndicator, call, createResource, toast } from 'frappe-ui'
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const name = route.params.name
const token = route.query.token

const body = ref('')
const attachmentUrl = ref(null)
const submitting = ref(false)
const uploading = ref(false)
const fileInput = ref(null)

async function onFilePicked(event) {
  const file = event.target.files?.[0]
  if (!file) return
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', name)
    formData.append('token', token)
    const res = await fetch('/api/method/seminary.seminary.recommender.upload_attachment', {
      method: 'POST',
      body: formData,
      headers: { 'X-Frappe-CSRF-Token': window.csrf_token || 'guest' },
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err._error_message || err.exc || `Upload failed (${res.status})`)
    }
    const data = await res.json()
    attachmentUrl.value = data.message?.file_url
    toast.success(__('Attachment uploaded.'))
  } catch (e) {
    toast.error(e.message || __('Upload failed.'))
  } finally {
    uploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

const request = createResource({
  url: 'seminary.seminary.recommender.get_request',
  makeParams() {
    return { name, token }
  },
  auto: true,
})

async function submit() {
  submitting.value = true
  try {
    await call('seminary.seminary.recommender.submit_letter', {
      name,
      token,
      body: body.value,
      attachment_url: attachmentUrl.value,
    })
    toast.success(__('Thank you. Your recommendation has been submitted.'))
    request.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || __('Failed to submit.'))
  } finally {
    submitting.value = false
  }
}
</script>
