<!-- components/RichTextInput.vue -->
<template>
    <QuillEditor ref="quillRef" :content="initialContent" content-type="html" :placeholder="placeholder" theme="snow"
        :toolbar="toolbar" @text-change="handleChange" style="min-height: 7rem;" />
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { QuillEditor } from '@vueup/vue-quill'
import '@vueup/vue-quill/dist/vue-quill.snow.css'

const props = defineProps({
    content: { type: String, default: '' },
    placeholder: { type: String, default: '' },
})

const emit = defineEmits(['change'])

// Only set once — never update from parent
const initialContent = ref('')
const quillRef = ref(null)
let debounceTimer = null

const toolbar = [
    ['bold', 'italic', 'underline'],
    [{ list: 'ordered' }, { list: 'bullet' }],
    ['link'],
    ['clean']
]

onMounted(() => {
    initialContent.value = props.content || ''
})

function handleChange() {
    clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
        const html = quillRef.value?.getHTML()
        if (html !== undefined) {
            console.log
        }
    }, 300)
}
</script>
