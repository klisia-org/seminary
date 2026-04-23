<template>
	<div v-if="isStudent">

		<h2
			class="text-xl font-bold text-ink-gray-8 sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5">
			{{ __('My Financial Status') }}
		</h2>

		<!-- Payment success banner -->
		<div v-if="paymentSuccess"
			class="mx-5 mt-4 flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
			<svg class="h-5 w-5 shrink-0 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
				<path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
			</svg>
			<span class="font-medium">{{ __('Payment successful! Your balance has been updated.') }}</span>
		</div>

		<div v-if="studentInfo.scholarships && studentInfo.scholarships?.[0]?.scholarship"
			class="flex flex-col items-center justify-center p-3">
			<h3 class="text-lg font-bold text-ink-gray-8">
				{{ __('Scholarship') }}: {{ studentInfo.scholarships[0].scholarship }}
			</h3>
		</div>

		<div v-if="tableData.rows.length > 0" class="px-5 py-4">
			<!-- Summary bar -->
			<div class="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-surface-gray-2 px-4 py-3 mb-4">
				<div class="flex flex-wrap gap-4 text-sm">
					<div>
						<span class="text-ink-gray-5">{{ __('Total') }}:</span>
						<span class="ml-1 font-semibold text-ink-gray-8">{{ formatCurrency(totalOutstanding) }}</span>
					</div>
					<div v-if="totalCredits < 0">
						<span class="text-ink-gray-5">{{ __('Credits') }}:</span>
						<span class="ml-1 font-semibold text-ink-green-3">{{ formatAbs(totalCredits) }} {{ __('Cr') }}</span>
					</div>
					<div>
						<span class="text-ink-gray-5">{{ __('Net Payable') }}:</span>
						<span class="ml-1 font-bold text-ink-gray-9">{{ formatCurrency(netPayableAmount) }}</span>
					</div>
				</div>
				<div v-if="paymentEnabled && netPayableAmount > 0" class="flex gap-2">
					<Button size="sm" variant="solid" theme="blue"
						@click="payFullBalance" icon-left="credit-card"
						:label="payingAll ? __('Redirecting...') : __('Pay Full Balance')"
						:disabled="payingAll" />
					<Button size="sm" variant="outline"
						@click="showPartialDialog = true" icon-left="credit-card"
						:label="__('Pay Partial')"
						:disabled="payingAll" />
				</div>
			</div>

			<table class="w-full text-sm">
				<thead>
					<tr class="border-b text-left text-ink-gray-6">
						<th class="py-2 px-3 font-medium">{{ __('Invoice') }}</th>
						<th class="py-2 px-3 font-medium">{{ __('Course') }}</th>
						<th class="py-2 px-3 font-medium text-right">{{ __('Amount') }}</th>
						<th class="py-2 px-3 font-medium">{{ __('Status') }}</th>
						<th class="py-2 px-3 font-medium text-right"></th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="row in tableData.rows" :key="row.name" class="border-b">
						<td class="py-2 px-3">
							<a class="text-ink-blue-3 hover:underline cursor-pointer" @click="openInvoicePDF(row)">
								{{ row.name }}
							</a>
							<div class="text-xs text-ink-gray-5">{{ row.posting_date }}</div>
						</td>
						<td class="py-2 px-3">
							<span v-if="row.summary || row.course" class="text-ink-gray-7">{{ row.summary || row.course }}</span>
							<span v-else class="text-ink-gray-4">-</span>
						</td>
						<td class="py-2 px-3 text-right">
							<div v-if="row.is_return" class="text-ink-green-3 font-medium">
								{{ formatAbs(row.total_raw) }} {{ __('Cr') }}
							</div>
							<div v-else class="text-ink-gray-9">{{ row.total }}</div>
							<div v-if="parseFloat(row.outstanding_raw) !== parseFloat(row.total_raw) && row.status !== 'Paid' && !row.is_return"
								class="text-xs text-ink-gray-5">
								{{ __('Outstanding') }}: {{ row.outstanding_amount }}
							</div>
							<div v-if="row.is_return" class="text-xs text-ink-gray-5">
								<span v-if="parseFloat(row.outstanding_raw) === 0">{{ __('Credit already applied') }}</span>
								<span v-else>{{ __('Credit available') }}: {{ formatAbs(row.outstanding_raw) }}</span>
							</div>
						</td>
						<td class="py-2 px-3">
							<Badge :theme="statusTheme(row.status)" :label="row.status" />
						</td>
						<td class="py-2 px-3 text-right">
							<Button v-if="row.status === 'Paid'" size="sm" variant="subtle"
								@click="openInvoicePDF(row)" icon-left="download" :label="__('Download')" />
							<Button v-else-if="paymentEnabled && !row.is_return" size="sm" variant="solid" theme="blue"
								@click="payInvoice(row)" icon-left="credit-card"
								:label="payingInvoice === row.name ? __('Redirecting...') : __('Pay')"
								:disabled="payingInvoice === row.name || payingAll" />
							<span v-else-if="!row.is_return" class="text-xs text-ink-gray-5">{{ __('Awaits payment') }}</span>
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<div v-else-if="!feesResource.loading">
			<MissingData message="No Fees found" />
		</div>

		<!-- Partial payment dialog -->
		<Dialog v-model="showPartialDialog" :options="{ title: __('Pay Partial Amount'), size: 'sm' }">
			<template #body-content>
				<div class="space-y-4">
					<FormControl
						type="number"
						:label="__('Amount to pay')"
						v-model="partialAmount"
						:min="0"
						:max="netPayableAmount"
						:placeholder="__('Enter amount')"
					/>
					<p class="text-xs text-ink-gray-5">
						{{ __('Amount will be allocated to invoices by due date, earliest first.') }}
					</p>
				</div>
			</template>
			<template #actions>
				<Button variant="solid" theme="blue" class="w-full"
					@click="payPartialBalance"
					:label="payingAll ? __('Redirecting...') : __('Pay')"
					:disabled="payingAll || !partialAmount || partialAmount <= 0" />
			</template>
		</Dialog>
	</div>
	<div v-else class="flex flex-col items-center justify-center">
		<p class="text-lg font-bold text-ink-gray-5">{{ __('Student Financial Status are only displayed for Students') }}
		</p>
	</div>
</template>

<script setup>

import { Badge, Button, Dialog, FormControl, createResource } from 'frappe-ui'
import { computed, onMounted, reactive, ref, inject } from 'vue'

import MissingData from '@/components/MissingData.vue'
import { createToast } from '@/utils'
import { usersStore } from '../stores/user'
import { statusTheme } from '@/utils/statusTheme'

const paymentSuccess = ref(false)

onMounted(() => {
	if (window.location.href.includes('payment=success')) {
		paymentSuccess.value = true
		window.history.replaceState({}, '', window.location.pathname)
		setTimeout(() => { paymentSuccess.value = false }, 10000)
	}
})


let studentInfo = usersStore()


const user = inject('$user')

const start = ref(0)

let userResource = usersStore()

let isStudent = user.data.is_student

let student = user.data.student

const scholarshipsResource = createResource({
	url: 'seminary.seminary.api.get_scholarship',
	params: {
		student: student,
	},
	onSuccess: (response) => {
		studentInfo.scholarships = response
	},
	auto: true,
})

const seminarySettings = createResource({
	url: 'frappe.client.get_value',
	params: {
		doctype: 'Seminary Settings',
		fieldname: 'portal_payment_enable',
	},
	auto: true,
})

const paymentEnabled = computed(() => {
	return seminarySettings.data?.portal_payment_enable === 1
})

const feesResource = createResource({
	url: 'seminary.seminary.api.get_student_invoices',
	params: {
		student: student,
	},
	onSuccess: (response) => {
		// Sort: unpaid (with outstanding) first, then returns, then paid (newest first)
		response = response.sort((a, b) => {
			const statusRank = (r) => {
				if (r.status === 'Paid') return 2
				if (r.is_return) return 1
				return 0
			}
			const rankA = statusRank(a)
			const rankB = statusRank(b)
			if (rankA !== rankB) return rankA - rankB
			// Within same group, newest first
			if (a.posting_date > b.posting_date) return -1
			if (a.posting_date < b.posting_date) return 1
			return 0
		})
		tableData.rows = response
	},
	auto: true,
})

const tableData = reactive({ rows: [] })

const payingInvoice = ref(null)
const payingAll = ref(false)
const showPartialDialog = ref(false)
const partialAmount = ref(null)

// Computed totals from raw numeric values
const totalOutstanding = computed(() => {
	return tableData.rows
		.filter(r => !r.is_return && r.status !== 'Paid')
		.reduce((sum, r) => sum + parseFloat(r.outstanding_raw || 0), 0)
})

const totalCredits = computed(() => {
	return tableData.rows
		.filter(r => r.is_return)
		.reduce((sum, r) => sum + parseFloat(r.outstanding_raw || 0), 0)
})

const netPayableAmount = computed(() => {
	return Math.max(0, totalOutstanding.value + totalCredits.value)
})

const formatCurrency = (value) => {
	return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const formatAbs = (value) => {
	return Math.abs(parseFloat(value || 0)).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const openInvoicePDF = (row) => {
	let url = `/api/method/frappe.utils.print_format.download_pdf?doctype=${encodeURIComponent('Sales Invoice')}&name=${encodeURIComponent(row.name)}&format=${encodeURIComponent('Standard')}`
	window.open(url, '_blank')
}

const payInvoice = (row) => {
	payingInvoice.value = row.name
	createResource({
		url: 'seminary.seminary.api.get_invoice_payment_url',
		params: { invoice_name: row.name },
		onSuccess: (data) => {
			if (data.payment_url) {
				window.location.href = data.payment_url
			}
		},
		onError: () => {
			payingInvoice.value = null
			createToast({
				title: __('Payment Error'),
				text: __('Could not initiate payment. Please try again.'),
				icon: 'x',
				iconClasses: 'text-ink-red-3',
			})
		},
		auto: true,
	})
}

const payFullBalance = () => {
	payingAll.value = true
	createResource({
		url: 'seminary.seminary.api.get_student_balance_payment_url',
		onSuccess: (data) => {
			if (data.payment_url) {
				window.location.href = data.payment_url
			}
		},
		onError: () => {
			payingAll.value = false
			createToast({
				title: __('Payment Error'),
				text: __('Could not initiate payment. Please try again.'),
				icon: 'x',
				iconClasses: 'text-ink-red-3',
			})
		},
		auto: true,
	})
}

const payPartialBalance = () => {
	payingAll.value = true
	showPartialDialog.value = false
	createResource({
		url: 'seminary.seminary.api.get_student_partial_balance_payment_url',
		params: { amount: partialAmount.value },
		onSuccess: (data) => {
			if (data.payment_url) {
				window.location.href = data.payment_url
			}
		},
		onError: () => {
			payingAll.value = false
			createToast({
				title: __('Payment Error'),
				text: __('Could not initiate payment. Please try again.'),
				icon: 'x',
				iconClasses: 'text-ink-red-3',
			})
		},
		auto: true,
	})
}
</script>
