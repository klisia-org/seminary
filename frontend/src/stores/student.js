import { defineStore } from 'pinia'
import { ref, inject } from 'vue'
import { createResource } from 'frappe-ui'

// Get user data to check if user is a student
const user = inject('$user')

export const studentStore = user.data.is_student ? defineStore('seminary-student', () => {
  const studentInfo = ref({})
  const currentProgram = ref({})

  const student = createResource({
    url: 'seminary.seminary.api.get_student_info',
    onSuccess(student_info) {
      currentProgram.value = student_info.current_program
      // remove current_program from info
      delete student_info.current_program
      studentInfo.value = student_info
      console.log('Student Info:', student_info)
    },
    onError(err) {
      console.error('Error fetching student info:', err)
    },
    auto: true, // Automatically fetch the resource
  })

  function getStudentInfo() {
    return studentInfo
  }

  function getCurrentProgram() {
    return currentProgram
  }

  return { student, studentInfo, currentProgram, getStudentInfo, getCurrentProgram }
}) : null