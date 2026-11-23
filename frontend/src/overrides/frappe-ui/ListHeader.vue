<!--
  frappe-ui 0.1.261's ListView header (src/components/ListView/ListHeader.vue) with a name
  on its select-all checkbox (decision 102 §9, WCAG 1.3.1/4.1.2). frappe-ui-overrides.js swaps it
  in for frappe-ui's own; keep it in step if frappe-ui is ever upgraded.
-->
<template>
  <div
    class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
    :style="{
      gridTemplateColumns: getGridTemplateColumns(
        list.columns,
        list.options.selectable,
      ),
    }"
  >
    <Checkbox
      v-if="list.options.selectable"
      class="cursor-pointer duration-300"
      :modelValue="list.allRowsSelected"
      :aria-label="__('Select all')"
      @click.stop="list.toggleAllRows"
    />
    <slot>
      <ListHeaderItem
        v-for="column in list.columns"
        :key="column.key"
        :item="column"
        @columnWidthUpdated="emit('columnWidthUpdated', column)"
      />
    </slot>
  </div>
</template>

<script setup>
import Checkbox from 'frappe-ui/src/components/Checkbox/Checkbox.vue'
import ListHeaderItem from 'frappe-ui/src/components/ListView/ListHeaderItem.vue'
import { getGridTemplateColumns } from 'frappe-ui/src/components/ListView/utils'
import { inject } from 'vue'

const emit = defineEmits(['columnWidthUpdated'])

const list = inject('list')
</script>
