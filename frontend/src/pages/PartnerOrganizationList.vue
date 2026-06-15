<template>
	<header
		class="sticky top-0 z-10 flex flex-col gap-2 border-b border-outline-gray-1 bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
			<h2 class="text-xl font-bold text-ink-gray-8">{{ __('Organizations') }}</h2>
			<div class="relative w-full sm:w-72">
				<Search class="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-gray-4" />
				<input
					v-model="query"
					type="search"
					class="w-full rounded-md border border-outline-gray-2 bg-surface-white py-1.5 pl-8 pr-3 text-sm text-ink-gray-8 focus:border-outline-gray-4 focus:outline-none"
					:placeholder="__('Search name, type, city')"
				/>
			</div>
		</div>
		<div class="flex flex-wrap items-center gap-2">
			<select v-model="partnerType" class="filter-select">
				<option value="">{{ __('All types') }}</option>
				<option v-for="pt in partnerTypes.data || []" :key="pt" :value="pt">{{ pt }}</option>
			</select>
		</div>
	</header>

	<div class="mx-auto flex w-full max-w-6xl flex-col gap-5 p-3 sm:p-5 lg:flex-row lg:items-start">
		<main class="min-w-0 flex-1">
			<div v-if="directory.loading" class="text-ink-gray-5">{{ __('Loading organizations...') }}</div>

			<div
				v-else-if="!directory.data?.length"
				class="mt-16 md:mt-28 mx-auto w-3/4 md:w-1/2 space-y-2 text-center text-ink-gray-5"
			>
				<Building2 class="mx-auto size-10 stroke-1 text-ink-gray-4" />
				<div class="text-xl font-medium">{{ __('No organizations found') }}</div>
				<div class="leading-5">{{ __('Try a different search or clear the filters.') }}</div>
			</div>

			<ul v-else class="grid grid-cols-1 gap-3 xl:grid-cols-2">
				<li v-for="org in directory.data" :key="org.name">
					<router-link
						:to="{ name: 'PartnerOrganizationDetail', params: { name: org.name } }"
						class="flex h-full flex-col gap-2 rounded-lg border border-outline-gray-2 bg-surface-white p-4 transition hover:border-outline-gray-3 hover:shadow-sm"
					>
						<div class="flex items-start justify-between gap-2">
							<span class="font-semibold text-ink-gray-8">{{ org.organization_name }}</span>
							<Badge v-if="org.partner_type" theme="blue" variant="subtle">
								{{ org.partner_type }}
							</Badge>
						</div>
						<div class="mt-auto flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-gray-5">
							<span v-if="org.city" class="flex items-center gap-1">
								<MapPin class="size-3.5" />{{ org.city }}
							</span>
							<span v-if="org.state">&middot; {{ org.state }}</span>
							<span v-if="org.country">&middot; {{ org.country }}</span>
						</div>
					</router-link>
				</li>
			</ul>
		</main>

		<aside class="w-full shrink-0 lg:w-80">
			<div class="rounded-lg border border-outline-gray-2 bg-surface-white p-4">
				<div class="mb-3 flex items-center justify-between gap-2">
					<h3 class="text-base font-semibold text-ink-gray-8">{{ myOrgsTitle }}</h3>
					<span v-if="myOrgs.data?.organizations?.length" class="rounded-full bg-surface-gray-2 px-2 py-0.5 text-xs font-medium text-ink-gray-6">
						{{ myOrgs.data.organizations.length }}
					</span>
				</div>

				<div v-if="myOrgs.loading" class="py-6 text-center text-sm text-ink-gray-5">{{ __('Loading...') }}</div>
				<ul v-else-if="myOrgs.data?.organizations?.length" class="space-y-2">
					<li v-for="org in myOrgs.data.organizations" :key="org.name" class="rounded-md border border-outline-gray-2 transition hover:border-outline-gray-3">
						<router-link
							:to="{ name: 'PartnerProfile' }"
							class="block rounded-md p-3 hover:bg-surface-gray-1"
						>
							<div class="flex items-start justify-between gap-2">
								<span class="text-sm font-medium text-ink-gray-8">{{ org.organization_name }}</span>
								<Badge :theme="listingTheme(org.listing_status)" variant="subtle">
									{{ __(org.listing_status) }}
								</Badge>
							</div>
							<div v-if="org.role_at_org" class="mt-0.5 text-xs text-ink-gray-6">{{ org.role_at_org }}</div>
						</router-link>
					</li>
				</ul>
				<div v-else class="py-6 text-center text-sm text-ink-gray-5">
					{{ __('You are not yet linked to any organization.') }}
				</div>

				<Button
					v-if="myOrgs.data?.can_create"
					class="mt-3 w-full"
					variant="solid"
					@click="openAdd"
				>
					{{ __('Add Organization') }}
				</Button>
			</div>
		</aside>
	</div>

	<Dialog v-model="showAdd" :options="{ title: __('Add Organization') }">
		<template #body-content>
			<div class="flex flex-col gap-3">
				<div class="rounded-md border border-outline-amber-2 bg-surface-amber-1 px-3 py-2 text-sm text-ink-amber-3">
					{{ __('You can only create an organization you are a member of and allowed to act on its behalf.') }}
				</div>
				<FormControl type="text" :label="__('Organization name')" v-model="form.organization_name" :required="true" />
				<FormControl type="text" :label="__('What is your role in this organization?')" v-model="form.role_at_org" />
				<FormControl type="text" :label="__('Website')" v-model="form.website" />
				<FormControl type="text" :label="__('City')" v-model="form.city" />
				<FormControl type="textarea" :label="__('About the organization')" v-model="form.about_us" />
				<label class="flex items-center gap-2 text-sm text-ink-gray-7">
					<input type="checkbox" v-model="form.is_primary" class="rounded border-outline-gray-3" />
					{{ __('I am the primary contact') }}
				</label>
				<Button variant="solid" :loading="create.loading" @click="onCreate">
					{{ __('Submit for approval') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { createResource, debounce, Badge, Button, Dialog, FormControl, toast } from 'frappe-ui'
import { Search, Building2, MapPin } from 'lucide-vue-next'

const query = ref('')
const partnerType = ref('')

const partnerTypes = createResource({
	url: 'seminary.partner.api.get_partner_types',
	auto: true,
})

const directory = createResource({
	url: 'seminary.partner.api.get_partner_directory',
	makeParams: () => ({
		query: query.value,
		partner_type: partnerType.value,
	}),
	auto: true,
})

const refetch = debounce(() => directory.reload(), 250)
watch([query, partnerType], refetch)

const myOrgs = createResource({
	url: 'seminary.partner.api.get_my_organizations',
	auto: true,
})

// Singular when the alumnus belongs to one org, plural otherwise — both strings
// reach Crowdin for translation.
const myOrgsTitle = computed(() =>
	(myOrgs.data?.organizations?.length === 1) ? __('My Organization') : __('My Organizations')
)

function listingTheme(status) {
	if (status === 'Listed') return 'green'
	if (status === 'Pending Approval') return 'orange'
	return 'gray'
}

// --- Add organization ----------------------------------------------------------
const showAdd = ref(false)
const form = reactive({
	organization_name: '',
	role_at_org: '',
	website: '',
	city: '',
	about_us: '',
	is_primary: false,
})

function openAdd() {
	form.organization_name = ''
	form.role_at_org = ''
	form.website = ''
	form.city = ''
	form.about_us = ''
	form.is_primary = false
	showAdd.value = true
}

const create = createResource({ url: 'seminary.partner.api.create_partner_organization' })

function onCreate() {
	if (!form.organization_name.trim()) {
		toast.error(__('Organization name is required.'))
		return
	}
	create.submit(
		{
			organization_name: form.organization_name,
			role_at_org: form.role_at_org,
			is_primary: form.is_primary ? 1 : 0,
			website: form.website,
			city: form.city,
			about_us: form.about_us,
		},
		{
			onSuccess: () => {
				showAdd.value = false
				myOrgs.reload()
				directory.reload()
				toast.success(__('Submitted for approval. Staff will review your organization.'))
			},
			onError: (err) => toast.error(err.messages?.[0] || __('Could not submit the organization.')),
		}
	)
}
</script>

<style scoped>
.filter-select {
	@apply rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm text-ink-gray-8 focus:border-outline-gray-4 focus:outline-none;
}
</style>
