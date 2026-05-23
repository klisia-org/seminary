<template>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 my-3">
        <!-- LEFT: source references (drag from here, click to select) -->
        <div>
            <div class="text-sm font-semibold text-ink-gray-7 mb-2">
                {{ __('References') }}
            </div>
            <VueDraggable
                v-model="sourceRefs"
                :group="dragGroup"
                :sort="false"
                :disabled="readOnly"
                :animation="150"
                class="space-y-2 min-h-[3rem]"
            >
                <div
                    v-for="element in sourceRefs"
                    :key="element.idx"
                    class="ref-card p-3 rounded-md border bg-surface-white cursor-grab select-none"
                    :class="{
                        'ring-2 ring-blue-500': selectedRefIdx === element.idx,
                        'cursor-not-allowed': readOnly,
                    }"
                    @click="onClickRef(element.idx)"
                >
                    {{ element.label }}
                </div>
            </VueDraggable>
            <div
                v-if="sourceRefs.length === 0"
                class="text-xs text-ink-gray-5 italic mt-2"
            >
                {{ __('All references placed.') }}
            </div>
        </div>

        <!-- RIGHT: passage slots (drop here) -->
        <div class="space-y-3">
            <div
                v-for="(slot, slotIdx) in slots"
                :key="slotIdx"
                class="border rounded-md p-3 bg-surface-gray-2"
                @click="onClickSlot(slotIdx)"
            >
                <div class="text-sm text-ink-gray-9 leading-snug mb-2">
                    {{ shuffledTexts[slotIdx]?.text }}
                </div>
                <VueDraggable
                    v-model="slots[slotIdx]"
                    :group="dragGroup"
                    :disabled="readOnly"
                    :animation="150"
                    @change="(e) => onSlotChange(slotIdx, e)"
                    class="min-h-[2.5rem] border-2 border-dashed border-outline-gray-2 rounded-md p-2 bg-surface-white"
                >
                    <div
                        v-for="element in slot"
                        :key="element.idx"
                        class="placed-ref p-2 bg-surface-amber-2 rounded text-sm cursor-grab select-none"
                    >
                        {{ element.label }}
                    </div>
                </VueDraggable>
                <div
                    v-if="slot.length === 0"
                    class="text-xs text-ink-gray-5 italic mt-1 pl-2 pointer-events-none -mt-7 relative z-0"
                >
                    {{ __('Drop the reference here') }}
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import { shuffle } from '@/utils/scripture'

const props = defineProps({
    items: { type: Array, required: true }, // [{reference, fetched_text, ...}]
    readOnly: { type: Boolean, default: false },
})
const emit = defineEmits(['update:answer'])

const dragGroup = { name: 'matching-' + Math.random().toString(36).slice(2, 8) }

// Build the reference pool (each card carries its original index)
const allRefs = computed(() =>
    (props.items || []).map((it, idx) => ({ idx, label: it.reference }))
)
const sourceRefs = ref([])
const slots = ref([]) // array of arrays (0 or 1 item per slot)
const shuffledTexts = ref([]) // shuffled fetched_text cards aligned with slots
const selectedRefIdx = ref(null)

const initState = () => {
    sourceRefs.value = [...allRefs.value]
    slots.value = (props.items || []).map(() => [])
    shuffledTexts.value = shuffle(
        (props.items || []).map((it, idx) => ({
            origIdx: idx,
            text: it.fetched_text,
        }))
    )
    selectedRefIdx.value = null
    emitAnswer()
}

onMounted(initState)
watch(
    () => props.items,
    () => initState(),
    { deep: false }
)

// Deep watch the slots array and re-emit after Vue's DOM updates settle.
// vue-draggable-plus's @change can fire mid-transition during swap drops,
// causing emitAnswer to snapshot stale state (one slot apparently empty).
// flush: 'post' guarantees we read the settled array.
watch(slots, () => emitAnswer(), { deep: true, flush: 'post' })

const onSlotChange = (slotIdx, event) => {
    // 1) Cap this slot at 1: kick any overflow back to source.
    const slot = slots.value[slotIdx]
    if (slot.length > 1) {
        const overflow = slot.splice(0, slot.length - 1) // keep last (newest drop)
        overflow.forEach((r) => {
            if (!sourceRefs.value.some((s) => s.idx === r.idx)) {
                sourceRefs.value.push(r)
            }
        })
    }
    // 2) Enforce one-to-one across slots: if this slot's ref also lives in
    //    another slot (can happen during fast swap drops), remove it there.
    if (slot.length === 1) {
        const myRefIdx = slot[0].idx
        slots.value.forEach((other, oi) => {
            if (oi !== slotIdx) {
                const i = other.findIndex((r) => r.idx === myRefIdx)
                if (i >= 0) other.splice(i, 1)
            }
        })
    }
}

const onClickRef = (refIdx) => {
    if (props.readOnly) return
    selectedRefIdx.value = selectedRefIdx.value === refIdx ? null : refIdx
}

const onClickSlot = (slotIdx) => {
    if (props.readOnly || selectedRefIdx.value === null) return
    // If clicking the slot the ref is already in: no-op
    const current = slots.value[slotIdx][0]
    if (current && current.idx === selectedRefIdx.value) {
        selectedRefIdx.value = null
        return
    }
    // Pull the selected ref from wherever it is (source or another slot)
    const refObj = allRefs.value.find((r) => r.idx === selectedRefIdx.value)
    if (!refObj) return
    const srcI = sourceRefs.value.findIndex((r) => r.idx === refObj.idx)
    if (srcI >= 0) sourceRefs.value.splice(srcI, 1)
    slots.value.forEach((s, oi) => {
        if (oi !== slotIdx) {
            const i = s.findIndex((r) => r.idx === refObj.idx)
            if (i >= 0) s.splice(i, 1)
        }
    })
    // If target slot already had a ref, send it back to source
    if (current) {
        slots.value[slotIdx] = []
        if (!sourceRefs.value.some((s) => s.idx === current.idx)) {
            sourceRefs.value.push(current)
        }
    }
    slots.value[slotIdx] = [refObj]
    selectedRefIdx.value = null
    emitAnswer()
}

const emitAnswer = () => {
    const payload = slots.value.map((s, slotIdx) => ({
        ref_idx: s.length ? s[0].idx : null,
        text_orig_idx: shuffledTexts.value[slotIdx]?.origIdx,
        matched_text: shuffledTexts.value[slotIdx]?.text || '',
    }))
    emit('update:answer', payload)
}
</script>
