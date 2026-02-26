<template>
  <div v-if="course.data && instructors.data">
    <header class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-white px-3 py-2.5 sm:px-5">
      <Breadcrumbs class="h-7" :items="breadcrumbs" />
    </header>
    <h1 class="text-2xl font-bold mt-4 mb-4 ml-5">
      {{ __('Student Group Management for ' + course.data.course) }}
    </h1>
    <h2 class="text-l mb-12 ml-5">
      {{ __('Student Groups are used to assign students to specific groups within the course, both for assigning' +
        ' grading to specific instructors and for organizing collaborative work.')
      }}
    </h2>
       <h3 class="text-md mb-12 ml-5">
      {{ __('If the page does not ref.')
      }}
    </h3>

    <!-- ============================================ -->
    <!-- EXISTING GROUPS VIEW (with manual adjustments) -->
    <!-- ============================================ -->
    <div v-if="hasSavedGroups" class="student-group-page">
      <div class="flex items-center justify-between mb-4 ml-5 mr-5">
        <h2 class="text-xl font-bold">Student Groups</h2>
        <div class="flex items-center gap-3">
          <Button v-if="hasUnsavedChanges" variant="solid" theme="blue" size="sm" :label="__('Save Changes')"
            :loading="isSaving" @click="saveManualChanges" />
          <Button v-if="hasUnsavedChanges" variant="outline" theme="gray" size="sm" :label="__('Discard Changes')"
            @click="discardChanges" />
          <Button variant="outline" theme="red" size="sm" :label="__('Recreate Groups')"
            @click="showRecreateConfirm = true" />
        </div>
      </div>

      <!-- Unsaved changes banner -->
      <div v-if="hasUnsavedChanges"
        class="mx-5 mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-md flex items-center gap-2">
        <span class="text-yellow-600 text-sm font-medium">
          ⚠️ You have unsaved changes. Click "Save Changes" to apply them.
        </span>
      </div>

      <!-- Unassigned Students Section -->
      <div v-if="unassignedStudents.length > 0" class="mx-5 mb-6 p-4 bg-orange-50 border border-orange-200 rounded-lg">
        <h3 class="text-md font-semibold text-orange-800 mb-3">
          ⚠️ Unassigned Students ({{ unassignedStudents.length }})
        </h3>
        <div class="space-y-2">
          <div v-for="student in unassignedStudents" :key="student.student"
            class="flex items-center justify-between bg-white p-2 rounded border border-orange-100">
            <span class="text-sm font-medium text-gray-700">
              {{ student.student_name }}
            </span>
            <div class="flex items-center gap-2">
              <FormControl type="select" :options="availableGroupOptions" :placeholder="__('Assign to group...')"
                size="sm" @change="(val) => assignStudentToGroup(student, val)" />
            </div>
          </div>
        </div>
      </div>

      <!-- Groups displayed as cards -->
      <div class="mx-5 space-y-6">
        <div v-for="(group, groupName) in groupedStudents" :key="groupName" class="border rounded-lg overflow-hidden">
          <!-- Group Header -->
          <div class="bg-surface-gray-2 px-4 py-3 flex items-center justify-between">
            <div>
              <h3 class="text-md font-semibold text-gray-800">
                {{ groupName }}
              </h3>
              <span class="text-xs text-gray-500">
                {{ group.instructor }} · {{ group.students.length }}
                {{ group.students.length === 1 ? 'student' : 'students' }}
              </span>
            </div>
          </div>

          <!-- Student List -->
          <div class="divide-y">
            <div v-for="student in group.students" :key="student.student"
              class="flex items-center justify-between px-4 py-2.5 hover:bg-gray-50 transition-colors">
              <span class="text-sm text-gray-700">
                {{ student.student_name }}
              </span>
              <div class="flex items-center gap-2">
                <!-- Move to another group -->
                <FormControl type="select" :options="getMoveOptions(groupName)" :modelValue="''"
                  :placeholder="__('Move to...')" size="sm" @change="
                    (val) => moveStudent(student, groupName, val)
                  " />
                <!-- Remove from group -->
                <Button variant="ghost" theme="red" size="sm" :label="__('Remove')"
                  @click="removeStudentFromGroup(student, groupName)" />
              </div>
            </div>
            <div v-if="group.students.length === 0" class="px-4 py-3 text-sm text-gray-400 italic">
              No students in this group
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ============================================ -->
    <!-- CREATE GROUPS VIEW (no groups exist yet) -->
    <!-- ============================================ -->
    <div v-else class="mt-8 ml-5">
      <div class="mb-4">
        <label for="groupCount" class="block text-lg font-medium text-gray-700 mb-4">
          How many student groups should be created?
        </label>
        <input id="groupCount" type="number" v-model="groupCount" :min="2" :max="course.data.enrollments"
          class="mt-1 mb-4 block w-full border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
      </div>

      <!-- Instructor selection -->
      <div v-if="hasInstructors" class="mb-4">
        <p class="text-lg font-medium text-gray-700 mb-2">
          Please, select the instructor for each group:
        </p>
        <div v-for="(group, index) in groupCount" :key="index" class="mb-2">
          <label :for="`instructor-${index}`" class="block text-sm font-medium text-gray-700">
            Group {{ index + 1 }} Instructor
          </label>
          <FormControl v-model="selectedInstructors[index]" :label="__('Instructor')" type="select"
            :options="instructorOptions" />
        </div>
      </div>
      <div v-else class="mb-4">
        <p class="text-lg font-medium text-gray-700 mb-2">
          Only one instructor is assigned to this course. Student groups will be
          created with instructor:
          {{ instructors.data[0].instructor_name }}
        </p>
      </div>

      <!-- Create Groups Button -->
      <Button variant="solid" theme="gray" size="sm" :label="__('Create Groups')" :loading="false" @click="createGroups"
        :disabled="!canCreateGroups" />
    </div>

    <!-- ============================================ -->
    <!-- Recreate Confirmation Dialog -->
    <!-- ============================================ -->
    <Dialog v-model="showRecreateConfirm" :options="{
      title: __('Recreate Student Groups'),
      message: __(
        'This will delete all existing groups and allow you to create new ones. This action cannot be undone. Are you sure?'
      ),
      actions: [
        {
          label: __('Cancel'),
          variant: 'outline',
          onClick: () => (showRecreateConfirm = false),
        },
        {
          label: __('Delete & Recreate'),
          variant: 'solid',
          theme: 'red',
          onClick: recreateGroups,
        },
      ],
    }" />
  </div>
</template>

<script setup>
import { ref, computed, inject, watch, reactive } from 'vue'
import {
  createResource,
  Breadcrumbs,
  ListView,
  ListHeader,
  ListHeaderItem,
  ListRows,
  ListRow,
  ListRowItem,
  FormControl,
  Button,
  Dialog,
} from 'frappe-ui'
import { useRouter, useRoute } from 'vue-router'
import { updateDocumentTitle } from '@/utils'

const router = useRouter()
const route = useRoute()
const user = inject('$user')

const props = defineProps({
  courseName: {
    type: String,
    required: true,
  },
})

// ============================================
// Resources
// ============================================

const instructors = createResource({
  url: 'seminary.seminary.utils.get_instructors',
  params: { course: props.courseName },
  auto: true,
})

const course = createResource({
  url: 'seminary.seminary.utils.get_course_details',
  cache: ['course', props.courseName],
  params: { course: props.courseName },
  auto: true,
})

const saved_groups = createResource({
  url: 'seminary.seminary.utils.get_student_groups',
  cache: ['saved_groups', props.courseName],
  params: { course: props.courseName },
  auto: true,
})

const students = createResource({
  url: 'seminary.seminary.utils.get_roster',
  cache: ['roster', props.courseName],
  params: { course: props.courseName },
  auto: true,
})

// ============================================
// Computed properties
// ============================================

const hasInstructors = computed(
  () => instructors.data && instructors.data.length > 1
)
const hasSavedGroups = computed(
  () => saved_groups.data && saved_groups.data.length > 0
)

const breadcrumbs = computed(() => {
  let items = [{ label: __('Courses'), route: { name: 'Courses' } }]
  items.push({
    label: course?.data?.course,
    route: {
      name: 'CourseDetail',
      params: { courseName: props.courseName },
    },
  })
  items.push({
    label: __('Configure Student Groups'),
    route: {
      name: 'StudentGroup',
      params: { courseName: props.courseName },
    },
  })
  return items
})

const pageMeta = computed(() => ({
  title: course?.data?.title,
  description: __('Configuration of Student Groups for the course'),
}))
updateDocumentTitle(pageMeta)

const instructorOptions = computed(() => {
  if (Array.isArray(instructors.data)) {
    return instructors.data.map((instructor) => ({
      label: instructor.instructor_name,
      value: instructor.user,
    }))
  }
  return Object.values(instructors.data || {}).map((instructor) => ({
    label: instructor.instructor_name,
    value: instructor.user,
  }))
})

const canCreateGroups = computed(() => {
  return (
    groupCount.value > 1 &&
    groupCount.value <= course.data.enrollments &&
    ((hasInstructors.value &&
      selectedInstructors.value.length === groupCount.value) ||
      !hasInstructors.value)
  )
})

// ============================================
// Manual adjustment state
// ============================================

const groupCount = ref(2)
const selectedInstructors = ref([])
const showRecreateConfirm = ref(false)
const isSaving = ref(false)

// This holds the working copy of group assignments for manual edits
// Structure: array of { student, student_name, student_group, group_instructor }
const editableGroups = ref([])

// Snapshot of original data to detect changes
const originalGroupsSnapshot = ref('')

// Initialize editable groups when saved_groups loads
watch(
  () => saved_groups.data,
  (newData) => {
    if (newData && newData.length > 0) {
      editableGroups.value = JSON.parse(JSON.stringify(newData))
      originalGroupsSnapshot.value = JSON.stringify(newData)
    }
  },
  { immediate: true }
)

const hasUnsavedChanges = computed(() => {
  if (!editableGroups.value.length) return false
  return JSON.stringify(editableGroups.value) !== originalGroupsSnapshot.value
})

// Group the editable data by student_group for card display
const groupedStudents = computed(() => {
  const groups = {}
  editableGroups.value.forEach((row) => {
    if (row.student_group) {
      if (!groups[row.student_group]) {
        groups[row.student_group] = {
          instructor: row.group_instructor,
          students: [],
        }
      }
      groups[row.student_group].students.push(row)
    }
  })
  return groups
})

// Students that have been removed from groups
const unassignedStudents = computed(() => {
  return editableGroups.value.filter((row) => !row.student_group)
})

// Dropdown options: list of existing group names
const availableGroupOptions = computed(() => {
  const groupNames = [
    ...new Set(
      editableGroups.value
        .filter((r) => r.student_group)
        .map((r) => r.student_group)
    ),
  ]
  return groupNames.map((name) => ({
    label: name,
    value: name,
  }))
})

// Build move options excluding the current group
function getMoveOptions(currentGroup) {
  return availableGroupOptions.value.filter(
    (opt) => opt.value !== currentGroup
  )
}

// ============================================
// Manual adjustment actions
// ============================================

function moveStudent(student, fromGroup, toGroup) {
  if (!toGroup) return
  const idx = editableGroups.value.findIndex(
    (r) => r.student === student.student && r.student_group === fromGroup
  )
  if (idx !== -1) {
    const targetRow = editableGroups.value.find(
      (r) => r.student_group === toGroup
    )
    // Replace the entire object to guarantee reactivity
    editableGroups.value[idx] = {
      ...editableGroups.value[idx],
      student_group: toGroup,
      group_instructor: targetRow?.group_instructor || '',
    }
    // Trigger array reactivity
    editableGroups.value = [...editableGroups.value]
  }
}

function removeStudentFromGroup(student, fromGroup) {
  const idx = editableGroups.value.findIndex(
    (r) => r.student === student.student && r.student_group === fromGroup
  )
  if (idx !== -1) {
    editableGroups.value[idx] = {
      ...editableGroups.value[idx],
      student_group: null,
      group_instructor: null,
    }
    editableGroups.value = [...editableGroups.value]
  }
}

function assignStudentToGroup(student, toGroup) {
  if (!toGroup) return
  const idx = editableGroups.value.findIndex(
    (r) => r.student === student.student
  )
  if (idx !== -1) {
    const targetRow = editableGroups.value.find(
      (r) => r.student_group === toGroup
    )
    editableGroups.value[idx] = {
      ...editableGroups.value[idx],
      student_group: toGroup,
      group_instructor: targetRow?.group_instructor || '',
    }
    editableGroups.value = [...editableGroups.value]
  }
}

function discardChanges() {
  editableGroups.value = JSON.parse(originalGroupsSnapshot.value)
}

// ============================================
// Save manual changes to backend
// ============================================

async function saveManualChanges() {
  isSaving.value = true
  try {
    const saveResource = createResource({
      url: 'seminary.seminary.utils.update_student_groups',
      params: {
        course: props.courseName,
        group_assignments: editableGroups.value,
      },
    })
    await saveResource.submit()

    // Refresh saved groups from server
    await saved_groups.reload()

    // Re-sync local state from the fresh server data
    if (saved_groups.data && saved_groups.data.length > 0) {
      editableGroups.value = JSON.parse(JSON.stringify(saved_groups.data))
      originalGroupsSnapshot.value = JSON.stringify(saved_groups.data)
    }
  } catch (error) {
    console.error('Error saving group changes:', error)
  } finally {
    isSaving.value = false
  }
}

// ============================================
// Recreate groups (delete existing + go to create view)
// ============================================

async function recreateGroups() {
  showRecreateConfirm.value = false
  try {
    const deleteResource = createResource({
      url: 'seminary.seminary.utils.delete_student_groups',
      params: { course: props.courseName },
    })
    await deleteResource.submit()
    // Reload saved_groups so hasSavedGroups becomes false, showing create view
    await saved_groups.reload()
    editableGroups.value = []
    originalGroupsSnapshot.value = ''
  } catch (error) {
    console.error('Error deleting groups:', error)
  }
}

// ============================================
// Create groups (original logic)
// ============================================

function createGroups() {
  try {
    if (!students.data || !Array.isArray(students.data)) {
      throw new Error(__('Students data is not available or not an array.'))
    }

    const filteredStudents = students.data.filter(
      (student) => student.audit_bool === 0 && student.active === 1
    )

    const studentData = filteredStudents.map((student) => ({
      member: student.student,
    }))

    const groups = Array.from({ length: groupCount.value }, () => [])
    studentData.forEach((student, index) => {
      groups[index % groupCount.value].push(student)
    })

    groups.forEach((group, index) => {
      const groupName = `${course.data.name} ${selectedInstructors.value[index] || instructors.data[0].instructor_name} Group ${index + 1}`
      const mentor =
        selectedInstructors.value[index] ||
        instructors.data[0].instructor_name

      createResource({
        url: 'seminary.seminary.utils.create_student_group',
        cache: ['student_group', props.courseName],
        params: {
          course: props.courseName,
          group_name: groupName,
          group_instructor: mentor,
          members: group,
        },
        auto: true,
      })
    })

    // Reload saved groups after creation
    setTimeout(() => {
      saved_groups.reload()
    }, 1500)
  } catch (error) {
    console.error('Error in createGroups function:', error)
  }
}

watch(
  () => instructors.data,
  (newValue) => {
    console.log('Instructors data changed:', newValue)
  }
)
</script>

<style>
.student-group-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 20px;
}
</style>
