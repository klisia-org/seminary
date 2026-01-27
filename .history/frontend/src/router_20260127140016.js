import { createRouter, createWebHistory } from 'vue-router'
import { usersStore } from '@/stores/user'
import { sessionStore } from '@/stores/session'
import path from 'path'


const routes = [
	{
		path: "/app/seminary",
		},
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
    path: "/courses/:courseName/assessment",
    name: "CourseAssessment",
    component: () => import('@/pages/CourseAssessment.vue'),
    props: true,
  },
  {
		path: '/courses/:courseName/learn/:chapterNumber-:lessonNumber',
		name: 'Lesson',
		component: () => import('@/pages/Lesson.vue'),
		props: true,
	},
  {
		path: '/courses/:courseName/edit',
		name: 'CourseForm',
		component: () => import('@/pages/CourseForm.vue'),
		props: true,
	},
  {
		path: '/courses/:courseName/learn/:chapterNumber-:lessonNumber/edit',
		name: 'LessonForm',
		component: () => import('@/pages/LessonForm.vue'),
		props: true,
	},
  {
    path: "/instructorprofile/:instructorName",
    name: "InstructorProfile",
    component: () => import('@/pages/InstructorProfile.vue'),
    props: true,
  },
  {
		path: '/quizzes',
		name: 'Quizzes',
		component: () => import('@/pages/Quizzes.vue'),
	},
	{
		path: '/quizzes/:quizID?',
		name: 'QuizForm',
		component: () => import('@/pages/QuizForm.vue'),
		props: true,
	},
	{
		path: '/quiz/:quizID',
		name: 'QuizPage',
		component: () => import('@/pages/QuizPage.vue'),
		props: true,
	},
	{
		path: '/quiz-submissions/:quizID',
		name: 'QuizSubmissionList',
		component: () => import('@/pages/QuizSubmissionList.vue'),
		props: true,
	},
	{
		path: '/gradebook/:courseName/:quizID',
		name: 'QuizSubmissionCS',
		component: () => import('@/pages/QuizSubmissionCS.vue'),
		props: true,
	},
	{
		path: '/quiz-submission/:submission',
		name: 'QuizSubmission',
		component: () => import('@/pages/QuizSubmission.vue'),
		props: true,
	},
	{
		path: '/assignments',
		name: 'Assignments',
		component: () => import('@/pages/Assignments.vue'),
	},
	{
		path: '/assignments/:assignmentID',
		name: 'AssignmentForm',
		component: () => import('@/pages/AssignmentForm.vue'),
		props: true,
	},
	{
		path: '/gradebook/:courseName/assignment-submissions/:assignmentID/:submissionName',
		name: 'AssignmentSubmission',
		component: () => import('@/pages/AssignmentSubmission.vue'),
		props: true,
	},
	{
		path:'/assignment-submissions', 
		name: 'AssignmentSubmissionList',
		component: () => import('@/pages/AssignmentSubmissionList.vue'),
	},
	{
		path: '/gradebook/:courseName/assignment-submissions/:assignmentID',
		name: 'AssignmentSubmissionCS',
		component: () => import('@/pages/AssignmentSubmissionCS.vue'),
		props: true,
	},
	{
		path: '/exams',
		name: 'Exams',
		component: () => import('@/pages/Exams.vue'),
	},
	{
  		path: '/exams/:examID?',
  		name: 'ExamForm',
  		component: () => import('@/pages/ExamForm.vue'),
  		props: true,
	},
	{
		path: '/exam/:examID',
		name: 'ExamPage',
		component: () => import('@/pages/ExamPage.vue'),
		props: true,
	},
	{
		path: '/exam-submissions/:examID',
		name: 'ExamSubmissionList',
		component: () => import('@/pages/ExamSubmissionList.vue'),
		props: true,
	},
	{
		path: '/gradebook/:courseName/exam-submissions/:examID/:submission',
		name: 'ExamSubmission',
		component: () => import('@/pages/ExamSubmission.vue'),
		props: true,
	},
	{
		path: '/gradebook/:courseName/exam-submissions/:examID',
		name: 'ExamSubmissionCS',
		component: () => import('@/pages/ExamSubmissionCS.vue'),
		props: true,
	},
	{
		path: '/gradebook/:courseName',
		name: 'Gradebook',
		component: () => import('@/pages/Gradebook.vue'),
		props: true,	
	},
	{
		path: '/attendance/:courseName',
		name: 'StudentAttendanceCS',
		component: () => import('@/pages/StudentAttendanceCS.vue'),
		props: true,	
	},
	{
  		path: '/discussion-activity/:discussionID?',
  		name: 'DiscussionActivityForm',
  		component: () => import('@/pages/DiscussionActivityForm.vue'),
  		props: true,
	},
	{
		path: '/gradebook/:courseName/discussion-submissions/:discussionID/:submissionName',
		name: 'DiscussionActivitySubmission',
		component: () => import('@/pages/DiscussionActivitySubmission.vue'),
		props: true,
	},
	{
		path: '/discussion-activity-submissions',
		name: 'DiscussionActivitySubmissionList',
		component: () => import('@/pages/DiscussionActivitySubmissionList.vue'),
		
	},
	{
		path: '/discussion-activities',
		name: 'DiscussionActivities',
		component: () => import('@/pages/DiscussionActivities.vue'),
	},
		{
		path: '/gradebook/:courseName/discussion-submissions/:discussionID',
		name: 'DiscussionActivitySubmissionCS',
		component: () => import('@/pages/DiscussionActivitySubmissionCS.vue'),
		props: true,
	},
	{
		path: '/mock',
		name: 'Mock',
		component: () => import('@/pages/Mock.vue'),
	},
	{
		path: '/courses/:courseName/student-group',
		name: 'StudentGroup',
		component: () => import('@/pages/StudentGroup.vue'),
		props: true,
	},
  {
    path :'/:catchAll(.*)',
    redirect: '/courses',
  }
]

const router = createRouter({
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