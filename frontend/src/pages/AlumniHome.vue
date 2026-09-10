<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<h2 class="text-xl font-bold text-ink-gray-8">
			{{ __('Alumni') }}
		</h2>
	</header>

	<div v-if="profile.loading" class="p-5 text-ink-gray-5">
		{{ __('Loading...') }}
	</div>

	<div
		v-else-if="!profile.data"
		class="mt-32 md:mt-52 mx-auto w-3/4 md:w-1/2 space-y-2 p-5 text-center text-ink-gray-5"
	>
		<GraduationCap class="mx-auto size-10 stroke-1 text-ink-gray-4" />
		<div class="text-xl font-medium">{{ __('No alumni profile') }}</div>
		<div class="leading-5">
			{{ __('You are not yet registered as an alumnus. The registrar will create your profile when you complete your program.') }}
		</div>
	</div>

	<div v-else class="mx-auto w-full max-w-3xl space-y-6 p-5">
		<section
			class="rounded-lg border border-outline-gray-1 bg-surface-white p-6 shadow-sm"
		>
			<div class="flex items-start gap-4">
				<div
					class="grid size-16 shrink-0 place-items-center rounded-full bg-surface-gray-2 text-2xl font-semibold text-ink-gray-7"
				>
					{{ initials }}
				</div>
				<div class="min-w-0 flex-1">
					<h1 class="text-xl font-semibold text-ink-gray-8">
						{{ profile.data.full_name }}
					</h1>
					<p v-if="profile.data.current_role" class="text-sm text-ink-gray-6">
						{{ profile.data.current_role }}
						<span v-if="profile.data.current_organization">
							&nbsp;·&nbsp;{{ profile.data.current_organization }}
						</span>
					</p>
					<!-- One line per completed program: a second degree adds a
					     row, it does not replace the first (ADR 069). -->
					<p
						v-for="grad in profile.data.graduations"
						:key="grad.name"
						class="mt-1 text-xs text-ink-gray-5"
					>
						{{ grad.program }}
						<span v-if="grad.class_year">
							&nbsp;·&nbsp;{{ __('Class of') }} {{ grad.class_year }}
						</span>
					</p>
				</div>
			</div>
		</section>

		<!-- Only where a school has asked alumni to lead, and only for the types
		     this person can join or start: for everybody else the resource comes
		     back empty and the section is not there at all. -->
		<section
			v-if="communities.data?.length"
			class="rounded-lg border border-outline-gray-1 bg-surface-white p-6 shadow-sm"
		>
			<h3 class="font-semibold text-ink-gray-8">{{ __('My communities') }}</h3>
			<ul class="mt-4 space-y-4">
				<li
					v-for="type in communities.data"
					:key="type.cohort_type"
					class="rounded-md border border-outline-gray-1 p-3"
				>
					<div class="font-medium text-ink-gray-8">{{ type.type_name }}</div>
					<div v-if="type.description" class="text-xs text-ink-gray-5">
						{{ type.description }}
					</div>

					<!-- Where they already stand: a group they belong to, or one
					     they have been asked to join. -->
					<ul v-if="type.memberships.length" class="mt-3 space-y-2">
						<li
							v-for="m in type.memberships"
							:key="m.membership"
							class="flex flex-wrap items-center justify-between gap-3 rounded-md bg-surface-gray-1 p-3"
						>
							<div class="min-w-0">
								<div class="text-sm font-medium text-ink-gray-8">
									{{ m.cohort_name }}
									<span
										v-if="m.status === 'Archived'"
										class="ml-1 text-xs font-normal text-ink-gray-5"
									>
										· {{ __('Archived') }}
									</span>
								</div>
								<div v-if="m.invite_status === 'Invited'" class="text-xs text-ink-gray-6">
									{{ __('You have been invited to join. {0} leads it.').format(m.leader_name || __('Someone else')) }}
								</div>
								<div v-else class="text-xs text-ink-gray-6">
									<template v-if="m.is_leader">{{ __('You lead it') }}</template>
									<template v-else-if="m.leader_name">
										{{ __('Led by {0}').format(m.leader_name) }}
									</template>
									<template v-if="m.member_count">
										&nbsp;·&nbsp;{{ __('{0} members').format(m.member_count) }}
									</template>
								</div>
								<div v-if="m.lineage_name" class="text-xs text-ink-gray-5">
									{{ __('Part of {0}, which has grown into {1} groups').format(m.lineage_name, m.lineage_size) }}
								</div>
							</div>
							<Button
								variant="subtle"
								:label="m.invite_status === 'Invited' ? __('See the invitation') : __('My cohort')"
								@click="openCohort(m)"
							/>
						</li>
					</ul>

					<p v-else class="mt-2 text-sm text-ink-gray-6">
						{{ __("You currently don't participate in any cohort of this type. Start your own group and invite the people you want to walk with.") }}
					</p>

					<div v-if="type.may_start" class="mt-3">
						<div v-if="type.portal_size_limit" class="mb-2 text-xs text-ink-gray-5">
							{{ __('Up to {0} people').format(type.portal_size_limit) }}
						</div>
						<Button
							variant="subtle"
							:label="type.memberships.length ? __('Start a new cohort') : __('Start a group')"
							@click="openStart(type)"
						/>
					</div>
				</li>
			</ul>
		</section>

		<!-- The panel decides for itself whether it belongs here: it is shown
		     where the seminary lets alumni act for an organization, and also
		     where this one already belongs to something, so an existing link
		     does not vanish when creation is switched off. -->
		<MyOrganizationsPanel hide-when-empty />

		<nav class="grid gap-3 sm:grid-cols-2">
			<router-link
				to="/alumni/profile"
				class="flex items-center gap-3 rounded-lg border border-outline-gray-1 bg-surface-white p-4 hover:border-outline-gray-3"
			>
				<UserCog class="size-5 text-ink-gray-6" />
				<div>
					<div class="font-medium text-ink-gray-8">{{ __('Edit my profile') }}</div>
					<div class="text-xs text-ink-gray-5">
						{{ __('Update your role, organization, bio, and visibility.') }}
					</div>
				</div>
			</router-link>
			<router-link
				to="/alumni/directory"
				class="flex items-center gap-3 rounded-lg border border-outline-gray-1 bg-surface-white p-4 hover:border-outline-gray-3"
			>
				<Users class="size-5 text-ink-gray-6" />
				<div>
					<div class="font-medium text-ink-gray-8">{{ __('Alumni directory') }}</div>
					<div class="text-xs text-ink-gray-5">
						{{ __('Find classmates by name, role, organization or city, and filter by program and graduation years.') }}
					</div>
				</div>
			</router-link>
		</nav>
	</div>

	<Dialog v-model="showStart" :options="{ title: __('Start a group') }">
		<template #body-content>
			<p class="mb-3 text-sm text-ink-gray-6">
				{{ startType?.type_name }}
			</p>
			<Input
				v-model="startName"
				type="text"
				:placeholder="__('What is it called?')"
				@keyup.enter="submitStart"
			/>
			<p class="mt-3 text-xs text-ink-gray-5">
				{{ __('You lead what you start. Invite people once it exists.') }}
			</p>
		</template>
		<template #actions>
			<Button
				variant="solid"
				:label="__('Create')"
				:loading="startRes.loading"
				@click="submitStart"
			/>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Dialog, Input, createResource } from 'frappe-ui'
import { GraduationCap, UserCog, Users } from 'lucide-vue-next'
import MyOrganizationsPanel from '@/components/MyOrganizationsPanel.vue'

const router = useRouter()

const profile = createResource({
	url: 'seminary.alumni.api.get_my_profile',
	auto: true,
	cache: 'my-alumni-profile',
})

const communities = createResource({
	url: 'seminary.seminary.discipleship.api.my_communities',
	auto: true,
})

const showStart = ref(false)
const startType = ref(null)
const startName = ref('')

function openStart(type) {
	startType.value = type
	startName.value = ''
	showStart.value = true
}

// The community page is where a cohort lives; `members` asks it to open the
// roster on arrival, which is what someone clicking their own cohort came for.
function openCohort(membership) {
	router.push({
		path: '/community',
		query: { cohort: membership.cohort, members: 1 },
	})
}

const startRes = createResource({
	url: 'seminary.seminary.discipleship.api.create_my_cohort',
	onSuccess(name) {
		showStart.value = false
		communities.reload()
		// Straight into the group: the next thing they want is to invite people.
		router.push({ path: '/community', query: { cohort: name, members: 1 } })
	},
})

function submitStart() {
	if (!startName.value.trim() || startRes.loading) return
	startRes.submit({
		cohort_name: startName.value.trim(),
		cohort_type: startType.value.cohort_type,
	})
}

const initials = computed(() => {
	const name = profile.data?.full_name || ''
	return name
		.split(/\s+/)
		.filter(Boolean)
		.slice(0, 2)
		.map((part) => part[0].toUpperCase())
		.join('') || '?'
})
</script>
