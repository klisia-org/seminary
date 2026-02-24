<!-- components/RichTextInput.vue -->
<template>
    <div>
        <div ref="editorDiv"></div>
    </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import Quill from 'quill'
import 'quill/dist/quill.snow.css'

const props = defineProps({
    content: { type: String, default: '' },
    placeholder: { type: String, default: '' },
})

const emit = defineEmits(['change'])

const editorDiv = ref(null)
let quill = null
let debounceTimer = null

onMounted(() => {
    quill = new Quill(editorDiv.value, {
        theme: 'snow',
        placeholder: props.placeholder,
        modules: {
            toolbar: [
                ['bold', 'italic'],
                [{ list: 'ordered' }, { list: 'bullet' }],
            ]
        }
    })

    if (props.content) {
        quill.root.innerHTML = props.content
    }

    quill.on('text-change', () => {
        console.log('typed')
        // Don't emit anything
    })
})

onBeforeUnmount(() => {
    clearTimeout(debounceTimer)
    quill = null
})
</script>
