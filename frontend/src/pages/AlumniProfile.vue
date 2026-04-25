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
			:disabled="!dirty || save.loading"
			@click="onSave"
		>
			{{ save.loading ? __('Saving...') : __('Save') }}
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
			<Field :label="__('City')">
				<input v-model="form.city" type="text" class="field-input" />
			</Field>
			<Field :label="__('Country')">
				<input v-model="form.country" type="text" class="field-input" />
			</Field>
		</div>

		<Field :label="__('Bio')">
			<textarea v-model="form.bio" rows="5" class="field-input" />
		</Field>

		<label class="flex items-center gap-2 text-sm text-ink-gray-7">
			<input v-model="form.show_in_directory" type="checkbox" />
			{{ __('Show me in the alumni directory') }}
		</label>
	</form>
</template>

<script setup>
import { reactive, computed, watch, h } from 'vue'
import { createResource } from 'frappe-ui'
import { UserX } from 'lucide-vue-next'

const EDITABLE = [
	'full_name',
	'current_role',
	'current_organization',
	'linkedin_url',
	'city',
	'country',
	'bio',
	'show_in_directory',
]

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

const dirty = computed(() =>
	EDITABLE.some((key) => (form[key] ?? '') !== (snapshot[key] ?? ''))
)

const save = createResource({
	url: 'seminary.alumni.api.update_profile',
	onSuccess(data) {
		const next = {}
		for (const key of EDITABLE) next[key] = data[key] ?? ''
		Object.assign(form, next)
		snapshot = { ...next }
	},
})

function onSave() {
	if (!dirty.value) return
	const values = {}
	for (const key of EDITABLE) values[key] = form[key]
	save.submit({ values })
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
