<template>
	<div v-if="isStudent">

		<h2
			class="text-xl font-bold text-gray-800 sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5">
			{{ __('My Financial Status') }}
		</h2>


		<div v-if="studentInfo.scholarships && studentInfo.scholarships.length > 0 && studentInfo.scholarships"
			class="flex flex-col items-center justify-center p-3">
			<h2 class="text-lg font-bold text-gray-800">
				{{ __('Scholarship') }}: {{ studentInfo.scholarships[0].scholarship }}
			</h2>
			<br>
		</div>
		<div v-else class="flex flex-col items-center justify-center">
			<p class="text-lg font-bold text-gray-800"> </p>
		</div>

		<div v-if="tableData.rows.length > 0" class="px-5 py-4">
			<ListView :columns="tableData.columns" :rows="tableData.rows" :options="{
				selectable: false,
				showTooltip: false,
				onRowClick: () => { },
			}" row-key="id" v-if="tableData.rows.length > 0">
				<ListHeader>
					<ListHeaderItem v-for="column in tableData.columns" :key="column.key" :item="column" />
				</ListHeader>
				<ListRow v-for="row in tableData.rows" :key="row.id" :row="row" v-slot="{ column, item }">
					<ListRowItem :item="item" :align="column.align">
						<Badge v-if="column.key === 'status'" variant="subtle" :theme="row.status === 'Paid' ? (bg_color = 'green') : (bg_color = 'red')
							" size="md" :label="item" />
						<Button v-if="column.key === 'cta' && row.status === 'Paid'" @click="openInvoicePDF(row)"
							class="hover:bg-gray-900 hover:text-white" icon-left="download" label="Download Invoice" />

						<Button v-if="column.key === 'cta' &&
							(row.status === 'Unpaid' || row.status === 'Overdue')
						" @click="openModal(row)"
							class="hover:bg-gray-900 hover:text-white flex flex-column items-center justify-center"
							icon-left="credit-card" label="Pay Now" />
					</ListRowItem>
				</ListRow>
			</ListView>
			<!-- <FeesPaymentDialog v-if="currentRow" :row="currentRow" :student="studentInfo" v-model="showPaymentDialog"
				@success="success()" /> -->
		</div>

		<div v-else>
			<MissingData message="No Fees found" />
		</div>
	</div>
	<div v-else class="flex flex-col items-center justify-center">
		<p class="text-lg font-bold text-gray-500">{{ __('Student Financial Status are only displayed for Students') }}
		</p>
	</div>
</template>

<script setup>

import {
	ListView,
	ListHeader,
	ListHeaderItem,
	ListRow,
	ListRowItem,
	Badge,
	createResource,
	Toast,
	FeatherIcon,
} from 'frappe-ui'
import { reactive, ref, inject } from 'vue'

// import FeesPaymentDialog from '@/components/FeesPaymentDialog.vue'
// import { studentStore } from '@/stores/student'
import MissingData from '@/components/MissingData.vue'
import { createToast } from '@/utils'
import { usersStore } from '../stores/user'


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

const tableData = reactive({
	rows: [],
	columns: [
		{
			label: __('Name'),
			key: 'name',
			width: 1,
		},

		{
			label: __('Customer'),
			key: 'customer',
			width: 1,
		},
		{
			label: __('Posting Date'),
			key: 'posting_date',
			width: 1,
		},
		{
			label: __('Total Amount'),
			key: 'total',
			width: 1,
		},
		{
			label: __('Outstanding Amount'),
			key: 'outstanding_amount',
			width: 1,
		},
		{
			label: __('Status'),
			key: 'status',
			width: 1,
		},
		{
			label: __('Invoice'),
			key: 'cta',
			width: 1,
		},
	],
})

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
		iconClasses: 'text-green-600',
	})
}
</script>