import router from '@/router'
import translationPlugin from '@/translation'
import utils from frappe.utils

const { siteURL } = utils.get_url()
export function generateCalendarURL(courseSchedule, token) {