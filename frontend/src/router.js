import { createRouter, createWebHistory } from 'vue-router'
import { usersStore } from '@/stores/user'
import { sessionStore } from '@/stores/session'


const routes = [

 

  {
    path: "/fees",
    name: "Fees",
    component: () => import('@/pages/Fees.vue'),

  },
  {
    path: "/grades",
    name: "Transcripts",
    component: () => import('@/pages/Grades.vue'),
  },
  {
    path: "/courses",
    name: "Courses",
    component: () => import('@/pages/Courses.vue'), 
  },
	{
		path: '/courses/:courseName',
		name: 'CourseDetail',
		component: () => import('@/pages/CourseDetail.vue'),
		props: true,
	},
  {
		path: '/courses/:courseName/learn/:chapterNumber-:lessonNumber',
		name: 'Lesson',
		component: () => import('@/pages/Lesson.vue'),
		props: true,
	},
  {
    path :'/:catchAll(.*)',
    redirect: '/courses',
  }
]

let router = createRouter({
  history: createWebHistory('/seminary/'),
  routes,
})

router.beforeEach(async (to, from, next) => {
	const { userResource } = usersStore()
	let { isLoggedIn } = sessionStore()
	

	try {
		if (isLoggedIn) {
			await userResource.promise
		}
	} catch (error) {
		isLoggedIn = false
	}

  if (!isLoggedIn) {
    window.location.href = '/login'
    return
  }
  return next()
})


export default router