import { createRouter, createWebHistory } from 'vue-router'
import { usersStore } from '@/stores/user'
import { sessionStore } from '@/stores/session'
import path from 'path'


const routes = [
	{
		path: "/desk/seminary",
		name: "Desk",
		beforeEnter() {
			window.location.href = '/desk/seminary';
		},
		meta: { requiresAuth: true },
		},
  {
    path: "/fees",
    name: "Fees",
    component: () => import('@/pages/Fees.vue'),
  },
  {
    path: "/jobs",
    name: "Jobs",
    component: () => import('@/pages/Jobs.vue'),
  },
  {
    path: "/jobs/:jobName",
    name: "JobOpening",
    component: () => import('@/pages/JobOpening.vue'),
    props: true,
  },
  {
    path: "/jobs/:jobName/apply",
    name: "JobApplication",
    component: () => import('@/pages/JobApplication.vue'),
    props: true,
  },
  {
    path: "/partner",
    redirect: "/partner/jobs",
  },
  {
    path: "/partner/profile",
    name: "PartnerProfile",
    component: () => import('@/pages/PartnerProfile.vue'),
  },
  {
    path: "/partner/people",
    name: "PartnerPeople",
    component: () => import('@/pages/PartnerPeople.vue'),
  },
  {
    path: "/partner/jobs",
    name: "PartnerJobPostings",
    component: () => import('@/pages/PartnerJobPostings.vue'),
  },
  {
    path: "/partner/jobs/new",
    name: "PartnerJobPostingNew",
    component: () => import('@/pages/PartnerJobPostingForm.vue'),
  },
  {
    path: "/partner/jobs/:name/edit",
    name: "PartnerJobPostingEdit",
    component: () => import('@/pages/PartnerJobPostingForm.vue'),
    props: true,
  },
  {
    path: "/partner/jobs/:name",
    name: "PartnerJobPosting",
    component: () => import('@/pages/PartnerJobPosting.vue'),
    props: true,
  },
  {
    path: "/partner/jobs/:name/applications/:appName",
    name: "PartnerApplication",
    component: () => import('@/pages/PartnerApplication.vue'),
    props: true,
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
    path: '/courses/:courseName/status',
    name: 'CourseStatus',
    component: () => import('@/pages/CourseStatus.vue'),
    props: true,
  },
  {
    path: '/courses/:courseName/withdraw',
    name: 'CourseWithdrawalRequest',
    component: () => import('@/pages/CourseWithdrawalRequest.vue'),
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
		path: '/attendance-checkin',
		name: 'CourseCheckin',
		component: () => import('@/pages/CourseCheckin.vue'),
	},
		{
		path: '/discussion-activities',
		name: 'DiscussionActivities',
		component: () => import('@/pages/DiscussionActivities.vue'),
	},
	{
  		path: '/discussion-activities/:discussionID',
  		name: 'DiscussionActivityForm',
  		component: () => import('@/pages/DiscussionActivityForm.vue'),
  		props: true,
	},
		{
		path: '/gradebook/:courseName/discussion-submissions/:discussionID',
		name: 'DiscussionActivitySubmissionCS',
		component: () => import('@/pages/DiscussionActivitySubmissionCS.vue'),
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
		path: '/courses/:courseName/course-calendar',
		name: 'CourseCalendar',
		component: () => import('@/pages/CourseCalendar.vue'),
		props: true,
	},
  {
    path: "/program-audit",
    name: "ProgramAudit",
    component: () => import('@/pages/ProgramAudit.vue'),
  },
  {
    path: "/culminating-project",
    name: "CulminatingProject",
    component: () => import('@/pages/CulminatingProject.vue'),
  },
  {
    path: "/enrollment",
    name: "Enrollment",
    component: () => import('@/pages/Enrollment.vue'),
  },
  {
    path: "/announcements",
    redirect: "/inbox",
  },
  {
    path: "/inbox",
    name: "Inbox",
    component: () => import('@/pages/Inbox.vue'),
  },
  {
    path: "/preferences",
    name: "CommunicationPreferences",
    component: () => import('@/pages/CommunicationPreferences.vue'),
  },
  {
    path: "/alumni",
    name: "AlumniHome",
    component: () => import('@/pages/AlumniHome.vue'),
  },
  {
    path: "/alumni/directory",
    name: "AlumniDirectory",
    component: () => import('@/pages/AlumniDirectory.vue'),
  },
  {
    path: "/alumni/profile",
    name: "AlumniProfile",
    component: () => import('@/pages/AlumniProfile.vue'),
  },
  {
    path: '/recommender-form/:name',
    name: 'RecommenderForm',
    component: () => import('@/pages/RecommenderForm.vue'),
    meta: { guest: true },
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

  if (to.meta?.guest) {
    return next()
  }

  if (!isLoggedIn) {
    window.location.href = '/login'
    return
  }
  return next()
})


export default router