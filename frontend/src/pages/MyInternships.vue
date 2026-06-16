<template>
	<header class="sticky top-0 z-10 flex items-center justify-between border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5">
		<h2 class="text-xl font-bold text-ink-gray-8">{{ __('My Internships') }}</h2>
		<Button variant="subtle" @click="$router.push({ name: 'Internships' })">{{ __('Browse internships') }}</Button>
	</header>

	<div v-if="mine.loading" class="p-5 text-ink-gray-5">{{ __('Loading...') }}</div>
	<div v-else-if="!mine.data?.length" class="mt-24 mx-auto w-3/4 md:w-1/2 space-y-2 p-5 text-center text-ink-gray-5">
		<Handshake class="mx-auto size-10 stroke-1 text-ink-gray-4" />
		<div class="text-xl font-medium">{{ __('No internships yet') }}</div>
		<div>{{ __('Apply to an internship to track it here.') }}</div>
	</div>

	<ul v-else class="mx-auto w-full max-w-3xl divide-y divide-outline-gray-1 px-3 sm:px-5">
		<li v-for="a in mine.data" :key="a.name" class="flex items-center gap-3 py-4">
			<router-link :to="{ name: 'MyInternship', params: { name: a.name } }" class="min-w-0 flex-1">
				<div class="flex flex-wrap items-center gap-2">
					<span class="font-semibold text-ink-gray-8">{{ a.title }}</span>
					<Badge :theme="statusTheme(a.status)" variant="subtle">{{ __(a.status) }}</Badge>
				</div>
				<div class="mt-0.5 text-xs text-ink-gray-5">
					<span v-if="a.organization_name">{{ a.organization_name }} &middot; </span>
					<span>{{ __('{0} / {1} hours logged').format(a.total_hours_logged || 0, a.hours_target || 0) }}</span>
				</div>
			</router-link>
			<div v-if="a.status === 'Draft'" class="flex items-center gap-1.5">
				<Button size="sm" variant="subtle" theme="red" @click="discard(a)">{{ __('Discard') }}</Button>
			</div>
			<Button v-else-if="WITHDRAWABLE.includes(a.status)" size="sm" variant="subtle" theme="red" @click="withdraw(a)">{{ __('Withdraw') }}</Button>
		</li>
	</ul>
</template>

<script setup>
import { createResource, Badge, Button, toast } from 'frappe-ui'
import { Handshake } from 'lucide-vue-next'

const WITHDRAWABLE = ['Submitted', 'Under Review', 'Accepted', 'Active']

const mine = createResource({
	url: 'seminary.partner.internship_api.get_my_internships',
	makeParams: () => ({}),
	auto: true,
})

const withdrawRes = createResource({ url: 'seminary.partner.internship_api.withdraw_application' })
const discardRes = createResource({ url: 'seminary.partner.internship_api.discard_draft' })
function withdraw(a) {
	withdrawRes.submit({ name: a.name }, { onSuccess: () => { toast.success(__('Withdrawn.')); mine.reload() }, onError: (e) => toast.error(e.messages?.[0] || __('Could not withdraw.')) })
}
function discard(a) {
	discardRes.submit({ name: a.name }, { onSuccess: () => { toast.success(__('Discarded.')); mine.reload() }, onError: (e) => toast.error(e.messages?.[0] || __('Could not discard.')) })
}

function statusTheme(s) {
	if (['Accepted', 'Active', 'Completed'].includes(s)) return 'green'
	if (['Rejected', 'Withdrawn'].includes(s)) return 'red'
	if (s === 'Under Review' || s === 'Submitted') return 'blue'
	return 'gray'
}
</script>
