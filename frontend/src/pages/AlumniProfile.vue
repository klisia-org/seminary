<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<h2 class="text-xl font-bold text-ink-gray-8">
			{{ __('My Alumni Profile') }}
		</h2>
		<button
			type="button"
			class="rounded-md bg-surface-gray-7 px-3 py-1.5 text-sm font-medium text-ink-white disabled:opacity-50"
			:disabled="!dirty || saving"
			@click="onSave"
		>
			{{ saving ? __('Saving...') : __('Save') }}
		</button>
	</header>

	<div v-if="profile.loading" class="p-5 text-ink-gray-5">
		{{ __('Loading...') }}
	</div>

	<div
		v-else-if="!profile.data"
		class="mt-32 md:mt-52 mx-auto w-3/4 md:w-1/2 space-y-2 p-5 text-center text-ink-gray-5"
	>
		<UserX class="mx-auto size-10 stroke-1 text-ink-gray-4" />
		<div class="text-xl font-medium">{{ __('No alumni profile') }}</div>
	</div>

	<form v-else class="mx-auto w-full max-w-2xl space-y-5 p-5" @submit.prevent="onSave">
		<div class="grid gap-4 sm:grid-cols-2">
			<Field :label="__('Full name')">
				<input v-model="form.full_name" type="text" class="field-input" />
			</Field>
			<Field :label="__('LinkedIn URL')">
				<input v-model="form.linkedin_url" type="url" class="field-input" />
			</Field>
			<Field :label="__('Current role')">
				<input v-model="form.current_role" type="text" class="field-input" />
			</Field>
			<Field :label="__('Current organization')">
				<input v-model="form.current_organization" type="text" class="field-input" />
			</Field>
			<!-- The free text above stays whatever the alumnus wrote; this only
			     adds a link when the seminary already knows the organization,
			     which is what turns it into a badge in the directory. -->
			<Field
				v-if="partnerOrgs.data?.length"
				:label="__('Is that one of our partner organizations?')"
			>
				<select v-model="form.current_partner_organization" class="field-input">
					<option value="">{{ __('Not listed') }}</option>
					<option v-for="org in partnerOrgs.data" :key="org.name" :value="org.name">
						{{ org.organization_name }}
					</option>
				</select>
			</Field>
			<Field :label="__('City')">
				<input v-model="form.city" type="text" class="field-input" />
			</Field>
			<Field :label="__('Country')">
				<input v-model="form.country" type="text" class="field-input" />
			</Field>
		</div>

		<Field :label="__('Bio')">
			<textarea v-model="form.bio" rows="5" class="field-input" />
			<p class="mt-1 text-xs text-ink-gray-5">
				{{ __('Shown to other alumni when they open your profile in the directory. Nobody else sees it.') }}
			</p>
		</Field>

		<section class="space-y-3 rounded-md border border-outline-gray-1 p-4">
			<h3 class="text-sm font-semibold text-ink-gray-8">
				{{ __('What others can see') }}
			</h3>

			<label class="flex items-start gap-2 text-sm text-ink-gray-7">
				<input
					v-model="form.show_in_directory"
					type="checkbox"
					:true-value="1"
					:false-value="0"
					class="mt-0.5"
				/>
				<span>
					{{ __('Show me in the alumni directory') }}
					<span class="block text-xs text-ink-gray-5">
						{{ __('Other alumni can find your name, programs, role, organization and city.') }}
					</span>
				</span>
			</label>

			<label class="flex items-start gap-2 text-sm text-ink-gray-7">
				<input
					v-model="form.open_to_cohort_invites"
					type="checkbox"
					:true-value="1"
					:false-value="0"
					class="mt-0.5"
				/>
				<span>
					{{ __('Let other alumni invite me to a community cohort') }}
					<span class="block text-xs text-ink-gray-5">
						{{ __('Turn this off to stay listed without being asked to join groups. Staff can still add you.') }}
					</span>
				</span>
			</label>

			<p class="text-xs text-ink-gray-5">
				{{ __('Your contact details are separate: you choose them one at a time in Preferences, and nothing is shown until you do.') }}
				<router-link to="/preferences" class="text-ink-blue-link hover:text-ink-blue-3">
					{{ __('Open Preferences') }}
				</router-link>
			</p>

			<Button variant="subtle" size="sm" @click="showExplainer = true">
				{{ __('How is this different from my message preferences?') }}
			</Button>
		</section>

		<div class="border-t border-outline-gray-1 pt-5">
			<CareerProfileFields ref="career" />
		</div>
	</form>

	<Dialog v-model="showExplainer" :options="{ title: __('Directory and messages') }">
		<template #body-content>
			<div class="space-y-3 text-sm text-ink-gray-7">
				<p>
					{{ __('They are two different things, and changing one never changes the other.') }}
				</p>
				<p>
					<b>{{ __('The directory') }}</b>
					{{ __('is about what other alumni can see: whether you are listed, and which of your contact addresses you chose to show. It does not affect anything the seminary sends you.') }}
				</p>
				<p>
					<b>{{ __('Message preferences') }}</b>
					{{ __('are about what the seminary sends you, and on which channel. Opting out there never removes you from the directory.') }}
				</p>
				<p class="rounded-md bg-surface-amber-1 p-3 text-ink-amber-3">
					{{ __('One thing does connect them: invitations to community cohorts are sent as “Community” messages. If you opt out of Community on every channel, you will stay listed but will not hear about invitations.') }}
				</p>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { reactive, ref, computed, h } from 'vue'
import { Button, Dialog, createResource } from 'frappe-ui'
import { UserX } from 'lucide-vue-next'
import CareerProfileFields from '@/components/CareerProfileFields.vue'

// Must stay in step with PROFILE_EDITABLE_FIELDS in seminary/alumni/api.py —
// anything missing here is silently not editable, anything extra is silently
// dropped on save.
const EDITABLE = [
	'full_name',
	'current_role',
	'current_organization',
	'linkedin_url',
	'city',
	'country',
	'bio',
	'show_in_directory',
	'open_to_cohort_invites',
	'current_partner_organization',
]

const showExplainer = ref(false)

// Comes back empty (and the picker stays hidden) when the seminary has the
// partner directory switched off — the endpoint refuses rather than returning
// rows, so a failure here is a configuration answer, not an error to show.
const partnerOrgs = createResource({
	url: 'seminary.partner.api.get_partner_directory',
	auto: true,
	onError() {},
})

const form = reactive({})
let snapshot = {}

const profile = createResource({
	url: 'seminary.alumni.api.get_my_profile',
	auto: true,
	onSuccess(data) {
		if (!data) return
		const next = {}
		for (const key of EDITABLE) next[key] = data[key] ?? ''
		Object.assign(form, next)
		snapshot = { ...next }
	},
})

const career = ref(null)
const saving = ref(false)

const profileDirty = computed(() =>
	EDITABLE.some((key) => (form[key] ?? '') !== (snapshot[key] ?? ''))
)
const dirty = computed(() => profileDirty.value || !!career.value?.dirty)

const save = createResource({
	url: 'seminary.alumni.api.update_profile',
	onSuccess(data) {
		const next = {}
		for (const key of EDITABLE) next[key] = data[key] ?? ''
		Object.assign(form, next)
		snapshot = { ...next }
	},
})

// One Save button drives both records: the Alumni Profile fields and the
// shared career fields (which live on the Person spine).
async function onSave() {
	if (!dirty.value || saving.value) return
	saving.value = true
	try {
		const tasks = []
		if (profileDirty.value) {
			const values = {}
			for (const key of EDITABLE) values[key] = form[key]
			tasks.push(save.submit({ values }))
		}
		if (career.value?.dirty) tasks.push(career.value.save())
		await Promise.all(tasks)
	} finally {
		saving.value = false
	}
}

const Field = (props, { slots }) =>
	h('label', { class: 'block' }, [
		h('span', { class: 'mb-1 block text-xs font-medium text-ink-gray-6' }, props.label),
		slots.default?.(),
	])
Field.props = ['label']
</script>

<style scoped>
.field-input {
	@apply block w-full rounded-md border border-outline-gray-2 bg-surface-white px-3 py-1.5 text-sm text-ink-gray-8 focus:border-outline-gray-4 focus:outline-none;
}
</style>
