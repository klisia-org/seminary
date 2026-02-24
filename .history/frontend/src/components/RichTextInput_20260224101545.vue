<!-- RichTextInput.vue -->
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
    id: { type: String, required: true },
    editable: { type: Boolean, default: true },
})

const emit = defineEmits(['change'])

const editorDiv = ref(null)
let quill = null
let debounceTimer = null

onMounted(() => {
    quill = new Quill(editorDiv.value, {
        theme: 'snow',
        placeholder: props.placeholder,
        readOnly: !props.editable,
        modules: {
            toolbar: props.editable
                ? [
                ['bold', 'italic'],
                [{ list: 'ordered' }, { list: 'bullet' }],
                ['blockquote'],
                ['link']
            ]
                : false,
        }
    })

    if (props.content) {
        quill.root.innerHTML = props.content
    }

    quill.on('text-change', () => {
        clearTimeout(debounceTimer)
        debounceTimer = setTimeout(() => {
            emit('change', quill.root.innerHTML)
        }, 500)
    })
})

function clear() {
    if (quill) {
        quill.root.innerHTML = ''
    }
}

onBeforeUnmount(() => {
    clearTimeout(debounceTimer)
    quill = null
})

defineExpose({ clear })
</script>
