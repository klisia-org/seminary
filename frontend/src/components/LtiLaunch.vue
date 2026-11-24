<!--
  An LTI lesson's launch (decisions/110 §3).

  The server authorises the launch and returns the tool's login URL; the tool
  sends the browser back to this site, which posts the signed launch to the
  tool. "New window" opens it in a tab. "Embedded" frames it here, and gives a
  way out to a tab for tools that refuse to be framed.

  The window is opened before the request returns, from the click itself:
  a window opened after an await is a popup, and browsers block it.
-->
<template>
	<div v-if="info.data?.lti" class="rounded-lg border border-outline-gray-2 bg-surface-gray-1 p-4">
		<div class="flex flex-wrap items-center justify-between gap-3">
			<div class="min-w-0">
				<div class="flex items-center gap-2 font-medium text-ink-gray-9">
					<ExternalLink class="h-4 w-4 shrink-0" aria-hidden="true" />
					{{ info.data.tool_name }}
				</div>
				<p v-if="info.data.description" class="mt-1 text-sm text-ink-gray-6">
					{{ info.data.description }}
				</p>
			</div>
			<Button
				v-if="info.data.may_launch && info.data.available"
				variant="solid"
				:loading="launching"
				@click="launch(false)"
			>
				{{ __('Open {0}').format(info.data.tool_name) }}
			</Button>
		</div>
		<p v-if="!info.data.available" class="mt-2 text-sm text-ink-gray-6">
			{{ __('This tool is not available right now. Ask your school if it should be.') }}
		</p>
		<p v-else-if="!info.data.may_launch" class="mt-2 text-sm text-ink-gray-6">
			{{ __("Only the section's students and teaching staff can open this tool.") }}
		</p>
		<p v-if="error" role="alert" class="mt-2 text-sm text-ink-red-4">{{ error }}</p>
		<div v-if="frameUrl" class="mt-4">
			<iframe
				:src="frameUrl"
				:title="info.data.tool_name"
				class="h-[70vh] w-full rounded-md border border-outline-gray-2 bg-surface-white"
				allow="fullscreen; clipboard-write; microphone; camera"
			></iframe>
			<Button class="mt-2" variant="ghost" @click="launch(true)">
				{{ __('Open in a new window instead') }}
			</Button>
		</div>
	</div>
</template>

<script setup>
import { ref } from 'vue'
import { Button, createResource } from 'frappe-ui'
import { ExternalLink } from 'lucide-vue-next'

const props = defineProps({
	lesson: { type: String, required: true },
})

const launching = ref(false)
const error = ref('')
const frameUrl = ref('')

const info = createResource({
	url: 'seminary.lti.launch.lesson_launch_info',
	makeParams() {
		return { lesson: props.lesson }
	},
	auto: true,
})

const start = createResource({ url: 'seminary.lti.launch.start' })

async function launch(forceWindow) {
	error.value = ''
	const embedded = !forceWindow && info.data?.presentation === 'iframe'
	const win = embedded ? null : window.open('', '_blank')
	launching.value = true
	try {
		const data = await start.submit({ lesson: props.lesson })
		if (embedded) {
			frameUrl.value = data.url
		} else if (win) {
			win.opener = null
			win.location = data.url
			frameUrl.value = ''
		} else {
			window.location.assign(data.url)
		}
	} catch (e) {
		win?.close()
		error.value = e?.messages?.[0] || __('The tool could not be opened.')
	} finally {
		launching.value = false
	}
}
</script>
