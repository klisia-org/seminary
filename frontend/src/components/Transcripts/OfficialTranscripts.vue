<template>
  <!-- Official transcripts (decisions/119 §5): requested here, issued by the school. -->
  <section class="px-5 py-4" aria-labelledby="official-transcripts">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h2 id="official-transcripts" class="text-lg font-bold text-ink-gray-7">{{ __('Official Transcripts') }}</h2>
      <Button variant="solid" @click="openNew">{{ __('Request an Official Transcript') }}</Button>
    </div>
    <p v-if="!requests.length" class="mt-2 text-sm text-ink-gray-5">{{ __('You have not requested an official transcript.') }}</p>
    <table v-else class="mt-3 w-full text-sm">
      <thead>
        <tr class="border-b text-left text-ink-gray-6">
          <th scope="col" class="py-2 px-3 font-medium">{{ __('Requested') }}</th>
          <th scope="col" class="py-2 px-3 font-medium">{{ __('Send To') }}</th>
          <th scope="col" class="py-2 px-3 font-medium">{{ __('Status') }}</th>
          <th scope="col" class="py-2 px-3 font-medium"><span class="sr-only">{{ __('Actions') }}</span></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in requests" :key="r.name" class="border-b align-top">
          <td class="py-2 px-3">{{ formatDay(r.creation) }}</td>
          <td class="py-2 px-3">
            <div>{{ __(r.delivery) }}</div>
            <div v-if="r.recipient_name || r.recipient_email" class="text-xs text-ink-gray-5">
              {{ r.recipient_name || '' }} {{ r.recipient_email || '' }}
            </div>
          </td>
          <td class="py-2 px-3">
            <Badge :theme="theme(r.status)" :label="__(r.status)" />
            <div v-if="r.status === 'On Hold' && r.hold_note" class="mt-1 whitespace-pre-line text-xs text-ink-gray-6">{{ r.hold_note }}</div>
            <div v-if="r.status === 'Awaiting Payment'" class="mt-1 text-xs text-ink-gray-6">
              {{ __('Pay the transcript fee from Fees. The transcript is issued once it is paid.') }}
            </div>
            <div v-if="r.verification_code" class="mt-1 text-xs text-ink-gray-6">
              {{ __('Verification code: {0}').format(r.verification_code) }}
            </div>
          </td>
          <td class="py-2 px-3 text-right">
            <a v-if="r.status === 'Issued' && r.delivery === 'Student' && r.transcript_file" :href="r.transcript_file"
              target="_blank" rel="noopener" class="text-ink-blue-link underline">{{ __('Download') }}</a>
            <Button v-else-if="['Draft', 'On Hold', 'Awaiting Payment'].includes(r.status)" size="sm" variant="ghost"
              @click="cancel(r)">{{ __('Cancel') }}</Button>
          </td>
        </tr>
      </tbody>
    </table>

    <Dialog v-model="form.show" :options="{ title: __('Request an Official Transcript') }">
      <template #body-content>
        <div class="space-y-3">
          <FormControl type="select" :label="__('Program')" v-model="form.program_enrollment"
            :options="[{ label: __('All my programs'), value: '' }, ...enrollments.map((e) => ({ label: e.program, value: e.name }))]" />
          <FormControl type="select" :label="__('Send To')" v-model="form.delivery" :options="deliveries" />
          <FormControl v-if="form.delivery !== 'Student'" :label="__('Recipient')" v-model="form.recipient_name" />
          <FormControl v-if="form.delivery === 'Email'" type="email" :label="__('Recipient Email')" v-model="form.recipient_email" />
          <template v-if="form.delivery === 'Printed copy'">
            <FormControl type="textarea" :label="__('Mailing Address')" v-model="form.mailing_address" />
            <FormControl type="number" :label="__('Copies')" v-model="form.copies" min="1" />
          </template>
          <p class="text-xs text-ink-gray-5">
            {{ __('A hold on your account (for example, fees owed) stops an official transcript until it is lifted. The school may charge a fee.') }}
          </p>
        </div>
      </template>
      <template #actions>
        <Button variant="solid" class="w-full" :loading="form.saving" @click="submit">{{ __('Submit Request') }}</Button>
      </template>
    </Dialog>
  </section>
</template>

<script setup>
import { userLocale } from '@seminary/portal-shell'
import { Badge, Button, Dialog, FormControl, call, createResource, toast } from 'frappe-ui'
import { computed, ref } from 'vue'

const data = createResource({ url: 'seminary.seminary.transcripts.my_requests', auto: true })
const requests = computed(() => data.data?.requests || [])
const enrollments = computed(() => data.data?.enrollments || [])

const deliveries = [
  { label: __('Me (download)'), value: 'Student' },
  { label: __('Someone by email'), value: 'Email' },
  { label: __('A printed copy by mail'), value: 'Printed copy' },
]
const blank = () => ({ show: true, saving: false, program_enrollment: '', delivery: 'Student', recipient_name: '', recipient_email: '', mailing_address: '', copies: 1 })
const form = ref({ ...blank(), show: false })
const openNew = () => { form.value = blank() }

const theme = (status) => ({ Issued: 'green', Ready: 'blue', 'On Hold': 'red', 'Awaiting Payment': 'orange', Cancelled: 'gray' })[status] || 'gray'
const formatDay = (value) => (value ? new Date(value.replace(' ', 'T')).toLocaleDateString(userLocale()) : '')

const submit = async () => {
  const f = form.value
  f.saving = true
  try {
    const res = await call('seminary.seminary.transcripts.new_request', {
      delivery: f.delivery,
      program_enrollment: f.program_enrollment || null,
      recipient_name: f.recipient_name,
      recipient_email: f.recipient_email,
      mailing_address: f.mailing_address,
      copies: f.copies,
    })
    f.show = false
    toast.success(__('Transcript request {0}: {1}').format(res.name, __(res.status)))
    data.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || __('Could not submit the request'))
  } finally {
    f.saving = false
  }
}

const cancel = async (r) => {
  if (!confirm(__('Cancel transcript request {0}?').format(r.name))) return
  try {
    await call('seminary.seminary.transcripts.cancel_request', { name: r.name })
    data.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || __('Could not cancel the request'))
  }
}
</script>
