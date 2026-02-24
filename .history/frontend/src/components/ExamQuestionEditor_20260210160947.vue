<template>
  <TextEditor
    :content="internalContent"
    :key="questionId"
    :editable="editable"
    :fixedMenu="true"
    :label="`Comment for Question ${questionId}`"
    :editorClass="'ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none'"
    @change="updateContent"
  />
</template>

<script setup>
import { ref, watch } from 'vue'
import { TextEditor } from 'frappe-ui'


const props = defineProps({
  questionId: {
    type: String,
    required: true,
  },

  content: {
    type: String,
    default: '',
  },
  editable: {
    type: Boolean,
    default: true,
  }
})

const emit = defineEmits(['change'])
console.log('Props:', props)
// Hold the editor content as a reactive string. This will be used by the TextEditor.
const internalContent = ref(props.content)

// Watch for changes to the content prop and update internalContent accordingly.
watch(() => props.content, (newContent, oldContent) => {
  if (newContent !== oldContent) {
    internalContent.value = newContent
  }
})

const updateContent = (val) => {
  internalContent.value = val
  emit('change', val)
}
</script>