<template>
	<div class="rounded-md border border-outline-gray-2 p-4">
		<div class="mb-2 flex items-center justify-between">
			<h3 class="font-semibold text-ink-gray-8">{{ placement.location_name || __('Placement') }}</h3>
			<Badge :theme="statusTheme(placement.placement_status)" variant="subtle">{{ __(placement.placement_status) }}</Badge>
		</div>
		<div class="text-xs text-ink-gray-5">
			<span v-if="placement.supervisor_name">{{ __('Supervisor: {0}').format(placement.supervisor_name) }} &middot; </span>
			<span>{{ __('{0} / {1} hours').format(placement.hours_logged || 0, placement.hours_allocated || 0) }}</span>
		</div>

		<!-- Hours logging -->
		<div class="mt-4 border-t border-outline-gray-1 pt-3">
			<div class="mb-2 text-sm font-medium text-ink-gray-7">{{ __('Log hours') }}</div>
			<p class="mb-2 text-xs text-ink-gray-5">{{ trackingHint }}</p>
			<div class="flex flex-wrap items-end gap-2">
				<FormControl type="date" :label="__('Date')" v-model="hoursForm.log_date" />
				<FormControl type="number" :label="__('Hours')" v-model="hoursForm.hours" class="w-24" />
				<FormControl type="text" :label="__('What did you do?')" v-model="hoursForm.description" class="flex-1" />
				<Button variant="solid" :loading="logRes.loading" @click="onLog">{{ __('Add') }}</Button>
			</div>
			<ul v-if="hours.data?.length" class="mt-3 divide-y divide-outline-gray-1 text-sm">
				<li v-for="h in hours.data" :key="h.name" class="flex items-center justify-between py-1.5">
					<span class="text-ink-gray-7">{{ h.log_date }} &middot; {{ h.hours }}h <span class="text-ink-gray-5">{{ h.description }}</span></span>
					<span class="flex items-center gap-2">
						<Badge :theme="h.supervisor_verified ? 'green' : 'gray'" variant="subtle">
							{{ h.supervisor_verified ? __('Verified') : __('Pending') }}
						</Badge>
						<button v-if="!h.supervisor_verified" class="text-xs text-ink-red-5 hover:underline" @click="removeHours(h)">{{ __('Remove') }}</button>
					</span>
				</li>
			</ul>
		</div>

		<!-- Feedback (when the placement is finished) -->
		<div v-if="canGiveFeedback" class="mt-4 border-t border-outline-gray-1 pt-3">
			<div class="mb-2 text-sm font-medium text-ink-gray-7">{{ __('Your feedback') }} <span class="text-ink-gray-5">({{ __('confidential') }})</span></div>
			<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<FormControl type="select" :label="__('Overall rating')" v-model="fbForm.overall_rating" :options="ratingOptions" />
				<FormControl type="select" :label="__('Supervision quality')" v-model="fbForm.supervision_quality" :options="opt(['Excellent','Good','Adequate','Poor'])" />
				<FormControl type="select" :label="__('Spiritual formation value')" v-model="fbForm.spiritual_formation_value" :options="opt(['High','Moderate','Low'])" />
				<FormControl type="select" :label="__('Workload')" v-model="fbForm.workload_appropriateness" :options="opt(['Too Light','Appropriate','Too Heavy'])" />
				<label class="flex items-center gap-2 text-sm text-ink-gray-7 sm:col-span-2">
					<input type="checkbox" v-model="fbForm.would_recommend" :true-value="1" :false-value="0" class="rounded border-outline-gray-3" />{{ __('I would recommend this placement') }}
				</label>
				<FormControl type="textarea" :label="__('Highlights')" v-model="fbForm.highlights" class="sm:col-span-2" />
				<FormControl type="textarea" :label="__('Concerns')" v-model="fbForm.concerns" class="sm:col-span-2" />
				<FormControl type="textarea" :label="__('Suggestions for the seminary')" v-model="fbForm.suggestions_for_seminary" class="sm:col-span-2" />
				<div class="sm:col-span-2">
					<Button variant="solid" :loading="fbRes.loading" @click="onFeedback">{{ fbName ? __('Update feedback') : __('Submit feedback') }}</Button>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { reactive, ref, computed } from 'vue'
import { createResource, Badge, Button, FormControl, toast } from 'frappe-ui'

const props = defineProps({
	placement: { type: Object, required: true },
	hoursTracking: { type: String, default: '' },
})

const ratingOptions = ['', '1', '2', '3', '4', '5'].map((v) => ({ label: v || '—', value: v }))
function opt(vals) { return ['', ...vals].map((v) => ({ label: v ? __(v) : '—', value: v })) }

const trackingHint = computed(() => {
	if (props.hoursTracking === 'Portal Daily Log with Supervisor Confirmation') return __('Hours count once your site supervisor verifies them.')
	if (props.hoursTracking === 'Submittable Log') return __('Hours count once your hour-log requirement is signed complete.')
	return __('Hours count as soon as you log them.')
})

const canGiveFeedback = computed(() => ['Completed', 'Terminated'].includes(props.placement.placement_status))

// Hours
const today = () => new Date().toISOString().slice(0, 10)
const hoursForm = reactive({ log_date: today(), hours: null, description: '' })
const hours = createResource({
	url: 'seminary.partner.internship_api.list_hours',
	makeParams: () => ({ placement: props.placement.name }),
	auto: true,
})
const logRes = createResource({ url: 'seminary.partner.internship_api.log_hours' })
function onLog() {
	if (!hoursForm.log_date || !hoursForm.hours) { toast.error(__('Date and hours are required.')); return }
	logRes.submit({ placement: props.placement.name, log_date: hoursForm.log_date, hours: hoursForm.hours, description: hoursForm.description }, {
		onSuccess: () => { hoursForm.hours = null; hoursForm.description = ''; toast.success(__('Hours logged.')); hours.reload() },
		onError: (e) => toast.error(e.messages?.[0] || __('Could not log hours.')),
	})
}
const delRes = createResource({ url: 'seminary.partner.internship_api.delete_hours' })
function removeHours(h) {
	delRes.submit({ name: h.name }, { onSuccess: () => hours.reload(), onError: (e) => toast.error(e.messages?.[0] || __('Could not remove.')) })
}

// Feedback
const fbForm = reactive({ overall_rating: '', supervision_quality: '', spiritual_formation_value: '', workload_appropriateness: '', would_recommend: 0, highlights: '', concerns: '', suggestions_for_seminary: '' })
const fbName = ref(null)
createResource({
	url: 'seminary.partner.internship_api.get_feedback',
	makeParams: () => ({ placement: props.placement.name }),
	auto: true,
	onSuccess(data) {
		if (data?.name) {
			fbName.value = data.name
			for (const k of Object.keys(fbForm)) if (data[k] !== undefined && data[k] !== null) fbForm[k] = data[k]
		}
	},
})
const fbRes = createResource({ url: 'seminary.partner.internship_api.submit_feedback' })
function onFeedback() {
	fbRes.submit({ placement: props.placement.name, values: { ...fbForm }, name: fbName.value || undefined }, {
		onSuccess: (data) => { fbName.value = data.name; toast.success(__('Feedback saved.')) },
		onError: (e) => toast.error(e.messages?.[0] || __('Could not save feedback.')),
	})
}

function statusTheme(s) {
	if (s === 'Active' || s === 'Completed') return 'green'
	if (s === 'Terminated') return 'red'
	return 'gray'
}
</script>
