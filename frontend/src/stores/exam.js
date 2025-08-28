import { reactive } from 'vue'

export const examStore = reactive({
  prefillData: {
    title: '',
    course: ''
  },
  setPrefillData(data) {
    this.prefillData = { ...data }
  },
  clearPrefillData() {
    this.prefillData = { title: '', course: '' }
  }
})
console.log(examStore.prefillData)