<template>
	<header class="sticky top-0 z-10 flex items-center justify-between border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5">
		<h2 class="text-xl font-bold text-ink-gray-8">{{ __('Our Profile') }}</h2>
		<Button variant="solid" :loading="save.loading" @click="onSave">{{ __('Save changes') }}</Button>
	</header>

	<div v-if="org.loading" class="p-5 text-ink-gray-5">{{ __('Loading...') }}</div>
	<div v-else-if="org.error" class="p-5 text-ink-red-4">{{ org.error.messages?.[0] || __('Not authorized.') }}</div>

	<div v-else-if="org.data" class="mx-auto w-full max-w-3xl px-4 py-6 sm:px-6">
		<div class="text-lg font-semibold text-ink-gray-9">{{ org.data.organization_name }}</div>

		<!-- Logo -->
		<div class="mt-4">
			<div class="mb-1 text-sm text-ink-gray-7">{{ __('Logo') }}</div>
			<div class="flex items-center gap-3">
				<img v-if="form.image" :src="form.image" class="h-14 w-auto rounded border border-outline-gray-2" />
				<FileUploader :upload-args="{ folder: 'Home/Attachments' }" @success="(f) => (form.image = f.file_url)">
					<template #default="{ uploading, openFileSelector }">
						<Button :loading="uploading" @click="openFileSelector">
							{{ form.image ? __('Replace logo') : __('Upload logo') }}
						</Button>
					</template>
				</FileUploader>
			</div>
		</div>

		<div class="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
			<FormControl type="text" :label="__('Website')" v-model="form.website" />
			<FormControl type="email" :label="__('Primary email')" v-model="form.primary_email" />
			<FormControl type="text" :label="__('Primary phone')" v-model="form.primary_phone" />
			<!-- Label, placeholder and mask come from the country's rule, so
			     this markup names no country. -->
			<div>
				<FormControl type="text" :label="__(taxId.label.value)" v-model="form.tax_id"
					:placeholder="taxId.placeholder.value" @input="onTaxIdInput"
					@blur="taxId.validate(form.tax_id)" />
				<p v-if="taxId.error.value" class="mt-1 text-xs text-ink-red-3">{{ taxId.error.value }}</p>
				<p v-else-if="taxId.note.value" class="mt-1 text-xs text-ink-gray-5">{{ __(taxId.note.value) }}</p>
			</div>
		</div>

		<div class="mt-4">
			<div class="mb-1 text-sm text-ink-gray-7">{{ __('About us') }}</div>
			<TextEditor :content="form.about_us" @change="(v) => (form.about_us = v)" :editable="true" :fixedMenu="true" :bubbleMenu="false"
				editorClass="prose-sm max-w-none rounded-b-md border-x border-b border-outline-gray-2 bg-surface-white px-2 py-2 min-h-[8rem] max-h-[20rem] overflow-y-auto text-ink-gray-8" />
		</div>
		<div class="mt-4">
			<div class="mb-1 text-sm text-ink-gray-7">{{ __('Doctrinal statement') }}</div>
			<TextEditor :content="form.doctrinal_statement" @change="(v) => (form.doctrinal_statement = v)" :editable="true" :fixedMenu="true" :bubbleMenu="false"
				editorClass="prose-sm max-w-none rounded-b-md border-x border-b border-outline-gray-2 bg-surface-white px-2 py-2 min-h-[8rem] max-h-[20rem] overflow-y-auto text-ink-gray-8" />
		</div>

		<div class="mt-6">
			<div class="mb-2 text-base font-semibold text-ink-gray-8">{{ __('Address') }}</div>
			<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<FormControl type="text" :label="__('Address line 1')" v-model="form.address_line_1" />
				<FormControl type="text" :label="__('Address line 2')" v-model="form.address_line_2" />
				<FormControl type="text" :label="__('City')" v-model="form.city" />
				<FormControl type="text" :label="__('State / Province')" v-model="form.state" />
				<FormControl type="text" :label="__('Postal code')" v-model="form.pincode" />
			</div>
		</div>

		<!-- Locations -->
		<div class="mt-8 border-t border-outline-gray-1 pt-6">
			<div class="mb-2 flex items-center justify-between">
				<div class="text-base font-semibold text-ink-gray-8">{{ __('Locations') }}</div>
				<Button @click="openLocation()">{{ __('Add location') }}</Button>
			</div>
			<ul v-if="org.data.locations?.length" class="divide-y divide-outline-gray-1">
				<li v-for="loc in org.data.locations" :key="loc.name" class="flex items-center justify-between py-2">
					<div>
						<div class="font-medium text-ink-gray-8">{{ loc.location_name }}</div>
						<div class="text-xs text-ink-gray-5">
							<span v-if="loc.city">{{ loc.city }}</span>
							<span v-if="loc.ministry_setting"> &middot; {{ __(loc.ministry_setting) }}</span>
						</div>
					</div>
					<Button variant="ghost" @click="openLocation(loc)">{{ __('Edit') }}</Button>
				</li>
			</ul>
			<div v-else class="text-sm text-ink-gray-5">{{ __('No locations yet.') }}</div>
		</div>
	</div>

	<!-- Location dialog -->
	<Dialog v-model="showLocation" :options="{ title: locForm.name ? __('Edit location') : __('Add location') }">
		<template #body-content>
			<div class="flex flex-col gap-3">
				<FormControl type="text" :label="__('Location name')" v-model="locForm.location_name" />
				<FormControl type="text" :label="__('Address line 1')" v-model="locForm.address_line_1" />
				<FormControl type="text" :label="__('City')" v-model="locForm.city" />
				<FormControl type="text" :label="__('State / Province')" v-model="locForm.state" />
				<FormControl type="select" :label="__('Ministry setting')" v-model="locForm.ministry_setting" :options="ministryOptions" />
				<FormControl type="select" :label="__('Congregation size')" v-model="locForm.congregation_size" :options="sizeOptions" />
				<Button variant="solid" :loading="saveLocation.loading" @click="onSaveLocation">{{ __('Save location') }}</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { createResource, Button, FormControl, TextEditor, FileUploader, Dialog, toast } from 'frappe-ui'
import { usePartnerOrg } from '@/composables/usePartnerOrg'
import { useTaxId } from '@/composables/useTaxId'

const { activeOrg } = usePartnerOrg()

const EDITABLE = ['about_us', 'doctrinal_statement', 'website', 'tax_id', 'image', 'primary_email', 'primary_phone', 'address_line_1', 'address_line_2', 'pincode', 'city', 'state']
const form = reactive(Object.fromEntries(EDITABLE.map((k) => [k, ''])))

const ministryOptions = [{ label: '—', value: '' }, ...['Urban', 'Suburban', 'Rural', 'Campus'].map((v) => ({ label: __(v), value: v }))]
const sizeOptions = [{ label: '—', value: '' }, ...['Under 50', '50-150', '150-500', 'Over 500'].map((v) => ({ label: v, value: v }))]

const org = createResource({
	url: 'seminary.partner.portal.get_my_org',
	makeParams: () => ({ org: activeOrg.value }),
	auto: true,
	onSuccess(data) {
		for (const k of EDITABLE) form[k] = data?.[k] || ''
	},
})
watch(activeOrg, () => org.reload())

// Which registration number is wanted follows the organization's country
// (ADR 071). The country is not editable from this page, so the rule is read
// from the loaded record rather than the form.
const taxCountry = computed(() => org.data?.country || '')
const taxId = useTaxId(taxCountry, { subject: 'organization' })

const onTaxIdInput = () => {
	form.tax_id = taxId.format(form.tax_id)
	taxId.error.value = ''
}

const save = createResource({
	url: 'seminary.partner.portal.update_org',
	makeParams: () => ({ values: { ...form }, org: activeOrg.value }),
	onSuccess() {
		toast.success(__('Profile saved.'))
		org.reload()
	},
	onError(err) {
		toast.error(err.messages?.[0] || __('Could not save.'))
	},
})
async function onSave() {
	// Don't post a registration number the server is only going to refuse.
	if (await taxId.validate(form.tax_id)) return
	if (!save.loading) save.submit()
}

// Locations
const showLocation = ref(false)
const locForm = reactive({ name: null, location_name: '', address_line_1: '', city: '', state: '', ministry_setting: '', congregation_size: '' })
function openLocation(loc = null) {
	Object.assign(locForm, {
		name: loc?.name || null,
		location_name: loc?.location_name || '',
		address_line_1: loc?.address_line_1 || '',
		city: loc?.city || '',
		state: loc?.state || '',
		ministry_setting: loc?.ministry_setting || '',
		congregation_size: loc?.congregation_size || '',
	})
	showLocation.value = true
}
const saveLocation = createResource({
	url: 'seminary.partner.portal.save_location',
	makeParams: () => ({
		name: locForm.name || undefined,
		org: activeOrg.value,
		values: {
			location_name: locForm.location_name,
			address_line_1: locForm.address_line_1,
			city: locForm.city,
			state: locForm.state,
			ministry_setting: locForm.ministry_setting,
			congregation_size: locForm.congregation_size,
		},
	}),
	onSuccess() {
		showLocation.value = false
		toast.success(__('Location saved.'))
		org.reload()
	},
	onError(err) {
		toast.error(err.messages?.[0] || __('Could not save the location.'))
	},
})
function onSaveLocation() {
	if (!locForm.location_name) {
		toast.error(__('Location name is required.'))
		return
	}
	if (!saveLocation.loading) saveLocation.submit()
}
</script>
