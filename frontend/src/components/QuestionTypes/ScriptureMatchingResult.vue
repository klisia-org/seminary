<template>
    <div class="space-y-3 my-2">
        <div
            v-for="(slot, slotIdx) in slots"
            :key="slotIdx"
            class="border rounded-md p-3"
            :class="slot.correct ? 'bg-surface-green-1 border-ink-green-2' : 'bg-surface-red-1 border-ink-red-2'"
        >
            <div class="text-sm text-ink-gray-9 leading-snug mb-2">
                {{ slot.text }}
            </div>
            <div class="flex items-center gap-2 text-sm">
                <span class="text-ink-gray-6">{{ __('Your match:') }}</span>
                <span
                    class="px-2 py-1 rounded font-semibold bg-surface-white"
                    :class="slot.correct ? 'text-ink-green-3' : 'text-ink-red-3'"
                >
                    {{ slot.studentRef || __('(no match)') }}
                </span>
                <CheckCircle v-if="slot.correct" class="w-4 h-4 text-ink-green-3" />
                <XCircle v-else class="w-4 h-4 text-ink-red-3" />
            </div>
            <div v-if="!slot.correct" class="text-sm mt-1">
                <span class="text-ink-gray-6">{{ __('Correct:') }}</span>
                <span class="ml-1 font-semibold px-2 py-0.5 rounded bg-surface-white text-ink-green-3">
                    {{ slot.correctRef }}
                </span>
            </div>
        </div>
    </div>
</template>

<script setup>
import { computed } from 'vue'
import { CheckCircle, XCircle } from 'lucide-vue-next'

const props = defineProps({
    // Original prof-defined pairs: [{reference, fetched_text, ...}, ...]
    items: { type: Array, required: true },
    // Student payload (JSON string from result.answer):
    //   [{ref_idx, text_orig_idx, matched_text}, ...] in shuffled display order
    userAnswer: { type: String, default: '' },
})

const parsed = computed(() => {
    if (!props.userAnswer) return []
    try {
        const v = JSON.parse(props.userAnswer)
        return Array.isArray(v) ? v : []
    } catch {
        return []
    }
})

// Render slots in the student's original display order so they recognise the test.
const slots = computed(() => {
    const items = props.items || []
    return parsed.value.map((entry) => {
        const textOrigIdx = entry?.text_orig_idx
        const refIdx = entry?.ref_idx
        const correctRow = typeof textOrigIdx === 'number' ? items[textOrigIdx] : null
        const studentRow = typeof refIdx === 'number' ? items[refIdx] : null
        const text =
            entry?.matched_text || (correctRow ? correctRow.fetched_text : '')
        const correct =
            refIdx !== null &&
            refIdx !== undefined &&
            textOrigIdx !== null &&
            textOrigIdx !== undefined &&
            Number(refIdx) === Number(textOrigIdx)
        return {
            text,
            studentRef: studentRow ? studentRow.reference : '',
            correctRef: correctRow ? correctRow.reference : '',
            correct,
        }
    })
})
</script>
