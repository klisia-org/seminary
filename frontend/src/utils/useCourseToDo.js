// utils/useCourseToDo.js
import { createResource } from 'frappe-ui'
import { computed } from 'vue'

export function useCourseToDo(courseName, user) {
 
  const isStudent =  user?.data?.is_student
  const isInstructor =  user?.data?.is_instructor
    console.log("useCourseToDo", courseName, user?.data?.name, isStudent, isInstructor)
  const course = createResource({
    url: 'seminary.seminary.utils.get_course_details',
    cache: ['course', courseName],
    params: { course: courseName },
    auto: true,
  })

  const assessments = createResource({
    url: 'seminary.seminary.utils.get_assessments',
    cache: ['assessments', courseName],
    params: { course: courseName },
  })

  const missingAssessments = createResource({
    url: 'seminary.seminary.utils.get_missingassessments',
    cache: ['missingassessments', courseName],
    params: {
      course: courseName,
      member: user?.data?.name,
    },
  })

  const assessmentsToGrade = createResource({
    url: 'seminary.seminary.utils.get_assessments_tograde',
    cache: ['assessments_tograde', courseName],
    params: { course: courseName },
  })

  
  const countToDoItems = computed(() => {
    const countMissing = missingAssessments.data?.length || 0
    const countDueSoon = (assessments.data || []).filter(a => new Date(a.due_date) >= new Date()).length
    const countToGrade = assessmentsToGrade.data?.length || 0
    if (isStudent) {
      return countMissing + countDueSoon
    }
    if (isInstructor) {
      return countToGrade
    } 
  })
  console.log("Course: ", courseName, 'countToDoItems', countToDoItems.value)
  return {
    course,
    assessments,
    missingAssessments,
    assessmentsToGrade,
    isStudent,
    isInstructor,
    countToDoItems,
  }
}
