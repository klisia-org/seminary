<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<h2 class="text-xl font-bold text-ink-gray-8">
			{{ __('Communication Preferences') }}
		</h2>
		<Button variant="solid" :label="__('Save')" :loading="saving.loading" @click="save" />
	</header>

	<div v-if="prefs.loading && !prefs.data" class="p-5 text-ink-gray-5">
		{{ __('Loading preferences...') }}
	</div>

	<div v-else-if="prefs.data" class="mx-auto w-full max-w-3xl space-y-5 p-5">
		<section class="rounded-lg border border-outline-gray-1 bg-surface-white p-5 shadow-sm">
			<h3 class="mb-1 text-base font-semibold text-ink-gray-8">
				{{ __('Language') }}
			</h3>
			<p class="mb-3 text-sm text-ink-gray-5">
				{{ __('Messages from the seminary are sent in this language when a translation exists.') }}
			</p>
			<select
				v-model="language"
				class="w-full max-w-xs rounded-md border-outline-gray-2 bg-surface-white text-sm text-ink-gray-7 focus:ring-0"
			>
				<option value="">{{ __('Site default') }}</option>
				<option v-for="l in prefs.data.languages" :key="l.name" :value="l.name">
					{{ l.language_name }}
				</option>
			</select>
		</section>

		<section class="rounded-lg border border-outline-gray-1 bg-surface-white p-5 shadow-sm">
			<h3 class="mb-1 text-base font-semibold text-ink-gray-8">
				{{ __('What we may send you, and where') }}
			</h3>
			<p class="mb-4 text-sm text-ink-gray-5">
				{{ __('Promotional messages are only sent if you opt in. Operational messages (enrollment, payments) pause only where you explicitly opt out. Emergency notices are always delivered.') }}
			</p>
			<div class="space-y-3">
				<div
					v-for="cat in prefs.data.categories"
					:key="cat"
					class="rounded-md border border-outline-gray-1 p-3"
				>
					<p class="mb-2 text-sm font-medium text-ink-gray-8">{{ __(cat) }}</p>
					<div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
						<label
							v-for="ch in prefs.data.channels"
							:key="ch"
							class="flex flex-col gap-1"
						>
							<span class="text-xs text-ink-gray-5">{{ __(ch) }}</span>
							<select
								v-model="consents[`${ch}::${cat}`]"
								class="w-full rounded-md border-outline-gray-2 bg-surface-white text-xs text-ink-gray-7 focus:ring-0"
								:disabled="cat === 'Emergency'"
							>
								<option value="Unset">{{ __('Default') }}</option>
								<option value="Opted In">{{ __('Opted In') }}</option>
								<option value="Opted Out">{{ __('Opted Out') }}</option>
							</select>
						</label>
					</div>
				</div>
			</div>
		</section>

		<section class="rounded-lg border border-outline-gray-1 bg-surface-white p-5 shadow-sm">
			<h3 class="mb-1 text-base font-semibold text-ink-gray-8">
				{{ __('Mailing address') }}
			</h3>
			<p class="mb-3 text-sm text-ink-gray-5">
				{{ __('Where the seminary sends printed letters.') }}
			</p>
			<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<input
					v-model="mailing.address_line_1"
					:placeholder="__('Address line 1')"
					class="rounded-md border-outline-gray-2 bg-surface-white text-sm text-ink-gray-7 focus:ring-0 sm:col-span-2"
				/>
				<input
					v-model="mailing.address_line_2"
					:placeholder="__('Address line 2')"
					class="rounded-md border-outline-gray-2 bg-surface-white text-sm text-ink-gray-7 focus:ring-0 sm:col-span-2"
				/>
				<input
					v-model="mailing.city"
					:placeholder="__('City')"
					class="rounded-md border-outline-gray-2 bg-surface-white text-sm text-ink-gray-7 focus:ring-0"
				/>
				<input
					v-model="mailing.state"
					:placeholder="__('State / Province')"
					class="rounded-md border-outline-gray-2 bg-surface-white text-sm text-ink-gray-7 focus:ring-0"
				/>
				<input
					v-model="mailing.pincode"
					:placeholder="__('Postal code')"
					class="rounded-md border-outline-gray-2 bg-surface-white text-sm text-ink-gray-7 focus:ring-0"
				/>
				<select
					v-model="mailing.country"
					class="rounded-md border-outline-gray-2 bg-surface-white text-sm text-ink-gray-7 focus:ring-0"
				>
					<option value="">{{ __('Country') }}</option>
					<option v-for="c in prefs.data.countries" :key="c" :value="c">
						{{ c }}
					</option>
				</select>
			</div>
		</section>

		<section class="rounded-lg border border-outline-gray-1 bg-surface-white p-5 shadow-sm">
			<h3 class="mb-1 text-base font-semibold text-ink-gray-8">
				{{ __('Your contact addresses') }}
			</h3>
			<p class="mb-3 text-sm text-ink-gray-5">
				{{ __('You can add your own addresses here. The ones the school keeps on file stay as they are — ask the registrar to change those.') }}
			</p>

			<div
				v-for="addr in prefs.data.addresses"
				:key="addr.name"
				class="flex flex-wrap items-center gap-2 border-b border-outline-gray-1 py-2.5 text-sm last:border-b-0"
			>
				<span class="w-24 shrink-0 text-ink-gray-5">{{ __(addr.channel) }}</span>
				<span class="min-w-0 flex-1 truncate text-ink-gray-8">{{ addr.value }}</span>

				<span
					v-if="addr.is_primary"
					class="rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-6"
				>
					{{ __('Primary') }}
				</span>
				<span
					v-if="addr.category"
					class="rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-6"
				>
					{{ __(addr.category) }}
				</span>
				<span
					v-if="addr.status !== 'Active'"
					class="rounded bg-surface-red-1 px-1.5 py-0.5 text-xs text-ink-red-3"
				>
					{{ __(addr.status) }}
				</span>
				<span
					v-else-if="addr.verified"
					class="rounded bg-surface-green-1 px-1.5 py-0.5 text-xs text-ink-green-3"
				>
					{{ __('Confirmed') }}
				</span>
				<span
					v-else
					class="rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-6"
				>
					{{ __('Not confirmed') }}
				</span>

				<!-- Sharing is offered on every row, including the one the
				     registrar created: it changes who sees the address, not the
				     address itself, and most people have no second email to
				     offer. Only a confirmed address can be shared. -->
				<label
					v-if="prefs.data.directory_sharing_available"
					class="flex items-center gap-1.5 text-xs"
					:class="addr.verified ? 'text-ink-gray-7' : 'text-ink-gray-4'"
				>
					<input
						type="checkbox"
						:checked="!!addr.share_in_directory"
						:disabled="!addr.verified || sharing.loading"
						class="rounded border-outline-gray-3"
						@change="toggleSharing(addr, $event.target.checked)"
					/>
					{{ __('Show in alumni directory') }}
				</label>

				<Button
					v-if="!addr.verified && addr.channel === 'Email'"
					variant="subtle"
					size="sm"
					:loading="verifying.loading"
					:label="__('Send confirmation')"
					@click="requestVerification(addr)"
				/>
				<Button
					v-if="addr.editable"
					variant="subtle"
					size="sm"
					:label="__('Remove')"
					@click="removeAddress(addr)"
				/>
			</div>

			<div v-if="!prefs.data.addresses.length" class="text-sm text-ink-gray-5">
				{{ __('No addresses on file.') }}
			</div>

			<div
				v-if="prefs.data.self_managed_channels?.length"
				class="mt-4 flex flex-wrap items-end gap-2 rounded-md border border-outline-gray-1 p-3"
			>
				<label class="flex flex-col gap-1">
					<span class="text-xs text-ink-gray-5">{{ __('Channel') }}</span>
					<select
						v-model="draft.channel"
						class="rounded-md border-outline-gray-2 bg-surface-white text-sm text-ink-gray-7 focus:ring-0"
					>
						<option v-for="ch in prefs.data.self_managed_channels" :key="ch" :value="ch">
							{{ __(ch) }}
						</option>
					</select>
				</label>
				<label class="flex min-w-48 flex-1 flex-col gap-1">
					<span class="text-xs text-ink-gray-5">{{ __('Address') }}</span>
					<input
						v-model="draft.value"
						class="rounded-md border-outline-gray-2 bg-surface-white text-sm text-ink-gray-7 focus:ring-0"
						:placeholder="draft.channel === 'Email' ? 'you@example.org' : '+15551234567'"
						@keyup.enter="addAddress"
					/>
				</label>
				<Button
					variant="solid"
					:loading="adding.loading"
					:label="__('Add')"
					@click="addAddress"
				/>
				<p class="w-full text-xs text-ink-gray-5">
					{{ __('We send a short message to confirm a new address reaches you. Phone numbers need the country code.') }}
				</p>
			</div>
			<div v-if="telegram.data?.url && !telegram.data.connected" class="mt-4">
				<a
					:href="telegram.data.url"
					target="_blank"
					rel="noopener"
					class="inline-flex items-center gap-2 rounded-md bg-surface-blue-2 px-3 py-1.5 text-sm font-medium text-ink-blue-3"
				>
					<Send class="size-4" />
					{{ __('Connect Telegram') }} (@{{ telegram.data.bot }})
				</a>
				<p class="mt-1.5 text-xs text-ink-gray-5">
					{{ __('Opens the seminary bot in Telegram; press Start to link this account.') }}
				</p>
			</div>
			<div
				v-else-if="telegram.data?.connected"
				class="mt-3 text-sm text-ink-green-3"
			>
				{{ __('Telegram connected.') }}
			</div>
		</section>
	</div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { Button, createResource } from 'frappe-ui'
import { Send } from 'lucide-vue-next'
import { createToast } from '@/utils'

const telegram = createResource({
	url: 'seminary.seminary.telegram_adapter.get_my_telegram_link',
	auto: true,
})

const language = ref('')
const consents = reactive({})
const mailing = reactive({
	address_line_1: '',
	address_line_2: '',
	city: '',
	state: '',
	pincode: '',
	country: '',
})

const prefs = createResource({
	url: 'seminary.seminary.comms.get_my_communication_preferences',
	auto: true,
	onSuccess(data) {
		language.value = data.language || ''
		for (const cat of data.categories) {
			for (const ch of data.channels) {
				consents[`${ch}::${cat}`] = data.consents[`${ch}::${cat}`] || 'Unset'
			}
		}
		Object.assign(mailing, {
			address_line_1: '',
			address_line_2: '',
			city: '',
			state: '',
			pincode: '',
			country: '',
			...(data.mailing_address || {}),
		})
	},
})

const saving = createResource({
	url: 'seminary.seminary.comms.update_my_communication_preferences',
	onSuccess() {
		createToast({ title: __('Preferences saved'), icon: 'check', iconClasses: 'text-ink-green-3' })
	},
})

function save() {
	const rows = Object.entries(consents).map(([key, status]) => {
		const [channel, category] = key.split('::')
		return { channel, category, status }
	})
	saving.submit({
		language: language.value || null,
		consents: rows,
		mailing_address: { ...mailing },
	})
}

// ----- channel addresses -----
// Every one of these returns the whole preferences payload, so the page
// re-renders from one source instead of patching rows by hand.

const draft = reactive({ channel: 'Email', value: '' })

function applyPrefs(data) {
	prefs.data = data
}

function addressError(e) {
	createToast({
		title: e.messages?.[0] || __('Could not save that address.'),
		icon: 'x',
		iconClasses: 'text-ink-red-3',
	})
}

const adding = createResource({
	url: 'seminary.seminary.comms.add_my_address',
	onSuccess: applyPrefs,
	onError: addressError,
})
const removing = createResource({
	url: 'seminary.seminary.comms.delete_my_address',
	onSuccess: applyPrefs,
	onError: addressError,
})
const sharing = createResource({
	url: 'seminary.seminary.comms.set_address_sharing',
	onSuccess: applyPrefs,
	onError: addressError,
})
const verifying = createResource({
	url: 'seminary.seminary.address_verification.request_verification',
	onSuccess(data) {
		createToast({
			title: data.sent
				? __('Confirmation sent. Open the link in that message.')
				: __('A confirmation was already sent today. Check that inbox.'),
			icon: 'check',
			iconClasses: 'text-ink-green-3',
		})
	},
	onError: addressError,
})

function addAddress() {
	if (!draft.value.trim()) return
	adding.submit({ channel: draft.channel, value: draft.value.trim() }).then(() => {
		draft.value = ''
		createToast({
			title:
				draft.channel === 'Email'
					? __('Added. Check that inbox for the confirmation link.')
					: __('Added.'),
			icon: 'check',
			iconClasses: 'text-ink-green-3',
		})
	})
}

function removeAddress(addr) {
	if (!window.confirm(__('Remove {0}?').format(addr.value))) return
	removing.submit({ row: addr.name })
}

function toggleSharing(addr, checked) {
	sharing.submit({ row: addr.name, share_in_directory: checked ? 1 : 0 })
}

function requestVerification(addr) {
	verifying.submit({ row: addr.name })
}
</script>
