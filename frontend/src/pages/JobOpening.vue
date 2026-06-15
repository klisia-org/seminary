<template>
	<header
		class="sticky top-0 z-10 flex items-center gap-2 border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<router-link
			:to="{ name: 'Jobs' }"
			class="flex items-center gap-1 text-sm text-ink-gray-6 hover:text-ink-gray-8"
		>
			<ArrowLeft class="size-4" />
			{{ __('Jobs') }}
		</router-link>
	</header>

	<div v-if="opening.loading" class="p-5 text-ink-gray-5">{{ __('Loading...') }}</div>

	<div v-else-if="opening.error" class="p-5 text-ink-red-4">
		{{ opening.error.messages?.[0] || __('This job opening is not available.') }}
	</div>

	<div v-else-if="opening.data" class="mx-auto w-full max-w-3xl px-4 py-6 text-ink-gray-8 sm:px-6">
		<!-- Title + key facts -->
		<div class="flex flex-wrap items-start justify-between gap-3">
			<div class="min-w-0">
				<h1 class="text-2xl font-bold text-ink-gray-9">{{ opening.data.job_title }}</h1>
				<div class="mt-1 text-base text-ink-gray-6">
					{{ opening.data.organization?.organization_name }}
				</div>
			</div>
			<Badge
				:theme="opening.data.status === 'Open' ? 'green' : 'gray'"
				variant="subtle"
				size="lg"
			>
				{{ __(opening.data.status) }}
			</Badge>
		</div>

		<div v-if="opening.data.position_type || opening.data.require_doctrinal_alignment" class="mt-2 flex flex-wrap items-center gap-1.5">
			<Badge v-if="opening.data.position_type" theme="gray" variant="subtle">
				{{ __(opening.data.position_type) }}
			</Badge>
			<Badge v-if="opening.data.require_doctrinal_alignment" theme="orange" variant="subtle">
				{{ __('Requires doctrinal agreement') }}
			</Badge>
		</div>

		<div class="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-gray-5">
			<span v-if="opening.data.employment_type" class="flex items-center gap-1">
				<Briefcase class="size-4" />{{ __(opening.data.employment_type) }}
			</span>
			<span v-if="locationCity" class="flex items-center gap-1">
				<MapPin class="size-4" />{{ locationCity }}
			</span>
			<span v-if="opening.data.ministry_setting">&middot; {{ __(opening.data.ministry_setting) }}</span>
			<span v-if="opening.data.vacancies">
				&middot; {{ __('{0} opening(s)').format(opening.data.vacancies) }}
			</span>
			<span v-if="opening.data.closes_on">
				&middot; {{ __('Closes {0}').format(formatDate(opening.data.closes_on)) }}
			</span>
		</div>

		<!-- Apply -->
		<div class="mt-5 flex flex-col gap-2">
			<template v-if="opening.data.can_apply">
				<Button variant="solid" size="md" @click="apply">
					{{ opening.data.has_draft ? __('Continue your application') : __('Apply for this position') }}
				</Button>
				<div v-if="opening.data.has_draft" class="text-xs text-ink-gray-5">
					{{ __('You have a saved draft for this opening.') }}
				</div>
			</template>
			<div
				v-else-if="opening.data.already_applied"
				class="flex items-center gap-2 rounded-md bg-surface-green-2 px-3 py-2 text-sm text-ink-green-3"
			>
				<CheckCircle2 class="size-4" />
				{{ __('You have already applied to this opening.') }}
			</div>
			<div
				v-else-if="opening.data.status !== 'Open'"
				class="rounded-md bg-surface-gray-2 px-3 py-2 text-sm text-ink-gray-6"
			>
				{{ __('This opening is closed and no longer accepting applications.') }}
			</div>
			<div
				v-else
				class="rounded-md bg-surface-gray-2 px-3 py-2 text-sm text-ink-gray-6"
			>
				{{ __('This opening is open to a specific audience and is not available to you.') }}
			</div>
		</div>

		<!-- Applications received -->
		<div
			v-if="opening.data.show_application_count"
			class="mt-3 flex items-center gap-1.5 text-sm text-ink-gray-5"
		>
			<Users class="size-4" />
			{{ __('{0} application(s) received').format(opening.data.application_count || 0) }}
		</div>

		<!-- Skills -->
		<section v-if="opening.data.skills?.length" class="mt-6">
			<h2 class="mb-2 text-base font-semibold text-ink-gray-8">{{ __('Skills') }}</h2>
			<div class="flex flex-wrap gap-1.5">
				<Badge v-for="skill in opening.data.skills" :key="skill" theme="gray" variant="subtle">
					{{ skill }}
				</Badge>
			</div>
		</section>

		<!-- Description -->
		<section v-if="opening.data.description" class="mt-6">
			<h2 class="mb-2 text-base font-semibold text-ink-gray-8">{{ __('Description') }}</h2>
			<div class="prose-sm max-w-none text-ink-gray-7" v-html="opening.data.description" />
		</section>

		<!-- Qualifications -->
		<section v-if="opening.data.qualifications" class="mt-6">
			<h2 class="mb-2 text-base font-semibold text-ink-gray-8">{{ __('Qualifications') }}</h2>
			<div class="prose-sm max-w-none text-ink-gray-7" v-html="opening.data.qualifications" />
		</section>

		<!-- Location -->
		<section v-if="hasLocation" class="mt-6">
			<h2 class="mb-2 text-base font-semibold text-ink-gray-8">{{ __('Location') }}</h2>
			<div class="text-sm text-ink-gray-7">
				<div v-if="loc.location_name" class="font-medium text-ink-gray-8">{{ loc.location_name }}</div>
				<div v-if="addressLine">{{ addressLine }}</div>
				<div class="mt-1 flex flex-wrap items-center gap-x-2 text-ink-gray-5">
					<span v-if="loc.ministry_setting">{{ __(loc.ministry_setting) }}</span>
					<span v-if="loc.ministry_setting && loc.congregation_size">&middot;</span>
					<span v-if="loc.congregation_size">
						{{ __('Congregation') }}: {{ loc.congregation_size }}
					</span>
				</div>
			</div>
		</section>

		<!-- About the organization -->
		<section
			v-if="org.about_us || org.doctrinal_statement || org.website || org.image"
			class="mt-8 border-t border-outline-gray-1 pt-6"
		>
			<h2 class="mb-2 text-base font-semibold text-ink-gray-8">
				{{ __('About {0}').format(org.organization_name) }}
			</h2>
			<a
				v-if="org.website"
				:href="org.website"
				target="_blank"
				rel="noopener"
				class="text-sm text-ink-blue-6 hover:underline"
			>
				{{ org.website }}
			</a>
			<img
				v-if="org.image"
				:src="org.image"
				:alt="org.organization_name"
				class="mt-3 max-h-16 w-auto rounded"
			/>
			<div
				v-if="org.about_us"
				class="prose-sm mt-2 max-w-none text-ink-gray-7"
				v-html="org.about_us"
			/>
			<details v-if="org.doctrinal_statement" class="mt-4">
				<summary class="cursor-pointer text-sm font-medium text-ink-gray-7">
					{{ __('Doctrinal statement') }}
				</summary>
				<div
					class="prose-sm mt-2 max-w-none text-ink-gray-7"
					v-html="org.doctrinal_statement"
				/>
			</details>
		</section>
	</div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { createResource, Button, Badge } from 'frappe-ui'
import { ArrowLeft, Briefcase, MapPin, CheckCircle2, Users } from 'lucide-vue-next'

const props = defineProps({
	jobName: { type: String, required: true },
})

const router = useRouter()

const opening = createResource({
	url: 'seminary.partner.api.get_job_opening',
	makeParams: () => ({ name: props.jobName }),
	auto: true,
})

const org = computed(() => opening.data?.organization || {})
const loc = computed(() => opening.data?.location || {})

const locationCity = computed(() => loc.value.city || org.value.city || '')

const hasLocation = computed(() => {
	const l = loc.value
	return !!(l.location_name || l.address_line_1 || l.city || l.ministry_setting || l.congregation_size)
})

const addressLine = computed(() => {
	const l = loc.value
	return [l.address_line_1, l.address_line_2, l.city, l.state, l.pincode, l.country]
		.filter(Boolean)
		.join(', ')
})

function apply() {
	router.push({ name: 'JobApplication', params: { jobName: props.jobName } })
}

function formatDate(value) {
	if (!value) return ''
	return new Date(value).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}
</script>
