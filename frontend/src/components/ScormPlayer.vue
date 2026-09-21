<!--
  The SCORM player (privatedocs p009 §2.11, S8).

  It renders one thing: a cross-origin iframe pointing at the delivery host, and
  it is the **only** party that talks to the LMS on the package's behalf. The
  package runs on an origin with no session, no CSRF token and no cookie of the
  app's; its runtime posts here, this component checks the message, and this
  component makes the API call with the user's own session.

  Two checks on every message, and neither is sufficient alone:

  * `event.origin` is the delivery origin the launch named -- not a prefix
    match, not `includes`;
  * `event.source` is this iframe's own window, so a *different* frame on the
    same origin cannot speak for the package we launched.

  The sandbox keeps `allow-same-origin` deliberately. It grants the framed
  document **its own** origin -- the delivery host -- which the launcher needs to
  reach the SCO frame and which the package needs for its own storage. It grants
  nothing against this origin, because the framed document is not same-origin
  with us. That pairing is only self-defeating when the framed content shares the
  framer's origin, which §2.2 makes impossible.
-->
<template>
	<div class="scorm-player">
		<div v-if="launch.loading" class="scorm-note">
			{{ __('Loading…') }}
		</div>

		<div v-else-if="status === 'Ready'" class="scorm-stage">
			<iframe
				ref="frame"
				:src="launcherUrl"
				:title="__('Course content')"
				class="scorm-frame"
				sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox allow-presentation allow-downloads"
				allow="autoplay; fullscreen; encrypted-media"
			/>
			<div v-if="reviewMode" class="scorm-badge">
				{{ __('Preview — nothing you do here is recorded') }}
			</div>
		</div>

		<div v-else class="scorm-note">
			<p class="font-medium text-ink-gray-7">{{ stateTitle }}</p>
			<p class="mt-1">{{ stateDetail }}</p>
			<p v-if="failureReason" class="mt-3 font-mono text-xs text-ink-gray-5">
				{{ failureReason }}
			</p>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, onMounted, ref } from 'vue'
import { createResource } from 'frappe-ui'

const props = defineProps({
	chapter: { type: String, required: true },
	sco: { type: String, default: null },
})

const user = inject('$user')
const frame = ref(null)
const payload = ref(null)
let heartbeat = null

const launch = createResource({
	url: 'seminary.scorm.launch.launch',
	makeParams() {
		return { chapter: props.chapter }
	},
	auto: true,
	onSuccess(data) {
		payload.value = data
		if (data?.status === 'Ready') {
			startHeartbeat(data)
		}
	},
})

const status = computed(() => payload.value?.status || null)
const reviewMode = computed(() => payload.value?.mode === 'review')
const failureReason = computed(() => payload.value?.failure_reason || null)

const launcherUrl = computed(() => {
	const data = payload.value
	if (!data?.launcher) return null
	// The SCO is named, never indexed: the server matches it against the
	// package's own items and falls back to the first.
	const sco = props.sco || data.scos?.[0]?.id
	return sco
		? `${data.launcher}?sco=${encodeURIComponent(sco)}`
		: data.launcher
})

const stateTitle = computed(() => {
	if (status.value === 'Failed') return __('This package could not be prepared')
	if (status.value === 'Pending' || status.value === 'Exploding')
		return __('Preparing this package')
	return __('This chapter cannot be played')
})

const stateDetail = computed(() => {
	if (status.value === 'Failed') {
		// The reason names files inside the instructor's package; the server
		// only sends it to staff, and the student gets the plain sentence.
		return failureReason.value
			? __('Ask your instructor — the details are below.')
			: __('Ask your instructor; this package needs to be re-uploaded.')
	}
	if (status.value === 'Pending' || status.value === 'Exploding')
		return __('This takes a moment for a large package. Reload shortly.')
	return __('Playing SCORM content is not available on this site.')
})

/* ------------------------------------------------------------- the bridge */

function isOurs(event) {
	const data = payload.value
	if (!data?.delivery_origin) return false
	if (event.origin !== data.delivery_origin) return false
	// Not just the origin: this exact frame. Another frame on the delivery
	// origin must not be able to speak for the package we launched.
	return !!frame.value && event.source === frame.value.contentWindow
}

async function onMessage(event) {
	if (!isOurs(event)) return
	const message = event.data || {}
	if (message.type !== 'scorm:commit') return

	let result = { ok: false }
	try {
		result = await commit.submit({
			token: payload.value.token,
			sco: message.sco,
			data: JSON.stringify(message.data || {}),
		})
	} catch (e) {
		result = { ok: false, error: '101' }
	}

	// Answer into the same frame, at the origin it came from -- never '*'.
	if (message.id && frame.value?.contentWindow) {
		frame.value.contentWindow.postMessage(
			{ type: 'scorm:commit:result', id: message.id, ok: !!result?.ok, error: result?.error },
			payload.value.delivery_origin
		)
	}
}

const commit = createResource({
	url: 'seminary.scorm.runtime.commit',
})

const renew = createResource({
	url: 'seminary.scorm.launch.heartbeat',
})

const finish = createResource({
	url: 'seminary.scorm.launch.end',
})

function startHeartbeat(data) {
	// Half the TTL, so one missed beat is not a dead launch mid-lecture.
	const ttl = Math.max(60, (data.token_ttl || 28800) / 2)
	heartbeat = window.setInterval(() => {
		renew.submit({ token: data.token }).catch(() => {})
	}, ttl * 1000)
}

onMounted(() => {
	window.addEventListener('message', onMessage)
})

onBeforeUnmount(() => {
	window.removeEventListener('message', onMessage)
	if (heartbeat) window.clearInterval(heartbeat)
	if (payload.value?.token) {
		// Best effort; the TTL is the real bound.
		finish.submit({ token: payload.value.token }).catch(() => {})
	}
})
</script>

<style scoped>
.scorm-stage {
	position: relative;
	width: 100%;
	/* Courseware is authored for a landscape stage; 16:10 fits the common
	   Storyline and Rise defaults without letterboxing either badly. */
	aspect-ratio: 16 / 10;
	min-height: 420px;
	background: #fff;
	border: 1px solid var(--surface-gray-3, #e5e7eb);
	border-radius: 0.5rem;
	overflow: hidden;
}

.scorm-frame {
	width: 100%;
	height: 100%;
	border: 0;
	display: block;
}

.scorm-badge {
	position: absolute;
	top: 0.5rem;
	right: 0.5rem;
	font-size: 0.75rem;
	padding: 0.125rem 0.5rem;
	border-radius: 9999px;
	background: rgba(0, 0, 0, 0.6);
	color: #fff;
}

.scorm-note {
	padding: 2rem 1rem;
	font-size: 0.875rem;
	color: var(--ink-gray-6, #4b5563);
}
</style>
