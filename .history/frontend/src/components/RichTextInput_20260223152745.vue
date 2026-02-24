<template>
    <TextEditor
        v-if="ready"
        :content="localContent"
        @change="handleChange"
        :placeholder="placeholder"
        :editable="true"
        :bubble-menu="true"
        :editor-class="editorClass"
    />
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { TextEditor } from 'frappe-ui'

const props = defineProps({
    content: {
        type: String,
        default: ''
    },
    placeholder: {
        type: String,
        default: ''
    },
    editorClass: {
        type: String,
        default: 'prose-sm min-h-[7rem]'
    }
})

const emit = defineEmits(['change'])

const localContent = ref(props.content || '')
const ready = ref(false)
let initialized = false

onMounted(() => {
    ready.value = true
})

function handleChange(val) {
    // Skip the initial @change fired on mount
    if (!initialized) {
        initialized = true
        return
    }

    // Skip if content hasn't actually changed
    if (val === localContent.value) return

    localContent.value = val
    emit('change', val)
}
</script>
