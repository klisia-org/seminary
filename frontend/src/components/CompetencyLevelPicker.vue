<template>
	<div class="flex flex-wrap gap-2" role="radiogroup" :aria-label="label">
		<button v-for="lv in levels" :key="lv.grade_code" type="button" role="radio"
			:aria-checked="modelValue === lv.grade_code"
			class="relative min-w-10 rounded-md border px-3 py-1.5 text-sm transition-colors"
			:class="modelValue === lv.grade_code
				? 'border-outline-gray-4 bg-surface-gray-4 font-medium text-ink-gray-9'
				: 'border-outline-gray-2 text-ink-gray-6 hover:bg-surface-gray-2'"
			:disabled="disabled" @click="emit('update:modelValue', lv.grade_code)">
			{{ lv.grade_code }}
			<!-- Where someone else placed this student, marked on the level
			     itself so the two views read as one scale. -->
			<span v-if="marksAt(lv.grade_code).length"
				class="absolute -right-2 -top-2 flex -space-x-1">
				<Tooltip v-for="m in marksAt(lv.grade_code)" :key="m.key" :text="m.label">
					<span class="flex size-5 items-center justify-center rounded-full border border-surface-white text-[10px] font-semibold"
						:class="m.tone === 'self'
							? 'bg-surface-amber-2 text-ink-amber-3'
							: 'bg-surface-blue-2 text-ink-blue-3'">
						{{ initials(m.label) }}
					</span>
				</Tooltip>
			</span>
		</button>
	</div>
</template>

<script setup>
import { Tooltip } from 'frappe-ui'

// One row of level buttons for one dimension, shared by the student's
// self-assessment and the mentor's assessment so both read the scale the same
// way (ADR 079 decision 6). `marks` are other people's levels on the same
// dimension: [{ key, label, level_code, tone: 'mentor' | 'self' }].
const props = defineProps({
	levels: { type: Array, default: () => [] },
	modelValue: { type: String, default: null },
	disabled: { type: Boolean, default: false },
	label: { type: String, default: '' },
	marks: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const marksAt = (code) => props.marks.filter((m) => m.level_code === code)

const initials = (name) =>
	(name || '?')
		.split(/\s+/)
		.filter(Boolean)
		.slice(0, 2)
		.map((w) => w[0].toUpperCase())
		.join('')
</script>
