<template>
  <header
    class="sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5"
  >
    <div class="flex items-center">
      <h1 class="text-xl font-semibold text-ink-gray-9">{{ isStudent ? 'My Courses' : 'All Courses' }}</h1>
    </div>
  </header>

  <!-- Parent container for filters and course cards -->
  <div class="p-5 flex flex-row gap-4 w-full mx-auto">
    <!-- To Do Column -->
<div class="w-1/4 p-4">
  <h2 class="text-lg font-semibold mb-4">To Do</h2>
  <div v-if="isStudent || isInstructor">
    <div v-for="entry in courseToDoList" :key="entry.course.name" >
  <h3 class="text-md font-medium mb-2">{{ entry.course.name }}</h3>
  <CourseCardToDo :course="entry.course.name" :singleCourse="false" />
</div>

<div v-if="courseToDoList.length === 0">
  <PartyPopper class="size-20 mx-auto stroke-1 text-gray-500 mt-5" />
  <h3 v-if="isStudent" class="text-xl text-center font-semibold text-gray-500 mt-5"> Congrats! No assessments to do!</h3>
  <h3 v-if="isInstructor" class="text-xl text-center font-semibold text-gray-500 mt-5"> Congrats! No assessments to grade!</h3>
</div>
  </div>
</div>

    <!-- Main Content -->
    <div class="w-3/4">
      <!-- Filters for non-student users -->
      <div class="flex gap-4 mb-5">
        <div>
          <label for="courseFilter" class="block text-sm font-medium text-gray-700">Course</label>
          <select
            id="courseFilter"
            v-model="filters.course"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          >
            <option value="">All Courses</option>
            <option v-for="course in uniqueCourses" :key="course" :value="course">
              {{ course }}
            </option>
          </select>
        </div>
        <div>
          <label for="academicTermFilter" class="block text-sm font-medium text-gray-700">Academic Term</label>
          <select
            id="academicTermFilter"
            v-model="filters.academic_term"
            class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm"
          >
            <option value="">All Terms</option>
            <option v-for="term in uniqueAcademicTerms" :key="term" :value="term">
              {{ term }}
            </option>
          </select>
        </div>
      </div>

      <!-- Course Cards -->
      <div v-if="filteredCourses.length" class="flex flex-wrap justify-start gap-4">
        <router-link
          v-for="course in filteredCourses"
          :to="{ name: 'CourseDetail', params: { courseName: course.name } }"
          :key="course.name"
          class="course_card"
        >
          <div class="course-image" :style="{ backgroundImage: `url(${encodeURI(course.course_image)})` }"></div>
          <div class="p-4 text-container">
            <h3 class="text-2xl font-semibold">{{ course.course }}</h3>
            <div class="short-introduction text-ink-gray-7 text-sm">
              {{ course.short_introduction }}
            </div>
            <div class="academic-term text-right mt-auto">
              {{ course.academic_term }}
            </div>
          </div>
        </router-link>
      </div>
      <div v-else class="flex flex-col items-center justify-center text-sm text-ink-gray-5 italic mt-48">
        <BookOpen class="size-10 mx-auto stroke-1 text-ink-gray-4" />
        <div class="text-2xl font-medium mb-1">
          <span>No courses found</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, inject, onMounted, ref, watch, watchEffect, reactive, toRaw } from 'vue'
import { BookOpen, Plus, PartyPopper } from 'lucide-vue-next'
import { createResource } from 'frappe-ui'
import { ListView, ListHeader, ListHeaderItem, ListRow, ListRowItem } from 'frappe-ui'
import { usersStore } from '../stores/user'
import CourseCardToDo from '@/components/CourseCardToDo.vue'
 import { useCourseToDo } from '@/utils/useCourseToDo'

const user = inject('$user')
const start = ref(0)

const { userResource } = usersStore()

// Debug logging
console.log('User from inject:', user)
console.log('User data:', user.data)
console.log('User resource:', userResource)
console.log('User resource data:', userResource.data)

// Make these computed properties that react to user.data changes
const isStudent = computed(() => user.data?.is_student || false)
const isModerator = computed(() => user.data?.is_moderator || false)
const isInstructor = computed(() => user.data?.is_instructor || false)
const isSystemManager = computed(() => user.data?.is_system_manager || false)


const cachedAcademicTerm = ref('');

const current_AcademicTerm = createResource({
  url: "frappe.client.get_value",
  params: {
    doctype: "Academic Term",
    fieldname: "title",
    filters: {
      iscurrent_acterm: 1
    }
  },
  auto: true,
  onSuccess: (data) => {
    if (data?.title) {
      cachedAcademicTerm.value = data.title;
      console.log("Current Academic Term on success:", data.title);
      console.log('isStudent:', isStudent.value)
    } else {
      console.log("Current Academic Term: undefined");
    }
  }
});

onMounted(() => {
  current_AcademicTerm.reload();
});

watch(
  () => current_AcademicTerm.data,
  (newData) => {
    if (newData?.title) {
      cachedAcademicTerm.value = newData.title;
    } else {
      console.log("Current Academic Term: undefined");
    }
  },
  { immediate: true }
);

watch(
  () => cachedAcademicTerm.value,
  (newTerm) => {
    if (newTerm) {
      filters.academic_term = newTerm;
      console.log("Updated filters.academic_term:", filters.academic_term);
    }
  }
);

const filters = reactive({
  course: '',
  academic_term: current_AcademicTerm.data?.title || ''
});
console.log(filters.academic_term)

// Ensure the URL is resolved as a string before passing to createResource
const resolvedUrl = computed(() => {
  return isStudent.value
    ? "seminary.seminary.utils.get_courses_for_student"
    : "seminary.seminary.utils.get_courses";
});

// Ensure params is resolved as a plain object to avoid circular references
const resolvedParams = computed(() => {
  return isStudent.value ? { student: user.data?.name } : {};
});


// Make courses resource reactive
const courses = createResource({
  url: resolvedUrl.value, // Pass the resolved string value
  params: resolvedParams.value, // Pass the resolved plain object
  onSuccess: (response) => {
    console.log("Courses data:", response);
    tableData.rows = response.sort((a, b) => {
      if (a.academic_term < b.academic_term) return -1;
      if (a.academic_term > b.academic_term) return 1;
      if (a.course < b.course) return -1;
      if (a.course > b.course) return 1;
      return 0;
    });
  },
  auto: true,
})



const tableData = reactive({
  rows: [],
  columns: [
    {
      label: 'Name',
      key: 'name',
      width: 1,
    },
    {
      label: 'Course',
      key: 'course',
      width: 1,
    },
    {
      label: 'Academic Term',
      key: 'academic_term',
      width: 1,
    },
    {
      label: 'Start Date',
      key: 'c_datestart',
      width: 1,
    },
    {
      label: 'End Date',
      key: 'c_dateend',
      width: 1,
    },
    {
      label: 'Image',
      key: 'course_image',
      width: 1,
    }
  ]
})

const uniqueCourses = computed(() => {
  return [...new Set(courses.data?.map(course => course.course))]
})

const uniqueAcademicTerms = computed(() => {
  return [...new Set(courses.data?.map(course => course.academic_term))]
})

const filteredCourses = computed(() => {
  return courses.data?.filter(course => {
    return (!filters.course || course.course === filters.course) &&
           (!filters.academic_term || course.academic_term === filters.academic_term)
  }) || []
})



const setQueryParams = () => {
  let queries = new URLSearchParams(location.search)
  let filterKeys = {
    name: course?.name || '',
  }

  Object.keys(filterKeys).forEach((key) => {
    if (filterKeys[key]) {
      queries.set(key, filterKeys[key])
    } else {
      queries.delete(key)
    }
  })

  history.replaceState({}, '', `${location.pathname}?${queries.toString()}`)
}

// We'll store one instance per course (keyed by course name) in a map.
const courseTodoInstances = ref({})
const courseToDoList = ref([]);
// When filteredCourses changes, add a to-do instance for any new course.
// Populate the map when filteredCourses changes:
watch(filteredCourses, (newCourses) => {
  if (!newCourses) return;
  const list = [];
  newCourses.forEach(course => {
    if (!courseTodoInstances.value[course.name]) {
      courseTodoInstances.value[course.name] = useCourseToDo(course.name, user);
      console.log('Created instance for course:', course.name, courseTodoInstances.value[course.name]);
    }
    const todoInstance = courseTodoInstances.value[course.name];
    const count = todoInstance.countToDoItems;
    console.log('Starting if statement with count:', count, 'for todoInstance:', todoInstance);
    if (todoInstance && count > 0) {
      list.push({ course: course, count: count });
    }
    });
    console.log('List: ', list);
    courseToDoList.value = list;
    console.log('Updated courseToDoList:', courseToDoList.value);
  });



let isInitialLoad = true;

watch(
  () => filteredCourses,
  (newFilteredCourses) => {
    if (isInitialLoad) {
      isInitialLoad = false; // Skip the first execution
      return;
    }

    if (!Array.isArray(newFilteredCourses)) {
      console.error("newFilteredCourses is not an array:", newFilteredCourses);
      newFilteredCourses = [];
    }

    const updatedList = newFilteredCourses.map(course => {
      const todo = useCourseToDo(course.name, user);
      return {
        course,
        count: todo.countToDoItems.value, // Accessing the value correctly
        hasItems: todo.countToDoItems.value > 0, // Ensuring correct comparison
      };
    }).filter(entry => entry.hasItems);

    courseToDoList.value = updatedList;
    console.log("Updated courseToDoList:", courseToDoList.value);
  },
  { immediate: true }
);
</script>

<style>
.course_card {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 400px;
  height: 400px;
  align-items: center;
  justify-content: flex-start;
  padding: 0;
  border-radius: 0.5rem;
  box-shadow: 0 0 1rem rgba(0, 0, 0, 0.1);
  background-color: #fff;
  transition: all 0.3s;
}
.course-image {
    width: 100%;
    height: 66.67%; /* 4:3 aspect ratio */
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    border-top-left-radius: 0.5rem;
    border-top-right-radius: 0.5rem;
}
.text-container {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    height: 33.33%; /* Bottom third of the card */
    padding: 1rem;
    width: 100%;
}
.short-introduction {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    text-overflow: ellipsis;
    width: 100%;
    overflow: hidden;
    margin: 0.25rem 0 1.25rem;
    line-height: 1.5;
}
@media (max-width: 640px) {
  .course_card {
    max-width: 100%;
    height: auto;
  }
  .course-image {
    height: auto;
    aspect-ratio: 4 / 3;
  }
  .text-container {
    height: auto;
  }
}
</style>