<template>
    <div class="my-3">
        <!-- flex+gap reliably preserves token spacing; v-for'd whitespace in
             Vue templates gets collapsed and renders as one big word. -->
        <div class="flex flex-wrap items-baseline gap-x-1.5 gap-y-2 text-ink-gray-9">
            <template v-for="(tok, idx) in tokens" :key="idx">
                <input
                    v-if="hiddenSet.has(idx)"
                    :value="filled[blankIndexOf(idx)]"
                    @input="(e) => onInput(blankIndexOf(idx), e.target.value)"
                    :disabled="readOnly"
                    type="text"
                    :size="Math.max(tok.replace(STRIP_NON_ALNUM, '').length, 4)"
                    class="bg-surface-amber-2 border-b-2 border-ink-amber-3 px-1 rounded-sm text-center focus:outline-none focus:border-ink-amber-4"
                />
                <span v-else>{{ tok }}</span>
            </template>
        </div>
        <div class="text-xs text-ink-gray-5 mt-3 italic">
            {{ __('Reference: {0}', [referenceLabel]) }} —
            {{ __('{0} blank(s) to fill', [hidden.length]) }}
        </div>
    </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { pickBlankPositions } from '@/utils/scripture'

const STRIP_NON_ALNUM = /[^\p{L}\p{N}]+/gu

const props = defineProps({
    text: { type: String, required: true },
    hideCount: { type: Number, default: 3 },
    minWordLength: { type: Number, default: 4 },
    referenceLabel: { type: String, default: '' },
    readOnly: { type: Boolean, default: false },
})
const emit = defineEmits(['update:answer'])

const tokens = computed(() => (props.text || '').split(/\s+/).filter(Boolean))
const hidden = ref([]) // sorted array of token indices that are hidden
const hiddenSet = computed(() => new Set(hidden.value))
const filled = ref([]) // student-typed words, aligned with hidden

const blankIndexOf = (tokenIdx) => hidden.value.indexOf(tokenIdx)

const onInput = (blankIdx, value) => {
    filled.value[blankIdx] = value
    emit('update:answer', { positions: [...hidden.value], words: [...filled.value] })
}

onMounted(() => {
    hidden.value = pickBlankPositions(
        props.text || '',
        Math.max(1, props.hideCount || 1),
        Math.max(1, props.minWordLength || 4)
    )
    filled.value = hidden.value.map(() => '')
    emit('update:answer', { positions: [...hidden.value], words: [...filled.value] })
})
</script>
