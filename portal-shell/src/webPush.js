// Notifications on this device (seminary decisions/121 §3 and its addendum). One
// service worker serves the whole site, so turning notifications on in one portal
// turns them on in every portal on the site.
import { call } from 'frappe-ui'

const SW_URL = '/sw.js'
const SCOPE = '/'

export function pushSupported() {
	return (
		typeof window !== 'undefined' &&
		window.isSecureContext &&
		'serviceWorker' in navigator &&
		'PushManager' in window &&
		'Notification' in window
	)
}

// iOS shows notifications only for a portal added to the Home Screen and
// opened from there (16.4 and later).
export function needsHomeScreen() {
	const ios =
		/iphone|ipad|ipod/i.test(navigator.userAgent) ||
		(navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
	const standalone =
		window.matchMedia?.('(display-mode: standalone)').matches || navigator.standalone === true
	return ios && !standalone
}

export function permission() {
	return 'Notification' in window ? Notification.permission : 'default'
}

function keyBytes(base64url) {
	const padded = (base64url + '='.repeat((4 - (base64url.length % 4)) % 4))
		.replace(/-/g, '+')
		.replace(/_/g, '/')
	const raw = atob(padded)
	return Uint8Array.from(raw, (c) => c.charCodeAt(0))
}

function sameKey(buffer, bytes) {
	if (!buffer) return false
	const a = new Uint8Array(buffer)
	return a.length === bytes.length && a.every((v, i) => v === bytes[i])
}

export async function currentSubscription() {
	if (!pushSupported()) return null
	const reg = await navigator.serviceWorker.getRegistration(SCOPE)
	return reg ? reg.pushManager.getSubscription() : null
}

// The server never sends endpoints back; it matches this device by hash.
export async function endpointHash(endpoint) {
	const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(endpoint))
	return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, '0')).join('')
}

export function deviceLabel() {
	const ua = navigator.userAgent
	const browser = /Edg\//.test(ua)
		? 'Edge'
		: /Firefox\//.test(ua)
			? 'Firefox'
			: /Chrome\//.test(ua)
				? 'Chrome'
				: /Safari\//.test(ua)
					? 'Safari'
					: ''
	const system = /Android/.test(ua)
		? 'Android'
		: /iPhone|iPad|iPod/.test(ua)
			? 'iPhone/iPad'
			: /Mac OS X/.test(ua)
				? 'Mac'
				: /Windows/.test(ua)
					? 'Windows'
					: /Linux/.test(ua)
						? 'Linux'
						: ''
	return [browser, system].filter(Boolean).join(' on ')
}

// Returns the server's row for this device. Throws 'denied' when the person
// (or the browser) refuses permission.
export async function turnOn(publicKey) {
	const granted = await Notification.requestPermission()
	if (granted !== 'granted') throw new Error('denied')
	const reg = await navigator.serviceWorker.register(SW_URL, { scope: SCOPE })
	await navigator.serviceWorker.ready
	const key = keyBytes(publicKey)
	let sub = await reg.pushManager.getSubscription()
	// A subscription made with an older key would be refused by the push service.
	if (sub && !sameKey(sub.options?.applicationServerKey, key)) {
		await sub.unsubscribe()
		sub = null
	}
	if (!sub) {
		sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key })
	}
	return call('seminary.seminary.web_push.subscribe', {
		subscription: JSON.stringify(sub.toJSON()),
		device_label: deviceLabel(),
	})
}

export async function turnOff() {
	const sub = await currentSubscription()
	if (!sub) return
	await call('seminary.seminary.web_push.remove_device', { endpoint: sub.endpoint })
	await sub.unsubscribe()
}
