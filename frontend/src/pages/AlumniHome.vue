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
					<p class="mt-1 text-xs text-ink-gray-5">
						{{ profile.data.program_completed }}
						<span v-if="profile.data.class_year">
							&nbsp;·&nbsp;{{ __('Class of') }} {{ profile.data.class_year }}
						</span>
					</p>
				</div>
			</div>
		</section>

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
						{{ __('Find classmates by program, class year, or organization.') }}
					</div>
				</div>
			</router-link>
		</nav>
	</div>
</template>

<script setup>
import { computed } from 'vue'
import { createResource } from 'frappe-ui'
import { GraduationCap, UserCog, Users } from 'lucide-vue-next'

const profile = createResource({
	url: 'seminary.alumni.api.get_my_profile',
	auto: true,
	cache: 'my-alumni-profile',
})

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
