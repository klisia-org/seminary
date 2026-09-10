<template>
	<Dialog v-model="show" :options="{ title: profile.data?.full_name || __('Alumni profile') }">
		<template #body-content>
			<div v-if="profile.loading" class="py-6 text-center text-sm text-ink-gray-5">
				{{ __('Loading...') }}
			</div>

			<div v-else-if="profile.error" class="py-6 text-center text-sm text-ink-gray-5">
				{{ __('This profile is not available.') }}
			</div>

			<div v-else-if="profile.data" class="space-y-4 text-sm">
				<div class="flex items-start gap-3">
					<img
						v-if="profile.data.image"
						:src="profile.data.image"
						:alt="profile.data.full_name"
						class="size-14 shrink-0 rounded-full object-cover"
					/>
					<div class="min-w-0">
						<div v-if="profile.data.current_role" class="text-ink-gray-8">
							{{ profile.data.current_role }}
						</div>
						<router-link
							v-if="profile.data.partner_organization"
							:to="`/alumni/organizations/${profile.data.partner_organization.name}`"
							class="text-ink-blue-link hover:text-ink-blue-3"
						>
							{{ profile.data.partner_organization.organization_name }}
						</router-link>
						<div v-else-if="profile.data.current_organization" class="text-ink-gray-6">
							{{ profile.data.current_organization }}
						</div>
						<div v-if="place" class="text-xs text-ink-gray-5">{{ place }}</div>
					</div>
				</div>

				<div v-if="profile.data.graduations?.length" class="space-y-0.5">
					<p
						v-for="(g, i) in profile.data.graduations"
						:key="i"
						class="text-xs text-ink-gray-6"
					>
						{{ g.program }}
						<span v-if="g.class_year">· {{ __('Class of') }} {{ g.class_year }}</span>
					</p>
				</div>

				<p v-if="profile.data.bio" class="whitespace-pre-line text-ink-gray-7">
					{{ profile.data.bio }}
				</p>

				<div v-if="profile.data.contacts?.length" class="space-y-1.5">
					<h4 class="text-xs font-medium text-ink-gray-5">{{ __('Contact') }}</h4>
					<div
						v-for="(c, i) in profile.data.contacts"
						:key="i"
						class="flex items-center gap-2"
					>
						<span class="w-20 shrink-0 text-xs text-ink-gray-5">
							{{ __(c.channel_name || c.channel) }}
						</span>
						<a
							v-if="c.url"
							:href="c.url"
							target="_blank"
							rel="noopener"
							class="truncate text-ink-blue-link hover:text-ink-blue-3"
						>
							{{ c.value }}
						</a>
						<span v-else class="truncate text-ink-gray-8">{{ c.value }}</span>
					</div>
				</div>

				<a
					v-if="profile.data.linkedin_url"
					:href="profile.data.linkedin_url"
					target="_blank"
					rel="noopener"
					class="inline-block text-ink-blue-link hover:text-ink-blue-3"
				>
					LinkedIn
				</a>

				<!-- Shown whether or not they published an address: someone who
				     shared nothing is still reachable, and someone who shared an
				     address may still prefer a message here. -->
				<div v-if="profile.data.relay_available" class="border-t border-outline-gray-1 pt-3">
					<p v-if="!profile.data.contacts?.length" class="mb-2 text-xs text-ink-gray-5">
						{{ __('{0} has not shared contact details, but you can write to them here.').format(firstName) }}
					</p>
					<textarea
						v-model="message"
						rows="4"
						class="w-full rounded-md border-outline-gray-2 bg-surface-white text-sm text-ink-gray-7 focus:ring-0"
						:placeholder="__('Write a message...')"
					/>
					<p class="mt-1 text-xs text-ink-gray-5">
						{{ __('They will see your name and can reply from their inbox. Your contact details are not shared.') }}
					</p>
					<Button
						class="mt-2"
						variant="solid"
						:loading="sending.loading"
						:label="__('Send message')"
						@click="send"
					/>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, Dialog, createResource } from 'frappe-ui'
import { createToast } from '@/utils'

const props = defineProps({ modelValue: { type: String, default: null } })
const emit = defineEmits(['update:modelValue'])

const message = ref('')

const show = computed({
	get: () => !!props.modelValue,
	set: (value) => {
		if (!value) emit('update:modelValue', null)
	},
})

const profile = createResource({
	url: 'seminary.alumni.api.get_directory_profile',
	makeParams: () => ({ name: props.modelValue }),
})

watch(
	() => props.modelValue,
	(name) => {
		message.value = ''
		if (name) profile.fetch()
	}
)

const place = computed(() =>
	[profile.data?.city, profile.data?.country].filter(Boolean).join(', ')
)

const firstName = computed(() => (profile.data?.full_name || '').split(/\s+/)[0] || '')

const sending = createResource({
	url: 'seminary.alumni.api.send_directory_message',
	onSuccess() {
		message.value = ''
		createToast({
			title: __('Message sent.'),
			icon: 'check',
			iconClasses: 'text-ink-green-3',
		})
	},
	onError(e) {
		createToast({
			title: e.messages?.[0] || __('Could not send that message.'),
			icon: 'x',
			iconClasses: 'text-ink-red-3',
		})
	},
})

function send() {
	if (!message.value.trim()) return
	sending.submit({ profile: props.modelValue, message: message.value.trim() })
}
</script>
