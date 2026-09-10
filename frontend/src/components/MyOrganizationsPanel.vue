<template>
	<div v-if="visible" class="rounded-lg border border-outline-gray-2 bg-surface-white p-4">
		<div class="mb-3 flex items-center justify-between gap-2">
			<h3 class="text-base font-semibold text-ink-gray-8">{{ title }}</h3>
			<span
				v-if="organizations.length"
				class="rounded-full bg-surface-gray-2 px-2 py-0.5 text-xs font-medium text-ink-gray-6"
			>
				{{ organizations.length }}
			</span>
		</div>

		<div v-if="myOrgs.loading" class="py-6 text-center text-sm text-ink-gray-5">
			{{ __('Loading...') }}
		</div>

		<ul v-else-if="organizations.length" class="space-y-2">
			<li
				v-for="org in organizations"
				:key="org.name"
				class="rounded-md border border-outline-gray-2 transition"
				:class="isReachable(org) ? 'hover:border-outline-gray-3' : ''"
			>
				<!-- Only a Listed organization has a page to open: the detail
				     endpoint refuses anything else, and an alumnus-created org
				     starts as Pending Approval. A row that cannot be opened is
				     rendered as a row, not as a link that fails. -->
				<router-link
					v-if="isReachable(org)"
					:to="`/alumni/organizations/${org.name}`"
					class="block rounded-md p-3 hover:bg-surface-gray-1"
				>
					<div class="flex items-start justify-between gap-2">
						<span class="text-sm font-medium text-ink-gray-8">{{ org.organization_name }}</span>
						<Badge :theme="listingTheme(org.listing_status)" variant="subtle">
							{{ __(org.listing_status) }}
						</Badge>
					</div>
					<div v-if="org.role_at_org" class="mt-0.5 text-xs text-ink-gray-6">
						{{ org.role_at_org }}
					</div>
				</router-link>
				<div v-else class="p-3">
					<div class="flex items-start justify-between gap-2">
						<span class="text-sm font-medium text-ink-gray-8">{{ org.organization_name }}</span>
						<Badge :theme="listingTheme(org.listing_status)" variant="subtle">
							{{ __(org.listing_status) }}
						</Badge>
					</div>
					<div v-if="org.role_at_org" class="mt-0.5 text-xs text-ink-gray-6">
						{{ org.role_at_org }}
					</div>
					<div class="mt-1 text-xs text-ink-gray-5">
						{{ __('Staff are reviewing this. It appears in the directory once approved.') }}
					</div>
				</div>
			</li>
		</ul>

		<div v-else class="py-6 text-center text-sm text-ink-gray-5">
			{{ __('You are not yet linked to any organization.') }}
		</div>

		<Button v-if="myOrgs.data?.can_create" class="mt-3 w-full" variant="solid" @click="openAdd">
			{{ __('Add Organization') }}
		</Button>
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
import { ref, reactive, computed } from 'vue'
import { createResource, Badge, Button, Dialog, FormControl, toast } from 'frappe-ui'

const props = defineProps({
	//: On a page where this is one section among others (AlumniHome), a panel
	//: offering nothing and permitting nothing is noise. On the organizations
	//: page it is the sidebar and always belongs.
	hideWhenEmpty: { type: Boolean, default: false },
})
const emit = defineEmits(['created'])

const myOrgs = createResource({
	url: 'seminary.partner.api.get_my_organizations',
	auto: true,
	onError() {},
})

const organizations = computed(() => myOrgs.data?.organizations || [])

const visible = computed(() => {
	if (!props.hideWhenEmpty) return true
	// Still loading, or the endpoint refused because the partner directory is
	// off: show nothing rather than an empty box that may never fill.
	if (!myOrgs.data) return false
	return !!(myOrgs.data.can_create || organizations.value.length)
})

// Singular when the alumnus belongs to one org, plural otherwise — both strings
// reach Crowdin for translation.
const title = computed(() =>
	organizations.value.length === 1 ? __('My Organization') : __('My Organizations')
)

function listingTheme(status) {
	if (status === 'Listed') return 'green'
	if (status === 'Pending Approval') return 'orange'
	return 'gray'
}

function isReachable(org) {
	return org.listing_status === 'Listed'
}

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
	Object.assign(form, {
		organization_name: '',
		role_at_org: '',
		website: '',
		city: '',
		about_us: '',
		is_primary: false,
	})
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
				emit('created')
				toast.success(__('Submitted for approval. Staff will review your organization.'))
			},
			onError: (err) => toast.error(err.messages?.[0] || __('Could not submit the organization.')),
		}
	)
}

defineExpose({ myOrgs })
</script>
