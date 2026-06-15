<template>
	<header class="sticky top-0 z-10 flex items-center justify-between border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5">
		<h2 class="text-xl font-bold text-ink-gray-8">{{ __('Our People') }}</h2>
		<Button variant="solid" @click="openCreate">{{ __('Create contact') }}</Button>
	</header>

	<div v-if="people.loading" class="p-5 text-ink-gray-5">{{ __('Loading...') }}</div>
	<div v-else-if="people.error" class="p-5 text-ink-red-4">{{ people.error.messages?.[0] || __('Not authorized.') }}</div>

	<ul v-else class="mx-auto w-full max-w-3xl divide-y divide-outline-gray-1 px-3 sm:px-5">
		<li v-for="p in people.data" :key="p.row" class="flex items-start gap-4 py-4">
			<div class="grid size-11 shrink-0 place-items-center rounded-full bg-surface-gray-2 text-sm font-semibold text-ink-gray-7">
				{{ initials(p.full_name) }}
			</div>
			<div class="min-w-0 flex-1">
				<div class="flex flex-wrap items-center gap-2">
					<span class="font-semibold text-ink-gray-8">{{ p.full_name }}</span>
					<Badge v-if="p.is_primary" theme="blue" variant="subtle">{{ __('Primary') }}</Badge>
					<Badge v-if="p.portal_access" theme="green" variant="subtle">{{ __('Portal access') }}</Badge>
				</div>
				<div v-if="p.role_at_org" class="text-sm text-ink-gray-6">{{ p.role_at_org }}</div>
				<div class="text-xs text-ink-gray-5">
					{{ p.email }}<span v-if="p.mobile"> &middot; {{ p.mobile }}</span>
				</div>
			</div>
		</li>
	</ul>

	<Dialog v-model="showCreate" :options="{ title: __('Create contact') }">
		<template #body-content>
			<div class="flex flex-col gap-3">
				<div class="grid grid-cols-2 gap-3">
					<FormControl type="text" :label="__('First name')" v-model="cForm.first_name" />
					<FormControl type="text" :label="__('Last name')" v-model="cForm.last_name" />
				</div>
				<FormControl type="email" :label="__('Email')" v-model="cForm.email" />
				<FormControl type="text" :label="__('Mobile')" v-model="cForm.mobile" />
				<FormControl type="text" :label="__('Role at organization')" v-model="cForm.role_at_org" />
				<label class="flex items-center gap-2 text-sm text-ink-gray-7">
					<input type="checkbox" v-model="cForm.grant" class="rounded border-outline-gray-3" />
					{{ __('Grant portal access (creates a login and emails an invite)') }}
				</label>
				<Button variant="solid" :loading="create.loading" @click="onCreate">{{ __('Create contact') }}</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { createResource, Button, Badge, FormControl, Dialog, toast } from 'frappe-ui'
import { usePartnerOrg } from '@/composables/usePartnerOrg'

const { activeOrg } = usePartnerOrg()

const people = createResource({
	url: 'seminary.partner.portal.get_people',
	makeParams: () => ({ org: activeOrg.value }),
	auto: true,
})
watch(activeOrg, () => people.reload())

const showCreate = ref(false)
const cForm = reactive({ first_name: '', last_name: '', email: '', mobile: '', role_at_org: '', grant: false })
function openCreate() {
	Object.assign(cForm, { first_name: '', last_name: '', email: '', mobile: '', role_at_org: '', grant: false })
	showCreate.value = true
}

const create = createResource({
	url: 'seminary.partner.portal.create_contact',
	makeParams: () => ({
		first_name: cForm.first_name,
		last_name: cForm.last_name,
		email: cForm.email,
		mobile: cForm.mobile,
		role_at_org: cForm.role_at_org,
		grant_portal_access: cForm.grant ? '1' : '0',
		org: activeOrg.value,
	}),
	onSuccess() {
		showCreate.value = false
		toast.success(__('Contact created.'))
		people.reload()
	},
	onError(err) {
		toast.error(err.messages?.[0] || __('Could not create the contact.'))
	},
})
function onCreate() {
	if (!cForm.first_name || !cForm.email) {
		toast.error(__('First name and email are required.'))
		return
	}
	if (!create.loading) create.submit()
}

function initials(name) {
	return (name || '').split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('') || '?'
}
</script>
