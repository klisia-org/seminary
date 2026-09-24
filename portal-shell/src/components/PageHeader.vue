<!--
  The page frame (ADR 075).

  Replaces 68 hand-copied sticky-header class strings that had drifted into 9
  variants -- 20 of them carrying `border-outline-gray-1` and 48 not, so the
  divider was a different colour depending on which page you were on -- and
  gives one to the eight pages that had no header at all.

  It owns the frame and nothing else:
    #title / `title`  the page's identity, or <Breadcrumbs> when it has a parent
    #actions          page-level actions only (New, Compose, Back to <origin>)
    #tabs             the <PageTabs> row, inside the sticky frame

  Filters do NOT belong here -- they filter the content, not the page, and
  filter rows next to a title are what forced five of the nine variants into
  existence by wrapping badly at phone width. Put them in the body, above what
  they filter. The one exception is a single primary scope selector that decides
  what the whole page is about (Program Audit's enrollment, Partner's org).
-->
<template>
	<header
		class="sticky top-0 z-10 bg-surface-white"
		:class="{ 'border-b': !$slots.tabs }"
	>
		<div
			class="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5 sm:px-5"
		>
			<div class="flex min-w-0 items-center gap-2">
				<slot name="title">
					<h1 class="truncate text-xl font-bold text-ink-gray-8">{{ title }}</h1>
				</slot>
			</div>
			<div v-if="$slots.actions" class="flex items-center gap-2">
				<slot name="actions" />
			</div>
		</div>
		<!-- Tabs sit inside the sticky frame so the bar survives scrolling a long
		     queue; the row supplies its own border-b, so drop the header's. -->
		<slot name="tabs" />
	</header>
</template>

<script setup>
defineProps({
	title: { type: String, default: '' },
})
</script>
