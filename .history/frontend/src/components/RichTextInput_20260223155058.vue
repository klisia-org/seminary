<!-- components/RichTextInput.vue -->
<template>
    <QuillEditor
        v-model:content="localContent"
        content-type="html"
        :placeholder="placeholder"
        theme="snow"
        :toolbar="toolbar"
        @update:content="handleChange"
        style="min-height: 7rem;"
    />
</template>

<script setup>
import { ref, watch } from 'vue'
import { QuillEditor } from '@vueup/vue-quill'
import '@vueup/vue-quill/dist/vue-quill.snow.css'

const props = defineProps({
    content: { type: String, default: '' },
    placeholder: { type: String, default: '' },
})

const emit = defineEmits(['change'])

const localContent = ref(props.content || '')
let initialized = false

const toolbar = [
    ['bold', 'italic', 'underline'],
    [{ list: 'ordered' }, { list: 'bullet' }],
    ['link'],
    ['clean']
]

watch(() => props.content, (val) => {
    if (val !== localContent.value) {
        localContent.value = val
    }
})

function handleChange() {
    if (!initialized) {
        initialized = true
        return
    }
    emit('change', localContent.value)
}
</script>
