/// <reference types="vite/client" />

declare module '*.vue' {
	const component: any
	export default component
}

interface Window {
	frappe: any
}

declare const frappe: any
declare const __: (key: string) => string
