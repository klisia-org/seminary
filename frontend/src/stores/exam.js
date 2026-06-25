import { reactive } from 'vue'

export const examStore = reactive({
  prefillData: {
    title: '',
    course: ''
  },
  // Set when an activity form is opened from the lesson editor's "create new"
  // flow. Tells the form where to return and which editor block type to insert.
  // { route: <vue-router location>, insertType: 'quiz'|'exam'|'assignment'|'discussionActivity' }
  returnContext: null,
  // Set by an activity form when the user clicks "Back to lesson" after saving.
  // Consumed by LessonForm to splice the new activity into the lesson content.
  // { type: <editor block type>, id: <activity name> }
  pendingInsert: null,
  setPrefillData(data) {
    this.prefillData = { ...data }
  },
  clearPrefillData() {
    this.prefillData = { title: '', course: '' }
  },
  setReturnContext(ctx) {
    this.returnContext = ctx
  },
  clearReturnContext() {
    this.returnContext = null
  },
  setPendingInsert(insert) {
    this.pendingInsert = insert
  },
  clearPendingInsert() {
    this.pendingInsert = null
  },
})
