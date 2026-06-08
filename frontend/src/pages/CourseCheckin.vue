<template>
  <div class="min-h-screen bg-surface-gray-1 px-4 py-6">
    <div class="mx-auto w-full max-w-md">
      <h1 class="text-xl font-semibold text-ink-gray-9 mb-1">{{ __('Class Check-in') }}</h1>
      <p class="text-sm text-ink-gray-6 mb-5">
        {{ __('Enter the code your instructor is showing to mark yourself present.') }}
      </p>

      <div v-if="status.loading" class="flex justify-center py-10">
        <LoadingIndicator class="w-6 h-6 text-ink-gray-5" />
      </div>

      <div
        v-else-if="!openMeetings.length"
        class="rounded-lg border border-outline-gray-2 bg-surface-white p-6 text-center"
      >
        <p class="text-sm text-ink-gray-6">
          {{ __('No class is open for check-in right now.') }}
        </p>
      </div>

      <div v-else class="rounded-lg border border-outline-gray-2 bg-surface-white p-5 space-y-4">
        <FormControl
          v-model="form.meeting"
          type="select"
          :label="__('Class')"
          :options="meetingOptions"
        />

        <FormControl
          v-if="status.data?.requires_code"
          v-model="form.code"
          type="text"
          :label="__('Check-in Code')"
          :description="__('The code shown on screen during class.')"
          @keyup.enter="submit"
        />

        <Button
          variant="solid"
          class="w-full"
          :loading="submitting"
          :disabled="!form.meeting"
          @click="submit"
        >
          {{ __('Check in') }}
        </Button>
      </div>

      <!-- Already checked in today -->
      <div v-if="checkedInMeetings.length" class="mt-6">
        <h2 class="text-xs font-semibold uppercase text-ink-gray-5 mb-2">
          {{ __('Already checked in') }}
        </h2>
        <ul class="space-y-1">
          <li
            v-for="m in checkedInMeetings"
            :key="`${m.course_schedule}__${m.meeting_date}`"
            class="flex items-center gap-2 text-sm text-ink-gray-7"
          >
            <CheckCircle2 class="w-4 h-4 text-ink-green-3" />
            <span>{{ m.course_title }}</span>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Button, FormControl, LoadingIndicator, call, createResource, toast } from 'frappe-ui'
import { CheckCircle2 } from 'lucide-vue-next'

const route = useRoute()

const key = (m) => `${m.course_schedule}__${m.meeting_date}`

const form = reactive({
  meeting: '',
  // Prefilled from a scanned QR deep link (?course=&date=&code=).
  code: route.query.code || '',
})

const status = createResource({
  url: 'seminary.seminary.course_checkin.get_open_course_checkins',
  auto: true,
  onSuccess(data) {
    const open = (data?.meetings || []).filter((m) => !m.already_checked_in)
    if (form.meeting) return
    // Preselect the meeting the QR pointed at, else the first open one.
    const wanted =
      route.query.course && route.query.date
        ? `${route.query.course}__${route.query.date}`
        : null
    form.meeting =
      (wanted && open.find((m) => key(m) === wanted) && wanted) ||
      (open[0] ? key(open[0]) : '')
  },
})

const openMeetings = computed(() =>
  (status.data?.meetings || []).filter((m) => !m.already_checked_in),
)

const checkedInMeetings = computed(() =>
  (status.data?.meetings || []).filter((m) => m.already_checked_in),
)

const meetingOptions = computed(() =>
  openMeetings.value.map((m) => ({
    label: `${m.course_title} — ${m.meeting_date}`,
    value: key(m),
  })),
)

const submitting = ref(false)

async function submit() {
  if (!form.meeting) {
    toast.error(__('Select a class'))
    return
  }
  const [course_schedule, meeting_date] = form.meeting.split('__')
  submitting.value = true
  try {
    const res = await call('seminary.seminary.course_checkin.course_check_in', {
      course_schedule,
      meeting_date,
      code: form.code || null,
    })
    toast.success(res?.status === 'Tardy' ? __('Checked in — marked Tardy') : __('Checked in'))
    form.code = ''
    status.reload()
  } catch (e) {
    toast.error(e.message || __('Failed to check in'))
  } finally {
    submitting.value = false
  }
}
</script>
