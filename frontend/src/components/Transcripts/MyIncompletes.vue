<template>
  <!-- Open Incompletes (decisions/119 §1): the date, what is still owed, and a way to ask for more time. -->
  <section v-if="rows.length" class="px-5 py-4" aria-labelledby="my-incompletes">
    <h2 id="my-incompletes" class="text-lg font-bold text-ink-gray-7">{{ __('Incompletes') }}</h2>
    <div v-for="row in rows" :key="row.roster" class="mt-3 rounded-md border border-outline-gray-2 px-4 py-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div class="font-medium text-ink-gray-9">{{ row.course }}</div>
          <div class="text-sm text-ink-gray-6">{{ __('Finish by {0}').format(formatDay(row.until)) }}</div>
        </div>
        <Button v-if="!openRequest(row)" size="sm" variant="subtle" @click="openDialog(row)">{{ __('Ask for More Time') }}</Button>
        <Badge v-else theme="orange" :label="__('Extension requested')" />
      </div>
      <div v-if="row.unsubmitted.length" class="mt-2 text-sm text-ink-gray-7">
        {{ __('Still to hand in: {0}').format(row.unsubmitted.join(', ')) }}
      </div>
      <div v-for="req in row.requests.filter((r) => r.status !== 'Open')" :key="req.name" class="mt-1 text-xs text-ink-gray-5">
        {{ __('Request for {0}: {1}').format(formatDay(req.requested_until), __(req.status)) }}<span v-if="req.decision_note"> · {{ req.decision_note }}</span>
      </div>
    </div>

    <Dialog v-model="form.show" :options="{ title: __('Ask for More Time') }">
      <template #body-content>
        <div class="space-y-3">
          <p class="text-sm text-ink-gray-7">{{ __('The registrar decides, after hearing from your instructor. The school may charge a fee if it is approved.') }}</p>
          <FormControl type="date" :label="__('New completion date')" v-model="form.until" />
          <FormControl type="textarea" :label="__('Reason')" v-model="form.reason" />
        </div>
      </template>
      <template #actions>
        <Button variant="solid" class="w-full" :loading="form.saving" :disabled="!form.until || !form.reason" @click="submit">
          {{ __('Send Request') }}
        </Button>
      </template>
    </Dialog>
  </section>
</template>

<script setup>
import { userLocale } from '@seminary/portal-shell'
import { Badge, Button, Dialog, FormControl, call, createResource, toast } from 'frappe-ui'
import { computed, ref } from 'vue'

const data = createResource({ url: 'seminary.seminary.incompletes.my_incompletes', auto: true, onError: () => { } })
const rows = computed(() => data.data || [])
const openRequest = (row) => row.requests.some((r) => r.status === 'Open')
const formatDay = (value) => (value ? new Date(value + 'T00:00:00').toLocaleDateString(userLocale()) : '')

const form = ref({ show: false, row: null, until: '', reason: '', saving: false })
const openDialog = (row) => { form.value = { show: true, row, until: '', reason: '', saving: false } }
const submit = async () => {
  const f = form.value
  f.saving = true
  try {
    await call('seminary.seminary.incompletes.request_extension', {
      roster: f.row.roster,
      requested_until: f.until,
      reason: f.reason,
    })
    f.show = false
    toast.success(__('Your request was sent to the registrar'))
    data.reload()
  } catch (e) {
    toast.error(e.messages?.[0] || e.message || __('Could not send the request'))
  } finally {
    f.saving = false
  }
}
</script>
