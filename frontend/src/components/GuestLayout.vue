<template>
	<!-- A page a signed-out visitor opens from a link (the recommender form): no portal
	     navigation, which needs a sign-in, and still the main landmark the skip link targets. -->
	<main id="scrollContainer" tabindex="-1" class="min-h-screen overflow-auto bg-surface-white text-base text-ink-gray-9 focus:outline-none">
		<slot />
	</main>
</template>
