<template>
    <div class="space-y-3 my-2">
        <!-- Your answer: full verse, with student's words in the blanks coloured by correctness -->
        <div class="border rounded-md p-3 bg-surface-gray-2">
            <div class="text-xs text-ink-gray-6 mb-2 font-semibold">
                {{ __('Your answer') }}
            </div>
            <div class="flex flex-wrap items-baseline gap-x-1.5 gap-y-1 text-ink-gray-9">
                <template v-for="(tok, idx) in tokens" :key="idx">
                    <span
                        v-if="blankAt(idx)"
                        class="px-2 py-0.5 rounded font-semibold"
                        :class="blankAt(idx).correct
                            ? 'bg-surface-green-1 text-ink-green-3'
                            : 'bg-surface-red-1 text-ink-red-3'"
                    >
                        {{ blankAt(idx).typed || __('(blank)') }}
                    </span>
                    <span v-else>{{ tok }}</span>
                </template>
            </div>
        </div>
        <!-- Correct version: same verse, with the originally-hidden words highlighted green -->
        <div class="border rounded-md p-3 bg-surface-gray-2">
            <div class="text-xs text-ink-gray-6 mb-2 font-semibold">
                {{ __('Correct') }}
            </div>
            <div class="flex flex-wrap items-baseline gap-x-1.5 gap-y-1 text-ink-gray-9">
                <template v-for="(tok, idx) in tokens" :key="idx">
                    <span
                        v-if="hiddenSet.has(idx)"
                        class="px-2 py-0.5 rounded font-semibold bg-surface-green-1 text-ink-green-3"
                    >
                        {{ tok }}
                    </span>
                    <span v-else>{{ tok }}</span>
                </template>
            </div>
        </div>
    </div>
</template>

<script setup>
import { computed } from 'vue'

const STRIP = /[^\p{L}\p{N}]+/gu
const norm = (s) => String(s || '').replace(STRIP, '').toLowerCase()

const props = defineProps({
    text: { type: String, required: true },
    userAnswer: { type: String, default: '' }, // JSON {"positions","words"}
})

const parsed = computed(() => {
    if (!props.userAnswer) return { positions: [], words: [] }
    try {
        const v = JSON.parse(props.userAnswer)
        return {
            positions: Array.isArray(v?.positions) ? v.positions : [],
            words: Array.isArray(v?.words) ? v.words : [],
        }
    } catch {
        return { positions: [], words: [] }
    }
})

const tokens = computed(() => (props.text || '').split(/\s+/).filter(Boolean))
const hiddenSet = computed(() => new Set(parsed.value.positions.map(Number)))

const blankAt = (idx) => {
    const i = parsed.value.positions.findIndex((p) => Number(p) === idx)
    if (i < 0) return null
    const typed = parsed.value.words[i] || ''
    const expected = tokens.value[idx] || ''
    return { typed, correct: typed !== '' && norm(typed) === norm(expected) }
}
</script>
