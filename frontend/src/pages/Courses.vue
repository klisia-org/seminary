<template>
    <header
        class="sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5"
      >
        
        <div class="flex items-center">
          <h1 class="text-xl font-semibold text-ink-gray-9">{{ isStudent ? 'My Courses' : 'All Courses' }}</h1>
        </div>
    </header>
    <div v-if="courses.data?.length" class="p-5 pb-10 flex flex-wrap justify-center gap-4">
      <router-link
        v-for="course in courses.data"
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
    

    
    </template>
    
    <script setup>
    
    import { computed, inject, onMounted, ref, watch } from 'vue'
    import { BookOpen, Plus } from 'lucide-vue-next'
   
    import { createResource } from 'frappe-ui'
    import { ListView, ListHeader, ListHeaderItem, ListRow, ListRowItem } from 'frappe-ui'
    import { reactive } from 'vue'
    import { usersStore} from '../stores/user'
   
    
    
    const user = inject('$user')
  
    const start = ref(0)
    
    let userResource = usersStore()
    
    let isStudent = user.data.is_student
    let isModerator = user.data.is_moderator
    let isInstructor = user.data.is_instructor
    let isSystemManager = user.data.is_system_manager
    
   
    console.log(user.data)
    
    const courses = createResource({
      url: isStudent ? "seminary.seminary.utils.get_courses_for_student" : "seminary.seminary.utils.get_courses",
      params: isStudent ? { student: user.data.name } : {},
      onSuccess: (response) => {
        tableData.rows = response.sort((a, b) => {
          if (a.academic_term < b.academic_term) return -1;
          if (a.academic_term > b.academic_term) return 1;
          if (a.course_name < b.course_name) return -1;
          if (a.course_name > b.course_name) return 1;
          return 0;
        });
      },
      auto: true
    });
    
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