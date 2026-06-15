<template>
	<header
		class="sticky top-0 z-10 flex items-center gap-2 border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<router-link
			:to="{ name: 'PartnerOrganizationList' }"
			class="flex items-center gap-1 text-sm text-ink-gray-6 hover:text-ink-gray-8"
		>
			<ArrowLeft class="size-4" />
			{{ __('Organizations') }}
		</router-link>
	</header>

	<div v-if="org.loading" class="p-5 text-ink-gray-5">{{ __('Loading...') }}</div>

	<div v-else-if="org.error" class="p-5 text-ink-red-4">
		{{ org.error.messages?.[0] || __('This organization is not available.') }}
	</div>

	<div v-else-if="org.data" class="mx-auto w-full max-w-3xl px-4 py-6 text-ink-gray-8 sm:px-6">
		<div class="flex flex-wrap items-start justify-between gap-3">
			<div class="min-w-0">
				<h1 class="text-2xl font-bold text-ink-gray-9">{{ org.data.organization_name }}</h1>
				<div class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink-gray-5">
					<span v-if="org.data.city" class="flex items-center gap-1">
						<MapPin class="size-3.5" />{{ org.data.city }}
					</span>
					<span v-if="org.data.state">&middot; {{ org.data.state }}</span>
					<span v-if="org.data.country">&middot; {{ org.data.country }}</span>
				</div>
			</div>
			<Badge v-if="org.data.partner_type" theme="blue" variant="subtle" size="lg">
				{{ org.data.partner_type }}
			</Badge>
		</div>

		<div class="mt-3 flex flex-wrap items-center gap-3 text-sm">
			<a
				v-if="org.data.website"
				:href="org.data.website"
				target="_blank"
				rel="noopener"
				class="flex items-center gap-1 text-ink-blue-6 hover:underline"
			>
				<Globe class="size-4" />{{ __('Website') }}
			</a>
			<a
				v-if="org.data.primary_email"
				:href="`mailto:${org.data.primary_email}`"
				class="flex items-center gap-1 text-ink-blue-6 hover:underline"
			>
				<Mail class="size-4" />{{ org.data.primary_email }}
			</a>
		</div>

		<div v-if="org.data.about_us" class="prose-sm mt-6 max-w-none text-ink-gray-7" v-html="org.data.about_us" />

		<router-link
			v-if="org.data.open_openings"
			:to="{ name: 'Jobs' }"
			class="mt-6 inline-flex items-center gap-2 rounded-lg border border-outline-gray-2 bg-surface-white px-4 py-2 text-sm font-medium text-ink-gray-8 transition hover:border-outline-gray-3"
		>
			<Briefcase class="size-4" />
			{{ __('{0} open opening(s)').format(org.data.open_openings) }}
		</router-link>
	</div>
</template>

<script setup>
import { createResource, Badge } from 'frappe-ui'
import { ArrowLeft, MapPin, Globe, Mail, Briefcase } from 'lucide-vue-next'

const props = defineProps({ name: { type: String, required: true } })

const org = createResource({
	url: 'seminary.partner.api.get_partner_organization',
	makeParams: () => ({ name: props.name }),
	auto: true,
})
</script>
