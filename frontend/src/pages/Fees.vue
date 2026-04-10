<template>
	<div v-if="isStudent">

		<h2
			class="text-xl font-bold text-ink-gray-8 sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5">
			{{ __('My Financial Status') }}
		</h2>

		<div v-if="studentInfo.scholarships && studentInfo.scholarships?.[0]?.scholarship"
			class="flex flex-col items-center justify-center p-3">
			<h3 class="text-lg font-bold text-ink-gray-8">
				{{ __('Scholarship') }}: {{ studentInfo.scholarships[0].scholarship }}
			</h3>
		</div>

		<div v-if="tableData.rows.length > 0" class="px-5 py-4">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b text-left text-ink-gray-6">
						<th class="py-2 px-3 font-medium">{{ __('Invoice') }}</th>
						<th class="py-2 px-3 font-medium text-right">{{ __('Amount') }}</th>
						<th class="py-2 px-3 font-medium">{{ __('Status') }}</th>
						<th class="py-2 px-3 font-medium text-right"></th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="row in tableData.rows" :key="row.name" class="border-b">
						<td class="py-2 px-3">
							<div class="text-ink-gray-9">{{ row.name }}</div>
							<div class="text-xs text-ink-gray-5">{{ row.posting_date }}</div>
						</td>
						<td class="py-2 px-3 text-right">
							<div class="text-ink-gray-9">{{ row.total }}</div>
							<div v-if="row.outstanding_amount && row.status !== 'Paid'"
								class="text-xs text-ink-gray-5">
								{{ __('Outstanding') }}: {{ row.outstanding_amount }}
							</div>
						</td>
						<td class="py-2 px-3">
							<Badge :theme="statusTheme(row.status)" :label="row.status" />
						</td>
						<td class="py-2 px-3 text-right">
							<Button v-if="row.status === 'Paid'" size="sm" variant="subtle"
								@click="openInvoicePDF(row)" icon-left="download" :label="__('Download')" />
							<Button v-else size="sm" variant="solid" theme="blue"
								@click="openModal(row)" icon-left="credit-card" :label="__('Pay')" />
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<div v-else>
			<MissingData message="No Fees found" />
		</div>
	</div>
	<div v-else class="flex flex-col items-center justify-center">
		<p class="text-lg font-bold text-ink-gray-5">{{ __('Student Financial Status are only displayed for Students') }}
		</p>
	</div>
</template>

<script setup>

import { Badge, Button, createResource } from 'frappe-ui'
import { reactive, ref, inject } from 'vue'

import MissingData from '@/components/MissingData.vue'
import { createToast } from '@/utils'
import { usersStore } from '../stores/user'
import { statusTheme } from '@/utils/statusTheme'


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

console.log("Student Scholarships:", studentInfo.scholarships)

const feesResource = createResource({
	url: 'seminary.seminary.api.get_student_invoices',
	params: {
		student: student,
	},
	onSuccess: (response) => {
		response = response.sort((a, b) => {
			const statusOrder = { Unpaid: 0, Paid: 1 }

			const statusA = statusOrder[a.status]
			const statusB = statusOrder[b.status]

			if (statusA !== statusB) {
				return statusA - statusB
			}

		})
		tableData.rows = response
	},
	auto: true,
})

const tableData = reactive({ rows: [] })

const currentRow = ref(null)
const showPaymentDialog = ref(false)

const openInvoicePDF = (row) => {
	let url = `/api/method/frappe.utils.print_format.download_pdf?
		doctype=${encodeURIComponent('Sales Invoice')}
		&name=${encodeURIComponent(row.name)}
		&format=${encodeURIComponent('Standard')}
	`
	window.open(url, '_blank')
}

const openModal = (row) => {
	currentRow.value = row
	showPaymentDialog.value = true
}

const success = () => {
	feesResource.reload()
	createToast({
		title: __('Payment Successful'),
		icon: 'check',
		iconClasses: 'text-ink-green-3',
	})
}
</script>