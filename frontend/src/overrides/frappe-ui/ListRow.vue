<!--
  frappe-ui 0.1.261's ListView row (src/components/ListView/ListRow.vue), fixed for
  decision 102 §9: linked rows showed no content, selectable rows nested a checkbox in a
  button, and the row checkbox had no name. vite.config.js swaps it in for frappe-ui's
  own; keep it in step if frappe-ui is ever upgraded.
-->
<template>
  <component
    :is="rowIsLink ? 'router-link' : 'div'"
    :class="[
      roundedClass,
      isSelected || isActive ? 'bg-surface-gray-2' : '',
      isHoverable ? 'cursor-pointer' : '',
      isHoverable
        ? isSelected || isActive
          ? 'hover:bg-surface-gray-3'
          : 'hover:bg-surface-menu-bar'
        : '',
    ]"
    class="flex flex-col transition-all duration-300 ease-in-out"
    v-bind="{
      to: rowIsLink ? list.options.getRowRoute(row) : undefined,
      onClick: linkInCell ? openRoute : onRowClick,
    }"
  >
    <component
      :is="innerTag"
      class="[all:unset] hover:[all:unset]"
      v-bind="innerAttrs"
    >
      <div
        class="grid items-center space-x-4 px-2"
        :style="{
          height: rowHeight,
          gridTemplateColumns: getGridTemplateColumns(
            list.columns,
            list.options.selectable,
          ),
        }"
      >
        <div
          v-if="list.options.selectable"
          class="w-fit pr-2 py-3 flex"
          @click.stop.prevent
          @dblclick.stop
        >
          <Checkbox
            :modelValue="isSelected"
            :aria-label="__('Select row')"
            class="cursor-pointer duration-300"
            @click.stop="handleCheckboxClick"
          />
        </div>
        <div
          v-for="(column, i) in list.columns"
          :key="column.key"
          :class="[
            alignmentMap[column.align],
            i == 0 ? 'text-ink-gray-9' : 'text-ink-gray-7',
          ]"
        >
          <!-- A selectable linked row links from its first cell, so the checkbox
               isn't inside the link (102 §9). -->
          <router-link
            v-if="linkInCell && i == 0"
            :to="list.options.getRowRoute(row)"
            class="block min-w-0 truncate rounded"
            @click.stop
          >
          <slot v-bind="{ idx: i, column, item: row[column.key], isActive }">
            <component
              v-if="list.slots.cell"
              :is="list.slots.cell"
              v-bind="{
                column,
                row,
                item: row[column.key],
                align: column.align,
              }"
            />
            <ListRowItem
              v-else
              :column="column"
              :row="row"
              :item="row[column.key]"
              :align="column.align"
            />
          </slot>
          </router-link>
          <template v-else>
          <slot v-bind="{ idx: i, column, item: row[column.key], isActive }">
            <component
              v-if="list.slots.cell"
              :is="list.slots.cell"
              v-bind="{
                column,
                row,
                item: row[column.key],
                align: column.align,
              }"
            />
            <ListRowItem
              v-else
              :column="column"
              :row="row"
              :item="row[column.key]"
              :align="column.align"
            />
          </slot>
          </template>
        </div>
      </div>
      <div
        v-if="!isLastRow"
        class="h-px border-t"
        :class="
          roundedClass === 'rounded' || roundedClass?.includes?.('rounded-b')
            ? 'mx-2 border-outline-gray-1'
            : 'border-t-[--surface-gray-2]'
        "
      />
    </component>
  </component>
</template>

<script setup>
import Checkbox from 'frappe-ui/src/components/Checkbox/Checkbox.vue'
import ListRowItem from 'frappe-ui/src/components/ListView/ListRowItem.vue'
import { alignmentMap, getGridTemplateColumns } from 'frappe-ui/src/components/ListView/utils'
import { computed, inject } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  row: {
    type: Object,
    required: true,
  },
})

const list = inject('list')

const isLastRow = computed(() => {
  if (!list.value.rows?.length) return false
  return (
    list.value.rows[list.value.rows.length - 1][list.value.rowKey] ===
    props.row[list.value.rowKey]
  )
})

const isSelected = computed(() => {
  return list.value.selections.has(props.row[list.value.rowKey])
})
const isActive = computed(
  () =>
    list.value.options.enableActive &&
    list.value.activeRow.value === props.row.name,
)

const isHoverable = computed(() => {
  return list.value.options.getRowRoute || list.value.options.onRowClick
})

const rowHeight = computed(() => {
  if (typeof list.value.options.rowHeight === 'number') {
    return `${list.value.options.rowHeight}px`
  }
  return list.value.options.rowHeight
})

const roundedClass = computed(() => {
  if (!isSelected.value) return 'rounded'
  const selections = [...list.value.selections]
  let groups = list.value.rows[0]?.group
    ? list.value.rows.map((k) => k.rows)
    : [list.value.rows]

  for (let rows of groups) {
    let currentIndex = rows.findIndex((k) => k == props.row)
    if (currentIndex === -1) continue
    let atBottom = !selections.includes(rows[currentIndex + 1]?.name)
    let atTop = !selections.includes(rows[currentIndex - 1]?.name)
    return (atBottom ? 'rounded-b ' : '') + (atTop ? 'rounded-t' : '')
  }
})

// The row's inner element (102 §9). frappe-ui renders a <template> element inside a
// linked row, which browsers never display, so the row's link had no content; and a
// selectable row put its checkbox inside a <button>, which a button can't contain.
// A linked row now wraps a plain div; a selectable row is a focusable div that opens
// with Enter or Space, as the button did; any other row keeps the button.
// A linked row is one link, unless it is selectable: then the first cell is the link
// and a click elsewhere on the row still opens it.
const rowIsLink = computed(() => Boolean(list.value.options.getRowRoute) && !list.value.options.selectable)
const linkInCell = computed(() => Boolean(list.value.options.getRowRoute) && Boolean(list.value.options.selectable))
const router = useRouter()
const openRoute = (event) => {
  onRowClick(event)
  router.push(list.value.options.getRowRoute(props.row))
}

const innerTag = computed(() => {
  if (list.value.options.getRowRoute) return 'div'
  return list.value.options.selectable ? 'div' : 'button'
})
const innerAttrs = computed(() => {
  if (list.value.options.getRowRoute) return {}
  if (!list.value.options.selectable) return { type: 'button' }
  if (!list.value.options.onRowClick) return {}
  return {
    tabindex: 0,
    onKeydown: (event) => {
      if (event.target !== event.currentTarget) return
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault()
        onRowClick(event)
      }
    },
  }
})

const onRowClick = (event) => {
  if (list.value.options.onRowClick)
    list.value.options.onRowClick(props.row, event)
  if (list.value.activeRow.value === props.row.name) {
    list.value.activeRow.value = null
  } else {
    list.value.activeRow.value = props.row.name
  }
}

const handleCheckboxClick = (event) => {
  const value = props.row[list.value.rowKey]
  if (event.shiftKey && !list.value.selections.has(value)) {
    const lastSelected = Array.from(list.value.selections).pop()
    const rows = list.value.rows.find((k) => k.group)
      ? list.value.rows.reduce((acc, curr) => acc.concat(curr.rows), [])
      : list.value.rows
    const lastIndex = rows.findIndex(
      (k) => lastSelected === k[list.value.rowKey],
    )
    const curIndex = rows.findIndex((k) => value === k[list.value.rowKey])
    const start = Math.min(lastIndex, curIndex)
    const end = Math.max(lastIndex, curIndex)
    for (let i = start; i <= end; i++) {
      list.value.selections.add(rows[i][list.value.rowKey])
    }
  } else {
    list.value.toggleRow(value)
  }
}
</script>
