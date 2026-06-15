<template>
	<header class="sticky top-0 z-10 flex items-center gap-2 border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5">
		<router-link :to="{ name: 'PartnerJobPosting', params: { name } }" class="flex items-center gap-1 text-sm text-ink-gray-6 hover:text-ink-gray-8">
			<ArrowLeft class="size-4" />{{ __('Applicants') }}
		</router-link>
	</header>

	<div v-if="app.loading" class="p-5 text-ink-gray-5">{{ __('Loading...') }}</div>
	<div v-else-if="app.error" class="p-5 text-ink-red-4">{{ app.error.messages?.[0] || __('Not authorized.') }}</div>

	<div v-else-if="app.data" class="mx-auto w-full max-w-2xl px-4 py-6 text-ink-gray-8 sm:px-6">
		<!-- Header -->
		<div class="flex flex-wrap items-start justify-between gap-3">
			<div>
				<h1 class="text-2xl font-bold text-ink-gray-9">{{ app.data.full_name }}</h1>
				<div class="mt-1 text-sm text-ink-gray-6">{{ app.data.job_title }}</div>
				<div class="mt-1 text-sm text-ink-gray-6">
					<a :href="`mailto:${app.data.email}`" class="text-ink-blue-6 hover:underline">{{ app.data.email }}</a>
					<span v-if="app.data.mobile"> &middot; {{ app.data.mobile }}</span>
				</div>
			</div>
			<div>
				<div class="mb-1 text-xs font-medium uppercase tracking-wide text-ink-gray-5">{{ __('Status') }}</div>
				<select :value="app.data.status" @change="onStatus($event.target.value)"
					class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm text-ink-gray-8 focus:outline-none">
					<option v-for="s in app.data.statuses" :key="s" :value="s">{{ __(s) }}</option>
				</select>
			</div>
		</div>

		<div class="mt-3 flex items-center gap-3 text-sm text-ink-gray-5">
			<a v-if="app.data.resume" :href="app.data.resume" target="_blank" rel="noopener" class="flex items-center gap-1 text-ink-blue-6 hover:underline">
				<FileText class="size-4" />{{ __('Résumé') }}
			</a>
			<span>{{ __('Avg rating') }}: {{ stars(app.data.average_rating) }}</span>
			<span>{{ __('Submitted') }} {{ formatDate(app.data.submission_date) }}</span>
		</div>

		<!-- Cover letter -->
		<section v-if="app.data.cover_letter" class="mt-6">
			<h2 class="mb-2 text-base font-semibold text-ink-gray-8">{{ __('Cover Letter') }}</h2>
			<div class="prose-sm max-w-none text-ink-gray-7" v-html="app.data.cover_letter" />
		</section>

		<!-- Doctrine -->
		<section v-if="app.data.doctrinal_alignment" class="mt-6">
			<h2 class="mb-2 text-base font-semibold text-ink-gray-8">{{ __('Doctrinal alignment') }}</h2>
			<div class="text-sm font-medium text-ink-gray-8">{{ __(app.data.doctrinal_alignment) }}</div>
			<div v-if="app.data.alignment_explanation" class="mt-1 whitespace-pre-line text-sm text-ink-gray-6">{{ app.data.alignment_explanation }}</div>
		</section>

		<!-- Reviews -->
		<section class="mt-8 border-t border-outline-gray-1 pt-6">
			<h2 class="mb-2 text-base font-semibold text-ink-gray-8">{{ __('Reviews') }}</h2>
			<ul v-if="app.data.reviews?.length" class="mb-4 divide-y divide-outline-gray-1">
				<li v-for="r in app.data.reviews" :key="r.row" class="py-2">
					<div class="flex items-center justify-between">
						<span class="text-sm font-medium text-ink-gray-8">{{ r.reviewer_name || r.reviewer }}</span>
						<span class="text-sm text-ink-gray-6">{{ stars(r.rating) }} ★</span>
					</div>
					<div v-if="r.notes" class="text-sm text-ink-gray-6">{{ r.notes }}</div>
				</li>
			</ul>
			<div class="rounded-lg border border-outline-gray-2 bg-surface-gray-1 p-3">
				<div class="mb-1 text-sm font-medium text-ink-gray-7">{{ app.data.my_review ? __('Your review') : __('Add your review') }}</div>
				<div class="flex items-center gap-1">
					<button v-for="n in 5" :key="n" type="button" @click="myRating = n / 5">
						<Star class="size-5" :class="myRating * 5 >= n ? 'fill-ink-amber-3 text-ink-amber-3' : 'text-ink-gray-4'" />
					</button>
				</div>
				<FormControl type="textarea" class="mt-2" :label="__('Notes')" v-model="myNotes" :rows="3" />
				<Button class="mt-2" variant="solid" :loading="review.loading" @click="onReview">
					{{ app.data.my_review ? __('Update review') : __('Add review') }}
				</Button>
			</div>
		</section>

		<!-- Contact log -->
		<section class="mt-8 border-t border-outline-gray-1 pt-6">
			<div class="mb-2 flex items-center justify-between">
				<h2 class="text-base font-semibold text-ink-gray-8">{{ __('Contact log') }}</h2>
				<Button @click="openContact()">{{ __('Add entry') }}</Button>
			</div>
			<ul v-if="app.data.contacts?.length" class="divide-y divide-outline-gray-1">
				<li v-for="c in app.data.contacts" :key="c.row" class="flex items-start justify-between gap-2 py-2">
					<div>
						<div class="text-sm font-medium text-ink-gray-8">{{ __(c.contact_type || 'Contact') }}
							<span class="font-normal text-ink-gray-5">· {{ formatDate(c.contacted_on) }}</span>
						</div>
						<div v-if="c.participants" class="text-xs text-ink-gray-5">{{ c.participants }}</div>
						<div v-if="c.notes" class="text-sm text-ink-gray-6">{{ c.notes }}</div>
					</div>
					<Button variant="ghost" @click="openContact(c)">{{ __('Edit') }}</Button>
				</li>
			</ul>
			<div v-else class="text-sm text-ink-gray-5">{{ __('No entries yet.') }}</div>
		</section>
	</div>

	<!-- Contact dialog -->
	<Dialog v-model="showContact" :options="{ title: cForm.row ? __('Edit entry') : __('Add entry') }">
		<template #body-content>
			<div class="flex flex-col gap-3">
				<FormControl type="select" :label="__('Type')" v-model="cForm.contact_type" :options="contactTypeOptions" />
				<FormControl type="text" :label="__('Participants')" v-model="cForm.participants" />
				<FormControl type="textarea" :label="__('Notes')" v-model="cForm.notes" :rows="3" />
				<Button variant="solid" :loading="contact.loading" @click="onContact">{{ __('Save entry') }}</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { createResource, Button, FormControl, Dialog, toast } from 'frappe-ui'
import { ArrowLeft, Star, FileText } from 'lucide-vue-next'

const props = defineProps({ name: { type: String, required: true }, appName: { type: String, required: true } })

const contactTypeOptions = ['Email', 'Phone', 'Video Call', 'In-person', 'Other'].map((v) => ({ label: __(v), value: v }))

const myRating = ref(0)
const myNotes = ref('')

const app = createResource({
	url: 'seminary.partner.portal.get_application',
	makeParams: () => ({ name: props.appName }),
	auto: true,
	onSuccess(data) {
		myRating.value = data?.my_review?.rating || 0
		myNotes.value = data?.my_review?.notes || ''
	},
})

const statusRes = createResource({
	url: 'seminary.partner.portal.set_application_status',
	onSuccess() {
		toast.success(__('Status updated.'))
		app.reload()
	},
	onError(err) {
		toast.error(err.messages?.[0] || __('Could not update status.'))
	},
})
function onStatus(value) {
	statusRes.submit({ name: props.appName, status: value })
}

const review = createResource({
	url: 'seminary.partner.portal.save_review',
	makeParams: () => ({ application: props.appName, rating: myRating.value, notes: myNotes.value }),
	onSuccess() {
		toast.success(__('Review saved.'))
		app.reload()
	},
	onError(err) {
		toast.error(err.messages?.[0] || __('Could not save the review.'))
	},
})
function onReview() {
	if (!myRating.value) {
		toast.error(__('Please pick a rating.'))
		return
	}
	if (!review.loading) review.submit()
}

// Contact log
const showContact = ref(false)
const cForm = reactive({ row: null, contact_type: 'Phone', participants: '', notes: '' })
function openContact(c = null) {
	Object.assign(cForm, { row: c?.row || null, contact_type: c?.contact_type || 'Phone', participants: c?.participants || '', notes: c?.notes || '' })
	showContact.value = true
}
const contact = createResource({
	url: 'seminary.partner.portal.save_contact_log',
	makeParams: () => ({ application: props.appName, row: cForm.row || undefined, contact_type: cForm.contact_type, participants: cForm.participants, notes: cForm.notes }),
	onSuccess() {
		showContact.value = false
		toast.success(__('Saved.'))
		app.reload()
	},
	onError(err) {
		toast.error(err.messages?.[0] || __('Could not save the entry.'))
	},
})
function onContact() {
	if (!contact.loading) contact.submit()
}

function stars(v) {
	return (Math.round((v || 0) * 5 * 10) / 10).toFixed(1)
}
function formatDate(v) {
	if (!v) return ''
	return new Date(v).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}
</script>
