<!-- RichTextInput.vue — updated -->
<template>
    <div ref="wrapper">
        <TextEditor v-if="mounted" :content="localContent" @change="handleChange" :placeholder="placeholder"
            :editable="true" :bubble-menu="true" :editor-class="editorClass" />
    </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
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

const localContent = ref('')
const mounted = ref(false)
let initialized = false

onMounted(async () => {
    // Set content before mounting TextEditor
    localContent.value = props.content || ''

    // Wait two ticks to ensure DOM is stable
    await nextTick()
    await nextTick()

    mounted.value = true
})

function handleChange(val) {
    if (!initialized) {
        initialized = true
        return
    }
    if (val === localContent.value) return
    localContent.value = val
    emit('change', val)
}
</script>
