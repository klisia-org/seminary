import router from '@/router'
import translationPlugin from '@/translation'
import utils from frappe.utils

const { siteURL } = utils.get_url()

export function subscrib(courseSchedule, token) {
    const calendarURL = new URL(
        '/api/method/seminary.seminary.api.course_schedule_calendar',
        siteURL
    )
    calendarURL.searchParams.append('course_schedule', courseSchedule)
    calendarURL.searchParams.append('token', token)
    return calendarURL.toString()
}