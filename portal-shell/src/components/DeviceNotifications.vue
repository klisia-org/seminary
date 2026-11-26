<template>
	<!-- Notifications on this device (seminary decisions/121 §3 and its addendum). Hidden on a
	     site that cannot push. -->
	<section
		v-if="push.data?.available"
		class="rounded-lg border border-outline-gray-1 bg-surface-white p-5 shadow-sm"
	>
		<h3 class="mb-1 text-base font-semibold text-ink-gray-8">
			{{ __('Notifications on your devices') }}
		</h3>
		<p class="mb-3 text-sm text-ink-gray-5">
			{{ description || __('Get a notification on this phone or computer when something needs you.') }}
		</p>

		<p v-if="!supported && homeScreenFirst" class="text-sm text-ink-gray-7">
			{{ __('On iPhone and iPad, add this site to your Home Screen first: tap Share, then Add to Home Screen. Open it from the Home Screen and come back to this page.') }}
		</p>
		<p v-else-if="!supported" class="text-sm text-ink-gray-7">
			{{ __('This browser cannot show notifications.') }}
		</p>
		<p v-else-if="blocked" class="text-sm text-ink-gray-7">
			{{ __('Notifications are blocked for this site. Allow them in your browser settings, then reload this page.') }}
		</p>
		<div v-else class="flex flex-wrap items-center gap-2">
			<template v-if="thisDevice">
				<span class="text-sm text-ink-gray-7">{{ __('Notifications are on for this device.') }}</span>
				<Button size="sm" :loading="testing" @click="sendTest">{{ __('Send a test') }}</Button>
				<Button size="sm" variant="subtle" :loading="switching" @click="switchOff">
					{{ __('Turn off on this device') }}
				</Button>
			</template>
			<Button v-else variant="solid" size="sm" :loading="switching" @click="switchOn">
				{{ __('Turn on notifications on this device') }}
			</Button>
		</div>

		<div v-if="push.data.devices.length" class="mt-4">
			<p class="mb-1 text-xs font-medium text-ink-gray-5">{{ __('Your devices') }}</p>
			<div
				v-for="d in push.data.devices"
				:key="d.name"
				class="flex flex-wrap items-center gap-2 border-b border-outline-gray-1 py-2 text-sm last:border-b-0"
			>
				<span class="min-w-0 flex-1 truncate text-ink-gray-8">{{ d.device_label }}</span>
				<span
					v-if="d.endpoint_hash === myHash"
					class="rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-6"
				>
					{{ __('This device') }}
				</span>
				<span class="text-xs text-ink-gray-5">
					{{ d.last_used ? __('Last notified {0}', [formatDate(d.last_used)]) : __('Not notified yet') }}
				</span>
				<Button size="sm" variant="subtle" :label="__('Remove')" @click="removeDevice(d)" />
			</div>
		</div>
	</section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, call, createResource, toast } from 'frappe-ui'
import { __ } from '../translation.js'
import {
	currentSubscription,
	endpointHash,
	needsHomeScreen,
	permission,
	pushSupported,
	turnOff,
	turnOn,
} from '../webPush.js'

defineProps({
	// What reaches the devices, in the portal's own words.
	description: { type: String, default: '' },
})

const supported = pushSupported()
const homeScreenFirst = needsHomeScreen()
const blocked = ref(supported && permission() === 'denied')
const myHash = ref(null)
const switching = ref(false)
const testing = ref(false)
const push = createResource({
	url: 'seminary.seminary.web_push.get_my_push_settings',
	auto: true,
})
const thisDevice = computed(
	() => !!myHash.value && !!push.data?.devices?.some((d) => d.endpoint_hash === myHash.value)
)

async function readThisDevice() {
	const sub = await currentSubscription().catch(() => null)
	myHash.value = sub ? await endpointHash(sub.endpoint) : null
}
readThisDevice()

function formatDate(value) {
	return new Date(String(value).replace(' ', 'T')).toLocaleString()
}

async function switchOn() {
	switching.value = true
	try {
		await turnOn(push.data.public_key)
		await readThisDevice()
		await push.fetch()
		toast.success(__('Notifications are on for this device.'))
	} catch (e) {
		if (e?.message === 'denied') {
			blocked.value = permission() === 'denied'
			toast.error(__('Notifications were not allowed.'))
		} else {
			toast.error(e?.messages?.[0] || __('Could not turn on notifications.'))
		}
	} finally {
		switching.value = false
	}
}

async function switchOff() {
	switching.value = true
	try {
		await turnOff()
		myHash.value = null
		await push.fetch()
	} catch (e) {
		toast.error(e?.messages?.[0] || __('Could not turn off notifications.'))
	} finally {
		switching.value = false
	}
}

async function sendTest() {
	testing.value = true
	try {
		await call('seminary.seminary.web_push.send_test_notification')
		toast.success(__('Sent. It should arrive in a few seconds.'))
	} catch (e) {
		toast.error(e?.messages?.[0] || __('Could not send a test.'))
	} finally {
		testing.value = false
	}
}

async function removeDevice(d) {
	try {
		if (d.endpoint_hash === myHash.value) {
			await turnOff()
			myHash.value = null
		} else {
			await call('seminary.seminary.web_push.remove_device', { name: d.name })
		}
		await push.fetch()
	} catch (e) {
		toast.error(e?.messages?.[0] || __('Could not remove the device.'))
	}
}
</script>
