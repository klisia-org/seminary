<!--
	The only component allowed to use v-html (p008 F1; enforced by
	seminary/seminary/tests/test_p008_frontend_sinks.py).

	<SafeHtml :html="doc.description" class="prose-sm" />
	<SafeHtml as="span" profile="inline" :html="row.comments" />

	Attributes (class, id, title...) fall through to the wrapper element. Keep a
	v-if on the <SafeHtml> tag itself. Profiles: see utils/sanitize.js.
-->
<template>
	<component :is="as" v-html="clean" />
</template>

<script setup>
import { computed } from 'vue'
import { sanitize } from '@/utils/sanitize'

const props = defineProps({
	html: { type: [String, Number, null], default: '' },
	profile: { type: String, default: 'rich' },
	as: { type: String, default: 'div' },
})

const clean = computed(() => sanitize(props.html, props.profile))
</script>
