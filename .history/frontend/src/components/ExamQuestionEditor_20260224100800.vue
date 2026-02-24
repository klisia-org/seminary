<template>
  <RichTextInput
    :content="internalContent"
    :key="questionId"
    :editable="editable"
    :fixedMenu="true"
    :label="`Comment for Question ${questionId}`"
  
  />
</template>

<script setup>
import { ref, watch } from 'vue'
import RichTextInput from '@/components/RichTextInput.vue'


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