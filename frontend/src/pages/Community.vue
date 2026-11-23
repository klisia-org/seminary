<template>
	<PageHeader>
		<template #title>
			<div class="min-w-0">
				<h1 class="truncate text-xl font-bold text-ink-gray-8">{{ __('Community') }}</h1>
				<p class="truncate text-sm text-ink-gray-5">
					{{ scopeLabel }}<template v-if="newCount"> · <b class="text-ink-gray-8">{{ __('{0} new').format(newCount) }}</b> {{ sinceLabel }}</template>
				</p>
			</div>
		</template>
		<template #actions>
			<Button v-if="canModerate" :label="__('Announce')" @click="openBroadcast" />
			<Button v-if="canModerate"
				:label="openFlags ? __('Moderation · {0}').format(openFlags) : __('Moderation')"
				@click="openModeration" />
			<Button v-if="cohorts.length" variant="solid" :label="__('New post')" @click="openCompose">
				<template #prefix><Plus class="h-4 w-4" /></template>
			</Button>
		</template>
	</PageHeader>

	<div class="mx-auto flex h-full w-full max-w-6xl gap-6 px-4 py-6">
		<!-- Rail: cohorts, then channels (decisions/101 section 5.1) -->
		<aside v-if="cohorts.length" class="hidden w-64 shrink-0 md:block">
			<div class="sticky top-20 flex flex-col gap-6">
				<section>
					<h2 class="mb-2 px-1 text-[11px] font-semibold uppercase tracking-wider text-ink-gray-5">{{ __('Cohorts') }}</h2>
					<div class="flex flex-col gap-1">
						<button type="button" class="flex items-center gap-2.5 rounded-lg border px-3 py-2 text-left"
							:class="selectedCohort === '' ? 'border-outline-gray-2 bg-surface-white shadow-sm' : 'border-transparent hover:bg-surface-gray-2'"
							@click="selectedCohort = ''">
							<span class="h-2.5 w-2.5 shrink-0 rounded-sm bg-surface-gray-7"></span>
							<span class="min-w-0 flex-1">
								<span class="block truncate text-sm font-medium text-ink-gray-9">{{ __('All my cohorts') }}</span>
								<span class="block truncate text-xs text-ink-gray-5">
									{{ cohorts.length === 1 ? __('1 cohort') : __('{0} cohorts').format(cohorts.length) }}
								</span>
							</span>
							<span v-if="totalNew" class="rounded-full bg-surface-gray-7 px-1.5 text-xs text-ink-white">{{ totalNew }}</span>
						</button>
						<div v-for="(c, i) in cohorts" :key="c.name">
							<button type="button" class="flex w-full items-center gap-2.5 rounded-lg border px-3 py-2 text-left"
								:class="selectedCohort === c.name ? 'border-outline-gray-2 bg-surface-white shadow-sm' : 'border-transparent hover:bg-surface-gray-2'"
								@click="selectedCohort = c.name">
								<span class="h-2.5 w-2.5 shrink-0 rounded-sm" :style="{ background: dotColor(i) }"></span>
								<span class="min-w-0 flex-1">
									<span class="block truncate text-sm font-medium text-ink-gray-9">{{ c.cohort_name }}</span>
									<span class="block truncate text-xs text-ink-gray-5">
										{{ [c.cohort_type, c.members === 1 ? __('1 member') : __('{0} members').format(c.members || 0)].filter(Boolean).join(' · ') }}
									</span>
								</span>
								<span v-if="c.new" class="rounded-full bg-surface-gray-7 px-1.5 text-xs text-ink-white">{{ c.new }}</span>
							</button>
							<div v-if="selectedCohort === c.name" class="mt-1 flex gap-3 pl-8 text-xs">
								<button type="button" class="text-ink-gray-6 hover:text-ink-gray-9" @click="openMembers">{{ __('Members') }}</button>
								<button type="button" class="text-ink-gray-6 hover:text-ink-gray-9" @click="meetingsRef?.openList()">{{ __('Meetings') }}</button>
							</div>
						</div>
					</div>
				</section>

				<section>
					<h2 class="mb-2 px-1 text-[11px] font-semibold uppercase tracking-wider text-ink-gray-5">{{ __('Channels') }}</h2>
					<div class="flex flex-col gap-0.5">
						<button type="button" class="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-left text-sm"
							:class="channelFilter === '' ? 'border-outline-gray-2 bg-surface-white font-medium text-ink-gray-9 shadow-sm' : 'border-transparent text-ink-gray-7 hover:bg-surface-gray-2'"
							@click="setChannel('')">
							<span class="flex-1">{{ __('All channels') }}</span>
						</button>
						<button v-for="ch in channels" :key="ch.name" type="button"
							class="flex items-center gap-2 rounded-lg border px-3 py-1.5 text-left text-sm"
							:class="channelFilter === ch.name ? 'border-outline-gray-2 bg-surface-white font-medium text-ink-gray-9 shadow-sm' : 'border-transparent text-ink-gray-7 hover:bg-surface-gray-2'"
							@click="setChannel(ch.name)">
							<span class="flex-1 truncate">{{ ch.channel_name }}</span>
							<span v-if="unread[ch.name]" class="rounded-full bg-surface-gray-7 px-1.5 text-xs text-ink-white">{{ unread[ch.name] }}</span>
							<span v-else-if="channelCounts[ch.name]" class="text-xs text-ink-gray-5">{{ channelCounts[ch.name] }}</span>
						</button>
					</div>
				</section>
			</div>
		</aside>

		<div class="flex min-w-0 flex-1 flex-col">
			<!-- Phones: the rail folds into selectors above the feed (section 5.5). -->
			<div v-if="cohorts.length" class="mb-3 flex flex-wrap gap-2 md:hidden">
				<select :aria-label="__('Cohort')" v-model="selectedCohort"
					class="min-w-0 flex-1 rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm text-ink-gray-8">
					<option value="">{{ __('All my cohorts') }}</option>
					<option v-for="c in cohorts" :key="c.name" :value="c.name">{{ c.cohort_name }}</option>
				</select>
				<Button v-if="selectedCohort" :label="__('Members')" @click="openMembers" />
			</div>

			<!-- pending invitations banner -->
			<div v-if="pendingRes.data?.length" class="mb-4 flex flex-col gap-2">
				<div v-for="inv in pendingRes.data" :key="inv.membership"
					class="flex flex-wrap items-center gap-3 rounded-md border border-outline-gray-3 bg-surface-gray-1 px-3 py-2 text-sm">
					<Mail class="h-4 w-4 shrink-0 text-ink-gray-6" />
					<span class="text-ink-gray-8">
						{{ __('You’re invited to') }} <b>{{ inv.cohort_name }}</b><span v-if="inv.invited_by"> {{ __('by') }} {{ inv.invited_by }}</span>.
					</span>
					<div class="ml-auto flex gap-2">
						<Button variant="solid" :label="__('Accept')" :loading="acceptInviteRes.loading" @click="acceptInvite(inv)" />
						<Button :label="__('Decline')" :loading="declineInviteRes.loading" @click="declineInvite(inv)" />
					</div>
				</div>
			</div>

			<div v-if="!cohorts.length && !pendingRes.data?.length && !feed.data?.length"
				class="mt-16 text-center text-ink-gray-5">
				{{ __('You are not part of any cohort yet.') }}
			</div>

			<template v-else>
				<CohortMeetings v-if="selectedCohort" ref="meetingsRef" :key="selectedCohort"
					:cohort="selectedCohort" :cohort-name="selectedCohortName" />

				<!-- One filter row: search, passage, channel, view (section 5.3) -->
				<div class="mb-3 flex flex-wrap items-center gap-2">
					<div class="flex min-w-[12rem] flex-1 items-center gap-2 rounded-md border border-outline-gray-2 bg-surface-white px-2">
						<Search class="h-4 w-4 text-ink-gray-4" />
						<input v-model="searchQuery" type="text" :placeholder="__('Search posts or people')" :aria-label="__('Search posts or people')"
							class="w-full border-0 bg-transparent px-0 py-1.5 text-sm text-ink-gray-8 shadow-none focus:outline-none focus:ring-0" />
						<button :aria-label="__('Clear search')" v-if="searchQuery" @click="searchQuery = ''"><X class="h-4 w-4 text-ink-gray-4" /></button>
					</div>
					<CommunityPassagePicker v-model="passageFilter" :cohort="selectedCohort" />
					<select :aria-label="__('Channel')" v-model="channelFilter"
						class="rounded-md border px-2 py-1.5 text-sm"
						:class="channelFilter ? 'border-outline-gray-4 bg-surface-gray-3 text-ink-gray-9' : 'border-outline-gray-2 bg-surface-white text-ink-gray-7'">
						<option value="">{{ __('Channel: all') }}</option>
						<option v-for="ch in channels" :key="ch.name" :value="ch.name">{{ __('Channel: {0}').format(ch.channel_name) }}</option>
					</select>
					<div class="flex rounded-md bg-surface-gray-2 p-0.5 text-sm">
						<button v-for="v in views" :key="v.value" type="button" class="rounded px-3 py-1"
							:class="view === v.value ? 'bg-surface-white font-medium text-ink-gray-9 shadow-sm' : 'text-ink-gray-6 hover:text-ink-gray-8'"
							@click="view = v.value">{{ v.label }}</button>
					</div>
				</div>

				<div v-if="searchActive" class="mb-3 text-sm text-ink-gray-6">
					<span v-if="searchRes.loading">{{ __('Searching…') }}</span>
					<span v-else>{{ posts.length === 1 ? __('1 result') : __('{0} results').format(posts.length) }}</span>
				</div>
				<div v-else-if="passageFilter || channelFilter" class="mb-3 text-sm text-ink-gray-6">
					<b class="text-ink-gray-9">{{ posts.length === 1 ? __('1 post') : __('{0} posts').format(posts.length) }}</b>
					<span v-if="channelFilter"> {{ __('in {0}').format(channelName(channelFilter)) }}</span>
					<span v-if="passageFilter"> {{ __('about {0}').format(passageFilter.label) }}</span>
				</div>

				<!-- prayer: active vs answered -->
				<div v-if="isPrayerChannel && view !== 'saved'" class="mb-3 flex gap-2 text-sm">
					<button class="rounded-md px-3 py-1"
						:class="prayerView === 'active' ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-6'"
						@click="setPrayerView('active')">{{ __('Active') }}</button>
					<button class="rounded-md px-3 py-1"
						:class="prayerView === 'answered' ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-6'"
						@click="setPrayerView('answered')">{{ __('Answered') }}</button>
				</div>

				<!-- feed -->
				<div class="flex flex-col gap-4">
					<div v-if="feed.loading && !posts.length" class="py-10 text-center text-ink-gray-5">{{ __('Loading…') }}</div>
					<div v-else-if="!posts.length" class="py-10 text-center text-ink-gray-5">
						{{ view === 'saved' ? __('Nothing saved yet.') : view === 'mine' ? __('You have not posted yet.') : __('No posts yet. Be the first to share.') }}
					</div>

					<template v-for="section in sections" :key="section.key">
					<h3 v-if="section.label && section.posts.length" class="mt-2 text-xs font-semibold uppercase tracking-wider text-ink-gray-5">
						{{ section.label }}
					</h3>
					<template v-for="(post, i) in section.posts" :key="post.name">
					<article class="rounded-xl border border-outline-gray-2 bg-surface-white p-5">
						<header class="mb-2 flex items-center justify-between gap-2">
							<div class="flex min-w-0 items-center gap-2 text-sm">
								<span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-gray-2 text-xs font-semibold text-ink-gray-7">
									{{ initials(post.author_name || post.author) }}
								</span>
								<span class="truncate font-medium text-ink-gray-9">{{ post.author_name || post.author }}</span>
								<template v-if="post.on_behalf_of">
									<a v-if="post.on_behalf_of.route" :href="post.on_behalf_of.route"
										class="text-ink-gray-7 underline-offset-2 hover:underline">· {{ post.on_behalf_of.label }}</a>
									<span v-else class="text-ink-gray-7">· {{ post.on_behalf_of.label }}</span>
								</template>
								<span v-if="post.author_membership === 'outside'"
									class="rounded bg-surface-gray-2 px-1.5 py-0.5 text-xs text-ink-gray-6">{{ __('guest') }}</span>
								<component :is="visIcon(post.visibility)" class="h-3.5 w-3.5 shrink-0 text-ink-gray-5" />
								<span class="whitespace-nowrap text-ink-gray-5">· {{ timeAgo(post.creation) }}</span>
							</div>
							<div class="flex shrink-0 items-center gap-2">
								<span v-if="post.new_comments" class="rounded-full bg-surface-red-5 px-1.5 py-0.5 text-xs text-ink-white">
									{{ post.new_comments }} {{ __('new') }}
								</span>
								<span v-if="post.prayer_answered" class="flex items-center gap-1 rounded bg-surface-gray-2 px-2 py-0.5 text-xs text-ink-gray-7">
									<Check class="h-3.5 w-3.5" />{{ __('Answered') }}
								</span>
								<span v-if="post.status === 'pinned'" class="flex items-center gap-1 text-xs text-ink-gray-5">
									<Pin class="h-3.5 w-3.5" />{{ __('Pinned') }}
								</span>
								<span class="hidden rounded-md bg-surface-gray-2 px-2 py-0.5 text-xs text-ink-gray-7 sm:inline">{{ channelName(post.channel) }}</span>
							</div>
						</header>

						<h2 v-if="post.title" class="mb-1 text-lg font-semibold text-ink-gray-9">{{ post.title }}</h2>
						<SafeHtml class="prose-sm max-w-none text-ink-gray-8" :html="post.content" />

						<!-- prayer testimony -->
						<div v-if="post.prayer_answered && post.prayer_answer_note"
							class="mt-2 rounded-md border-l-2 border-outline-gray-3 bg-surface-gray-1 p-2 text-sm text-ink-gray-7">
							<span class="font-medium">{{ __('Answered') }}<span v-if="post.prayer_answered_on"> · {{ post.prayer_answered_on }}</span>:</span>
							{{ post.prayer_answer_note }}
						</div>

						<!-- tags -->
						<div v-if="post.topics?.length || (post.scripture?.length && post.channel_kind !== 'bible_passage')" class="mt-2 flex flex-wrap gap-1.5">
							<span v-for="t in post.topics" :key="'t' + t"
								class="rounded border border-outline-gray-2 px-2 py-0.5 text-xs text-ink-gray-6">#{{ t }}</span>
							<template v-if="post.channel_kind !== 'bible_passage'">
								<button v-for="s in post.scripture" :key="'s' + s.resolved_ref"
									class="flex items-center gap-1 rounded border border-outline-gray-2 px-2 py-0.5 text-xs text-ink-gray-7 hover:bg-surface-gray-2"
									@click="openPassage(s)">
									<BookOpen class="h-3 w-3" />{{ s.display }}
								</button>
							</template>
						</div>

						<!-- sermon lab: video + timestamped comments -->
						<SermonLabPlayer v-if="post.channel_kind === 'video_timestamp' && post.video_url"
							:post-name="post.name" :video-url="post.video_url" :can-comment="true" />

						<!-- exegetical: the passage folds behind "Show passage" (section 5.4) -->
						<template v-else-if="post.channel_kind === 'bible_passage' && post.scripture?.length">
							<div class="mt-3 flex items-center gap-2 rounded-lg border border-outline-gray-2 bg-surface-gray-1 px-3 py-2 text-sm">
								<BookOpen class="h-4 w-4 shrink-0 text-ink-gray-6" />
								<span class="min-w-0 flex-1 truncate font-medium text-ink-gray-8">{{ post.scripture.map((s) => s.display).join('; ') }}</span>
								<button type="button" class="whitespace-nowrap text-ink-gray-7 hover:text-ink-gray-9" @click="toggleReader(post)">
									{{ openReaders[post.name] ? __('Hide passage') : __('Show passage') }}
								</button>
							</div>
							<ExegeticalReader v-if="openReaders[post.name]"
								:post-name="post.name" :scripture="post.scripture" :can-comment="true" />
						</template>

						<!-- reactions: the post's channel's own, with counts -->
						<div class="mt-3 flex flex-wrap items-center gap-1.5">
							<button v-for="rt in reactionsFor(post)" :key="rt.name"
								class="flex items-center gap-1 rounded-full border px-2 py-0.5 text-sm"
								:class="reactionMine(post, rt.name) ? 'border-outline-gray-4 bg-surface-gray-2' : 'border-outline-gray-2'"
								:title="reactionTitle(post, rt)"
								@click="react(post, rt.name)">
								<span>{{ rt.glyph }}</span>
								<span v-if="reactionCount(post, rt.name)" class="text-xs text-ink-gray-6">{{ reactionCount(post, rt.name) }}</span>
							</button>
							<button v-if="!['video_timestamp', 'bible_passage'].includes(post.channel_kind)"
								class="ml-2 flex items-center gap-1 text-sm text-ink-gray-6" @click="toggleThread(post)">
								<MessageCircle class="h-4 w-4" />{{ post.comment_count || 0 }}
							</button>
							<button v-if="post.channel_kind === 'prayer' && post.is_mine && !post.prayer_answered"
								class="ml-2 text-sm text-ink-gray-6 hover:text-ink-gray-9" @click="openAnswer(post)">
								{{ __('Mark answered') }}
							</button>
							<button v-if="post.channel_kind === 'prayer' && post.is_mine && post.prayer_answered"
								class="ml-2 text-sm text-ink-gray-6 hover:text-ink-gray-9" @click="reopen(post)">
								{{ __('Reopen') }}
							</button>
							<button class="ml-auto text-ink-gray-4 hover:text-ink-gray-7"
								:title="post.saved ? __('Unsave') : __('Save')" @click="toggleSave(post)">
								<component :is="post.saved ? BookmarkCheck : Bookmark" class="h-3.5 w-3.5"
									:class="post.saved ? 'text-ink-gray-8' : ''" />
							</button>
							<button class="text-ink-gray-4 hover:text-ink-gray-7" :title="__('Report')"
								@click="openReport('Cohort Post', post.name)">
								<Flag class="h-3.5 w-3.5" />
							</button>
							<template v-if="canModerate">
								<button class="text-ink-gray-5 hover:text-ink-gray-9"
									:title="post.status === 'pinned' ? __('Unpin') : __('Pin')"
									@click="moderatePost(post, post.status === 'pinned' ? 'published' : 'pinned')">
									<Pin class="h-3.5 w-3.5" />
								</button>
								<button class="text-ink-gray-5 hover:text-ink-red-4" :title="__('Block')"
									@click="moderatePost(post, 'blocked')">
									<Ban class="h-3.5 w-3.5" />
								</button>
							</template>
							<template v-if="post.is_mine">
								<button class="text-ink-gray-5 hover:text-ink-gray-9" :title="__('Edit')" @click="openEdit(post)">
									<Pencil class="h-3.5 w-3.5" />
								</button>
								<button class="text-ink-gray-5 hover:text-ink-red-4" :title="__('Delete')" @click="confirmDelete(post)">
									<Trash2 class="h-3.5 w-3.5" />
								</button>
							</template>
						</div>
					<!-- thread -->
					<div v-if="expandedPost === post.name" class="mt-3 border-t border-outline-gray-1 pt-3">
						<div v-if="thread.loading" class="text-sm text-ink-gray-5">{{ __('Loading…') }}</div>
						<div v-else class="flex flex-col gap-3">
							<div v-for="c in threadComments" :key="c.name"
								:style="{ marginLeft: Math.min(c.depth, 4) * 16 + 'px' }">
								<div class="text-sm">
									<span class="font-medium text-ink-gray-9">{{ c.author_name || c.author }}</span>
									<span v-if="c.is_private" class="ml-1 inline-flex items-center gap-0.5 rounded bg-surface-gray-2 px-1.5 text-xs text-ink-gray-6"><Lock class="h-3 w-3" />{{ __('private') }}</span>
									<span class="text-ink-gray-5">· {{ timeAgo(c.creation) }}</span>
								</div>
								<SafeHtml class="prose-sm max-w-none text-ink-gray-8" :html="c.content" />
								<button class="text-xs text-ink-gray-5" @click="replyTo = c">{{ __('Reply') }}</button>
							</div>

							<!-- reply box -->
							<div class="mt-2">
								<div v-if="replyTo" class="mb-1 flex items-center gap-2 text-xs text-ink-gray-5">
									{{ __('Replying to') }} {{ replyTo.author_name || replyTo.author }}
									<button :aria-label="__('Cancel reply')" @click="replyTo = null"><X class="h-3 w-3" /></button>
								</div>
								<div class="flex gap-2">
									<Input v-model="replyText" type="text" :placeholder="__('Write a reply…')" :aria-label="__('Write a reply…')" class="flex-1"
										@keyup.enter="submitReply(post)" />
									<Button :aria-label="__('Send reply')" variant="solid" :loading="addComment.loading" @click="submitReply(post)">
										<Send class="h-4 w-4" />
									</Button>
								</div>
									<label class="mt-1 flex items-center gap-1 text-xs text-ink-gray-5"><input type="checkbox" v-model="replyPrivate" class="rounded" /><Lock class="h-3 w-3" />{{ __('Private — only the author and leaders will see this') }}</label>
							</div>

							<!-- linked reflections -->
							<div v-if="thread.data?.post?.linked_posts?.length" class="mt-2">
								<div class="mb-1 text-xs font-medium text-ink-gray-6">{{ __('Linked reflections') }}</div>
								<ul class="flex flex-col gap-1">
									<li v-for="l in thread.data.post.linked_posts" :key="l.name" class="text-sm text-ink-gray-8">
										{{ l.title || l.name }}
										<span class="text-xs text-ink-gray-5">· {{ l.relation_type }}</span>
									</li>
								</ul>
							</div>
							<div v-if="post.is_mine" class="mt-2 flex items-center gap-2">
								<Input v-model="linkTarget" type="text" :placeholder="__('Link a post by ID (e.g. a journal)')" :aria-label="__('Link a post by ID (e.g. a journal)')" class="flex-1" />
								<Button :label="__('Link')" :loading="linkPost.loading" @click="submitLink(post)" />
							</div>

							<!-- related across channels -->
							<div v-if="related.data?.length" class="mt-2 rounded-md bg-surface-gray-1 p-2">
								<div class="mb-1 text-xs font-medium text-ink-gray-6">{{ __('Related across channels') }}</div>
								<ul class="flex flex-col gap-1">
									<li v-for="r in related.data" :key="r.name" class="flex items-center gap-2 text-sm text-ink-gray-8">
										<span class="truncate">{{ r.title || plain(r.content) }}</span>
										<span class="whitespace-nowrap text-xs text-ink-gray-5">· {{ r.channel_kind }}</span>
									</li>
								</ul>
							</div>
						</div>
					</div>
				</article>
					<div v-if="section.key === 'all' && i === lastNewIndex && i < section.posts.length - 1"
						class="my-1 flex items-center gap-2 text-xs font-medium text-ink-red-4">
						<div class="h-px flex-1 bg-surface-red-3"></div>{{ __('New') }}<div class="h-px flex-1 bg-surface-red-3"></div>
					</div>
					</template>
					</template>

					<!-- A filtered list ends with what else it is hiding (section 5.4). -->
					<div v-if="otherChannelPosts.length"
						class="flex flex-wrap items-center gap-3 rounded-xl border border-dashed border-outline-gray-3 px-4 py-3 text-sm text-ink-gray-7">
						<span class="flex-1">
							{{ otherChannelPosts.length === 1
								? __('1 more post about {0} in {1}.').format(passageFilter.label, otherChannelNames)
								: __('{0} more posts about {1} in {2}.').format(otherChannelPosts.length, passageFilter.label, otherChannelNames) }}
						</span>
						<Button :label="__('Show all {0} posts').format(passageFilter.label)" @click="channelFilter = ''" />
					</div>
				</div>
			</template>

		<!-- compose dialog (decisions/101 section 5.6) -->
		<Dialog v-model="showCompose" :options="{ title: __('New post'), size: 'xl' }">
			<template #body-content>
				<div class="flex flex-col gap-4">
					<div v-if="cohorts.length > 1">
						<div class="mb-1.5 text-sm font-medium text-ink-gray-7">{{ __('Cohort') }}</div>
						<div class="grid grid-cols-1 gap-2 sm:grid-cols-3">
							<button v-for="(c, i) in cohorts" :key="c.name" type="button"
								class="rounded-lg border px-3 py-2 text-left"
								:class="draft.cohort === c.name ? 'border-outline-gray-5 bg-surface-gray-1 ring-1 ring-outline-gray-5' : 'border-outline-gray-2 hover:bg-surface-gray-1'"
								:aria-pressed="draft.cohort === c.name"
								@click="draft.cohort = c.name">
								<span class="flex items-center gap-2">
									<span class="h-2.5 w-2.5 shrink-0 rounded-sm" :style="{ background: dotColor(i) }"></span>
									<span class="truncate text-sm font-medium text-ink-gray-9">{{ c.cohort_name }}</span>
								</span>
								<span class="mt-0.5 block truncate pl-[1.125rem] text-xs text-ink-gray-5">
									{{ [c.cohort_type, c.members || 0].filter((v) => v !== '' && v != null).join(' · ') }}
								</span>
							</button>
						</div>
					</div>
					<div>
						<div class="mb-1.5 text-sm text-ink-gray-7">
							<span class="font-medium">{{ __('Channel') }}</span>
							<span v-if="composeCohort" class="text-ink-gray-5"> — {{ __('channels for {0}').format(composeCohort.cohort_name) }}</span>
						</div>
						<div class="flex flex-wrap gap-2">
							<button v-for="ch in composeChannels" :key="ch.name" type="button"
								class="rounded-full border px-3.5 py-1.5 text-sm"
								:class="draft.channel === ch.name ? 'border-transparent bg-surface-gray-7 font-medium text-ink-white' : 'border-outline-gray-2 text-ink-gray-8 hover:bg-surface-gray-2'"
								:aria-pressed="draft.channel === ch.name"
								@click="draft.channel = ch.name">{{ ch.channel_name }}</button>
						</div>
					</div>
					<label class="block">
						<span class="mb-1.5 block text-sm text-ink-gray-7"><span class="font-medium">{{ __('Title') }}</span> <span class="text-ink-gray-5">({{ __('optional') }})</span></span>
						<Input v-model="draft.title" type="text" :placeholder="__('A short headline helps people scan the feed')" />
					</label>
					<label v-if="composeChannelKind === 'video_timestamp'" class="block">
						<span class="mb-1.5 block text-sm font-medium text-ink-gray-7">{{ __('YouTube link') }}</span>
						<div class="flex items-center gap-2">
							<VideoIcon class="h-4 w-4 text-ink-gray-5" />
							<Input v-model="draft.video_url" type="text" :placeholder="__('Required for this channel')" class="flex-1" />
						</div>
					</label>
					<div>
						<div class="mb-1.5 text-sm font-medium text-ink-gray-7">{{ __('Post') }}</div>
						<!-- :teleport="false" keeps the editor's menu inside the Dialog -->
						<RichTextEditor :key="'compose-' + composeKey" :content="draft.content" :teleport="false"
							:placeholder="__('Share a question, insight or request…')" @change="(v) => (draft.content = v)" />
					</div>
					<div>
						<div class="mb-1.5 text-sm text-ink-gray-7">
							<span class="font-medium">{{ __('Topics') }}</span>
							<span class="text-ink-gray-5"> — {{ __('press Enter or comma after each') }}</span>
						</div>
						<CommunityTopicInput v-model="draft.topics" />
					</div>
					<label for="community-draft-scripture" class="block">
						<span class="mb-1.5 block text-sm text-ink-gray-7"><span class="font-medium">{{ __('Scripture') }}</span> <span class="text-ink-gray-5">({{ __('optional') }})</span></span>
						<TextInput id="community-draft-scripture" v-model="draft.scripture" type="text" size="md" :placeholder="__('e.g. Rom 8:28; Jn 3:16-18')">
							<template #prefix><BookOpen class="h-4 w-4 text-ink-gray-5" /></template>
						</TextInput>
					</label>
					<!-- Scoped type-ahead: only people the author already shares a
					     cohort with, so the picker never promises an unreachable
					     recipient and lineage size never matters. -->
					<div v-if="draft.visibility === 'direct'" class="relative">
						<label for="community-recipient" class="mb-1.5 block text-sm font-medium text-ink-gray-7">{{ __('To') }}</label>
						<Input id="community-recipient" v-model="recipientQuery" type="text"
							:placeholder="__('Search someone in your cohorts…')"
							@input="searchRecipients" />
						<div v-if="draft.direct_recipient" class="mt-1 text-xs text-ink-gray-6">
							{{ __('To: {0}').format(recipientLabel) }}
						</div>
						<ul v-if="recipientResults.length"
							class="absolute z-20 mt-1 max-h-48 w-full overflow-y-auto rounded-md border border-outline-gray-2 bg-surface-white shadow">
							<li v-for="r in recipientResults" :key="r.person">
								<button type="button" class="flex w-full flex-col px-3 py-1.5 text-left text-sm hover:bg-surface-gray-2"
									@click="pickRecipient(r)">
									<span class="text-ink-gray-8">{{ r.full_name }}</span>
									<span class="text-xs text-ink-gray-5">{{ r.cohort_name }}</span>
								</button>
							</li>
						</ul>
					</div>
				</div>
			</template>
			<template #actions>
				<div class="flex flex-wrap items-center justify-between gap-2">
					<div class="relative flex items-center gap-2" @focusout="onVisFocusOut">
						<span class="text-sm text-ink-gray-6">{{ __('Who can see this:') }}</span>
						<button type="button"
							class="flex items-center gap-1.5 rounded-lg border border-outline-gray-3 px-3 py-1.5 text-sm font-medium text-ink-gray-8 hover:bg-surface-gray-2"
							:aria-expanded="visMenuOpen" aria-haspopup="listbox"
							@click="visMenuOpen = !visMenuOpen">
							<component :is="visIcon(draft.visibility)" class="h-4 w-4" />
							{{ currentVis?.label }}
							<ChevronUp class="h-3.5 w-3.5 text-ink-gray-5 transition-transform" :class="visMenuOpen ? '' : 'rotate-180'" />
						</button>
						<!-- ADR 076: Mentors is offered only to those who may use it.
						     The server enforces the same test. -->
						<ul v-if="visMenuOpen" role="listbox"
							class="absolute bottom-full left-0 z-30 mb-2 w-[22rem] max-w-[calc(100vw-3rem)] rounded-xl border border-outline-gray-2 bg-surface-white p-1.5 shadow-xl">
							<li v-for="o in visOptions" :key="o.value">
								<button type="button" role="option" :aria-selected="draft.visibility === o.value"
									class="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left"
									:class="draft.visibility === o.value ? 'bg-surface-gray-2' : 'hover:bg-surface-gray-1'"
									@click="draft.visibility = o.value; visMenuOpen = false">
									<span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-surface-gray-2">
										<component :is="visIcon(o.value)" class="h-4 w-4 text-ink-gray-7" />
									</span>
									<span class="min-w-0 flex-1">
										<span class="block text-sm font-medium text-ink-gray-9">{{ o.label }}</span>
										<span class="block truncate text-xs text-ink-gray-5">{{ o.hint }}</span>
									</span>
									<Check v-if="draft.visibility === o.value" class="h-4 w-4 shrink-0 text-ink-gray-8" />
								</button>
							</li>
						</ul>
					</div>
					<div class="flex gap-2">
						<Button :label="__('Cancel')" @click="showCompose = false" />
						<Button variant="solid" :label="__('Post')" :loading="createPost.loading" @click="submitPost" />
					</div>
				</div>
			</template>
		</Dialog>

		<!-- mark answered dialog -->
		<Dialog v-model="showAnswer" :options="{ title: __('Mark prayer answered') }">
			<template #body-content>
				<textarea v-model="answerNote" rows="3"
					class="w-full rounded-md border border-outline-gray-2 bg-surface-white p-2 text-sm text-ink-gray-8"
					:placeholder="__('Share how it was answered (optional)')" :aria-label="__('Share how it was answered (optional)')"></textarea>
			</template>
			<template #actions>
				<div class="flex justify-end gap-2">
					<Button :label="__('Cancel')" @click="showAnswer = false" />
					<Button variant="solid" :label="__('Mark answered')" :loading="markAnswered.loading" @click="confirmAnswer" />
				</div>
			</template>
		</Dialog>

		<!-- edit post dialog -->
		<Dialog v-model="showEdit" :options="{ title: __('Edit post'), size: 'lg' }">
			<template #body-content>
				<div class="flex flex-col gap-3">
					<Input v-model="editDraft.title" type="text" :placeholder="__('Title (optional)')" :aria-label="__('Title (optional)')" />
					<div v-if="editDraft.channel_kind === 'video_timestamp'" class="flex items-center gap-2">
						<VideoIcon class="h-4 w-4 text-ink-gray-5" />
						<Input v-model="editDraft.video_url" type="text" :placeholder="__('YouTube link')" :aria-label="__('YouTube link')" class="flex-1" />
					</div>
					<div class="flex items-center gap-2">
						<label for="community-edit-visibility" class="text-sm text-ink-gray-6">{{ __('Visibility') }}</label>
						<select id="community-edit-visibility" v-model="editDraft.visibility"
							class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm">
							<option value="cohort_only">{{ __('Cohort only') }}</option>
							<option value="portal_users">{{ __('Whole community') }}</option>
							<option value="private">{{ __('Only me') }}</option>
						</select>
					</div>
					<CommunityTopicInput v-model="editDraft.topics" />
					<Input v-model="editDraft.scripture" type="text"
						:placeholder="__('Scripture, e.g. Jn 3:16-18; Rom 8:28')" :aria-label="__('Scripture, e.g. Jn 3:16-18; Rom 8:28')" />
					<RichTextEditor :key="'edit-' + editKey" :content="editDraft.content" :teleport="false"
						:placeholder="__('Share something…')" @change="(v) => (editDraft.content = v)" />
				</div>
			</template>
			<template #actions>
				<div class="flex justify-end gap-2">
					<Button :label="__('Cancel')" @click="showEdit = false" />
					<Button variant="solid" :label="__('Save')" :loading="editPostRes.loading" @click="submitEdit" />
				</div>
			</template>
		</Dialog>

		<!-- message leaders (Inbox broadcast) -->
		<Dialog v-model="showBroadcast" :options="{ title: __('Message leaders') }">
			<template #body-content>
				<div class="flex flex-col gap-3">
					<Input v-model="broadcastSubject" type="text" :placeholder="__('Subject')" :aria-label="__('Subject')" />
					<textarea v-model="broadcastMessage" rows="4"
						class="w-full rounded-md border border-outline-gray-2 bg-surface-white p-2 text-sm text-ink-gray-8"
						:placeholder="__('Message to the leaders you oversee…')" :aria-label="__('Message to the leaders you oversee…')"></textarea>
					<label class="flex items-center gap-1 text-sm text-ink-gray-6">
						<input type="checkbox" v-model="broadcastEmail" class="rounded" />{{ __('Also send by email') }}
					</label>
					<p class="text-xs text-ink-gray-4">{{ __('Goes to each leader’s Community inbox.') }}</p>
				</div>
			</template>
			<template #actions>
				<div class="flex justify-end gap-2">
					<Button :label="__('Cancel')" @click="showBroadcast = false" />
					<Button variant="solid" :label="__('Send')" :loading="broadcastRes.loading" @click="submitBroadcast" />
				</div>
			</template>
		</Dialog>

		<!-- split cohort (transfer members) -->
		<Dialog v-model="showSplit" :options="{ title: __('Split cohort'), size: '3xl' }">
			<template #body-content>
				<div class="flex flex-col gap-3">
					<Input v-model="splitName" type="text" :placeholder="__('New cohort name')" :aria-label="__('New cohort name')" />
					<div class="grid grid-cols-2 gap-3">
						<div class="rounded-md border border-outline-gray-2 p-2">
							<div class="mb-1 text-xs font-medium text-ink-gray-6">{{ __('Stays in original') }}</div>
							<ul class="flex flex-col gap-1">
								<li v-for="m in splitOriginal" :key="m.person"
									class="flex items-center justify-between gap-2 rounded px-1 py-0.5 text-sm hover:bg-surface-gray-1">
									<span class="truncate text-ink-gray-8">{{ m.name }}</span>
									<button class="font-semibold text-ink-gray-5 hover:text-ink-gray-9" :title="__('Move to new cohort')"
										@click="moveToNew(m)">»</button>
								</li>
								<li v-if="!splitOriginal.length" class="text-xs text-ink-gray-4">{{ __('None') }}</li>
							</ul>
						</div>
						<div class="rounded-md border border-outline-gray-2 p-2">
							<div class="mb-1 text-xs font-medium text-ink-gray-6">{{ __('Moves to new cohort') }}</div>
							<ul class="flex flex-col gap-1">
								<li v-for="m in splitMoving" :key="m.person"
									class="flex items-center gap-2 rounded px-1 py-0.5 text-sm hover:bg-surface-gray-1">
									<button class="font-semibold text-ink-gray-5 hover:text-ink-gray-9" :title="__('Move back')"
										@click="moveToOriginal(m)">«</button>
									<span class="mr-auto truncate text-ink-gray-8">{{ m.name }}</span>
									<button class="rounded px-1.5 py-0.5 text-xs"
										:class="splitLeader === m.person ? 'bg-surface-gray-3 text-ink-gray-9' : 'text-ink-gray-5 hover:text-ink-gray-9'"
										@click="splitLeader = m.person">
										{{ splitLeader === m.person ? __('Leader ✓') : __('Make leader') }}
									</button>
								</li>
								<li v-if="!splitMoving.length" class="text-xs text-ink-gray-4">{{ __('Move members here with »') }}</li>
							</ul>
						</div>
					</div>
				</div>
			</template>
			<template #actions>
				<div class="flex justify-end gap-2">
					<Button :label="__('Cancel')" @click="showSplit = false" />
					<Button variant="solid" :label="__('Create split')" :loading="splitRes.loading" @click="submitSplit" />
				</div>
			</template>
		</Dialog>

		<!-- passage text popover -->
		<Dialog v-model="showPassage" :options="{ title: passageRes.data?.reference || __('Passage') }">
			<template #body-content>
				<div v-if="passageRes.loading" class="py-4 text-center text-sm text-ink-gray-5">{{ __('Loading…') }}</div>
				<p v-else class="whitespace-pre-line text-sm leading-relaxed text-ink-gray-8">
					{{ passageRes.data?.text || __('Passage text unavailable.') }}
				</p>
			</template>
		</Dialog>

		<!-- my cohort -->
		<Dialog v-model="showMembers" :options="{ title: membersTitle, size: 'xl' }">
			<template #body-content>
				<div class="flex flex-col gap-3">
					<div v-if="membersRes.data?.is_leader" class="flex flex-col gap-2 rounded-md border border-outline-gray-2 p-2">
						<div class="flex items-center justify-between">
							<span class="text-xs font-medium text-ink-gray-6">{{ __('Invite someone') }}</span>
							<Button v-if="membersRes.data?.allow_split" variant="subtle" :label="__('Split cohort')" @click="openSplit" />
						</div>
						<!-- Search the alumni directory first: most people a leader
						     wants are already here, and this is the only place
						     that can say who is free to join before they ask. -->
						<div class="flex flex-col gap-1">
							<Input
								v-model="alumniQuery"
								type="text"
								:placeholder="__('Search alumni by name, role, organization or city')" :aria-label="__('Search alumni by name, role, organization or city')"
							/>
							<p v-if="alumniSearch.loading" class="px-1 text-xs text-ink-gray-5">
								{{ __('Searching...') }}
							</p>
							<p
								v-else-if="alumniQuery.trim().length >= 2 && !alumniSearch.data?.length"
								class="px-1 text-xs text-ink-gray-5"
							>
								{{ __('Nobody in the directory matches. Invite them by email below.') }}
							</p>
							<ul v-else-if="alumniSearch.data?.length" class="divide-y divide-outline-gray-1 rounded-md border border-outline-gray-2">
								<li
									v-for="cand in alumniSearch.data"
									:key="cand.person"
									class="flex items-center justify-between gap-3 p-2"
								>
									<div class="min-w-0">
										<div class="truncate text-sm text-ink-gray-8">{{ cand.full_name }}</div>
										<div class="truncate text-xs text-ink-gray-5">
											{{ [cand.current_role, cand.current_organization, cand.city].filter(Boolean).join(' · ') }}
										</div>
										<!-- Said plainly rather than hidden: a leader who
										     cannot see why someone is unpickable just
										     emails them instead. -->
										<div v-if="!cand.available" class="text-xs text-ink-amber-3">
											{{ __('Already in another cohort of this kind') }}
										</div>
									</div>
									<Button
										variant="subtle"
										:disabled="!cand.available || inviteRes.loading"
										:label="cand.available ? __('Invite') : __('Unavailable')"
										@click="invitePerson(cand)"
									/>
								</li>
							</ul>
						</div>

						<div class="text-xs text-ink-gray-5">
							{{ __('Or invite someone who is not in the directory:') }}
						</div>
						<div class="flex flex-wrap items-center gap-2">
							<Input v-model="inviteDraft.first_name" type="text" :placeholder="__('First name *')" :aria-label="__('First name *')" class="w-32" />
							<Input v-model="inviteDraft.last_name" type="text" :placeholder="__('Last name')" :aria-label="__('Last name')" class="w-32" />
							<Input v-model="inviteDraft.email" type="text" :placeholder="__('Email *')" :aria-label="__('Email *')" class="w-48" @keyup.enter="inviteMember" />
							<Input v-model="inviteDraft.mobile" type="text" :placeholder="__('Phone (optional)')" :aria-label="__('Phone (optional)')" class="w-36" />
							<Button variant="solid" :label="__('Invite')" :loading="inviteRes.loading" @click="inviteMember" />
						</div>
					</div>
					<table class="w-full text-sm">
						<thead>
							<tr class="text-left text-xs text-ink-gray-5">
								<th class="py-1">{{ __('Member') }}</th>
								<th>{{ __('Role') }}</th>
								<th>{{ __('Last visit') }}</th>
								<th>{{ __('Last post') }}</th>
								<th></th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="m in membersRes.data?.members || []" :key="m.person" class="border-t border-outline-gray-1">
								<td class="py-1.5">
									<div class="font-medium text-ink-gray-9">
										{{ m.name }}
										<span v-if="m.is_leader" class="ml-1 text-xs text-ink-gray-5">({{ __('leader') }})</span>
										<span v-if="m.invite_status === 'Invited'" class="ml-1 rounded bg-surface-gray-2 px-1.5 text-xs text-ink-gray-6">{{ __('invited') }}</span>
									</div>
									<a v-if="m.email" :href="'mailto:' + m.email" class="text-xs text-ink-blue-3 hover:underline">{{ m.email }}</a>
								</td>
								<td class="text-ink-gray-7">{{ m.role }}</td>
								<td class="text-ink-gray-6">{{ m.last_visited ? timeAgo(m.last_visited) : '—' }}</td>
								<td class="text-ink-gray-6">{{ m.last_post_on ? timeAgo(m.last_post_on) : '—' }}</td>
								<td class="text-right">
									<div v-if="membersRes.data?.is_leader && m.invite_status === 'Invited'"
										class="flex items-center justify-end gap-2 text-xs">
										<button class="text-ink-gray-6 hover:text-ink-gray-9" @click="resendInvite(m)">{{ __('Re-send') }}</button>
										<button class="text-ink-gray-6 hover:text-ink-gray-9" @click="copyInvite(m)">{{ __('Copy') }}</button>
										<a v-if="m.mobile" :href="whatsappUrl(m)" target="_blank" rel="noopener" class="text-ink-green-3 hover:underline">WhatsApp</a>
										<a :href="telegramUrl(m)" target="_blank" rel="noopener" class="text-ink-blue-3 hover:underline">Telegram</a>
									</div>
									<button v-else-if="membersRes.data?.is_leader && !m.is_leader"
										class="text-xs text-ink-gray-6 hover:text-ink-gray-9" @click="makeLeader(m)">
										{{ __('Make leader') }}
									</button>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</template>
		</Dialog>

		<!-- report dialog -->
		<Dialog v-model="showReport" :options="{ title: __('Report content') }">
			<template #body-content>
				<div class="flex flex-col gap-3">
					<select :aria-label="__('Reason')" v-model="reportReason"
						class="rounded-md border border-outline-gray-2 bg-surface-white px-2 py-1.5 text-sm">
						<option value="Inappropriate">{{ __('Inappropriate') }}</option>
						<option value="Off-topic">{{ __('Off-topic') }}</option>
						<option value="Harmful">{{ __('Harmful') }}</option>
						<option value="Spam">{{ __('Spam') }}</option>
						<option value="Other">{{ __('Other') }}</option>
					</select>
					<textarea v-model="reportDetail" rows="3"
						class="w-full rounded-md border border-outline-gray-2 bg-surface-white p-2 text-sm text-ink-gray-8"
						:placeholder="__('Anything the moderator should know (optional)')" :aria-label="__('Anything the moderator should know (optional)')"></textarea>
				</div>
			</template>
			<template #actions>
				<div class="flex justify-end gap-2">
					<Button :label="__('Cancel')" @click="showReport = false" />
					<Button variant="solid" :label="__('Report')" :loading="flagContent.loading" @click="submitReport" />
				</div>
			</template>
		</Dialog>

		<!-- moderation queue -->
		<Dialog v-model="showModeration" :options="{ title: __('Moderation queue'), size: 'lg' }">
			<template #body-content>
				<div v-if="!flagsRes.data?.length" class="py-6 text-center text-sm text-ink-gray-5">
					{{ __('No open flags.') }}
				</div>
				<div v-else class="flex flex-col gap-3">
					<div v-for="f in flagsRes.data" :key="f.name" class="rounded-md border border-outline-gray-2 p-2">
						<div class="text-xs text-ink-gray-5">{{ f.target_doctype }} · {{ f.reason }}</div>
						<div class="my-1 text-sm text-ink-gray-8">{{ f.preview || '—' }}</div>
						<div v-if="f.detail" class="mb-1 text-xs italic text-ink-gray-5">{{ f.detail }}</div>
						<div class="flex gap-2">
							<Button variant="subtle" :label="__('Dismiss')" @click="resolveFlag(f.name, 'dismiss')" />
							<Button variant="solid" theme="red" :label="__('Block content')" @click="resolveFlag(f.name, 'block')" />
						</div>
					</div>
				</div>
			</template>
		</Dialog>
		</div>
	</div>
</template>

<script setup>
import PageHeader from '@/components/PageHeader.vue'
import { computed, inject, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Button, Dialog, Input, TextInput, createResource, debounce } from 'frappe-ui'
import {
	MessagesSquare, SquarePen, MessageCircle, Send, Pin, X,
	Lock, Users, Globe, Mail, BookOpen, Check, Video as VideoIcon, Flag, Shield, Ban, Pencil, Trash2,
	Bookmark, BookmarkCheck, UsersRound, Search, Plus, ChevronUp, User,
} from 'lucide-vue-next'
import { timeAgo, siteDate, createToast } from '@/utils'
import RichTextEditor from '@/components/RichTextEditor.vue'
import SermonLabPlayer from '@/components/SermonLabPlayer.vue'
import ExegeticalReader from '@/components/ExegeticalReader.vue'
import CommunityPassagePicker from '@/components/CommunityPassagePicker.vue'
import CohortMeetings from '@/components/CohortMeetings.vue'
import CommunityTopicInput from '@/components/CommunityTopicInput.vue'

const socket = inject('$socket')
const route = useRoute()

const selectedCohort = ref('')
const channelFilter = ref('')
const expandedPost = ref(null)
const replyTo = ref(null)
const replyText = ref('')
const showCompose = ref(false)
const composeKey = ref(0)
const draft = reactive({ cohort: '', channel: '', title: '', content: '', visibility: 'cohort_only', direct_recipient: '', topics: [], scripture: '', video_url: '', reference_doctype: '', reference_name: '' })
const prayerView = ref('active')
// All / Saved / Mine (decisions/101 section 5.3)
const view = ref('all')
const views = [
	{ value: 'all', label: __('All') },
	{ value: 'saved', label: __('Saved') },
	{ value: 'mine', label: __('Mine') },
]
const openReaders = reactive({})
const meetingsRef = ref(null)
const searchQuery = ref('')
const showPassage = ref(false)
const showMembers = ref(false)
const inviteDraft = reactive({ first_name: '', last_name: '', email: '', mobile: '' })
const alumniQuery = ref('')
const alumniSearch = createResource({
	url: 'seminary.seminary.discipleship.api.search_invitable_alumni',
	makeParams: () => ({ cohort: selectedCohort.value, query: alumniQuery.value.trim() }),
	onError() {},
})
// The endpoint returns nothing under two characters, so don't ask.
const searchAlumniDebounced = debounce(() => {
	if (alumniQuery.value.trim().length < 2) {
		alumniSearch.data = []
		return
	}
	alumniSearch.fetch()
}, 300)
watch(alumniQuery, searchAlumniDebounced)
const passageFilter = ref(null)
const showSplit = ref(false)
const splitName = ref('')
const splitOriginal = ref([])
const splitMoving = ref([])
const splitLeader = ref(null)
const replyPrivate = ref(false)
const showBroadcast = ref(false)
const broadcastSubject = ref('')
const broadcastMessage = ref('')
const broadcastEmail = ref(false)
const showEdit = ref(false)
const editKey = ref(0)
const editDraft = reactive({ name: '', title: '', content: '', visibility: 'cohort_only', direct_recipient: '', topics: [], scripture: '', video_url: '', channel_kind: '' })
const showAnswer = ref(false)
const answerNote = ref('')
const answerPost = ref(null)
const linkTarget = ref('')

// --- resources ---
// The rail remembers the last selection in this browser (decisions/101
// section 5.1); it replaced the default-cohort star.
const LAST_COHORT = 'community:lastCohort'
function readLast() {
	try { return localStorage.getItem(LAST_COHORT) } catch { return null }
}
function writeLast(name) {
	try { localStorage.setItem(LAST_COHORT, name || '') } catch { /* private mode */ }
}
let firstLoad = true
const cohortsRes = createResource({
	url: 'seminary.seminary.discipleship.feed_api.community_summary',
	auto: true,
	onSuccess(data) {
		const list = data?.cohorts || []
		if (!firstLoad) return
		firstLoad = false
		// Arriving from a link that names a cohort (the alumni home does this)
		// beats the remembered selection: the person just said which one they
		// meant. Otherwise the last one, else all of them.
		const asked = route.query.cohort
		const last = readLast()
		const known = (name) => name && list.some((c) => c.name === name)
		const pick = known(asked) ? asked : known(last) ? last : ''
		if (pick !== selectedCohort.value) selectedCohort.value = pick
		else refresh()
		if (route.query.members && selectedCohort.value) openMembers()
		if (route.query.discuss && route.query.step) openDiscussion(route.query.discuss, route.query.step)
	},
})
const channelsRes = createResource({
	url: 'seminary.seminary.discipleship.feed_api.list_channels',
	makeParams: () => ({ cohort: selectedCohort.value || null }),
	auto: true,
})
const channelCountsRes = createResource({
	url: 'seminary.seminary.discipleship.feed_api.channel_counts',
	makeParams: () => ({ cohort: selectedCohort.value || null }),
})
// The composer offers the channels of the cohort it posts to (section 1.3).
const composeChannelsRes = createResource({ url: 'seminary.seminary.discipleship.feed_api.list_channels' })
const reactionTypesRes = createResource({
	url: 'seminary.seminary.discipleship.feed_api.list_reaction_types',
	auto: true,
})
const feed = createResource({
	url: 'seminary.seminary.discipleship.feed_api.list_feed',
	makeParams: () => ({
		cohort: selectedCohort.value,
		channel: channelFilter.value || null,
		saved_only: view.value === 'saved' ? 1 : 0,
		mine: view.value === 'mine' ? 1 : 0,
		// Saved shows prayers answered and not, each under its heading.
		answered: isPrayerChannel.value && view.value !== 'saved' ? (prayerView.value === 'answered' ? 1 : 0) : null,
	}),
})
const unreadRes = createResource({
	url: 'seminary.seminary.discipleship.feed_api.unread_counts',
	makeParams: () => ({ cohort: selectedCohort.value }),
})
const thread = createResource({
	url: 'seminary.seminary.discipleship.feed_api.get_thread',
	makeParams: () => ({ post: expandedPost.value }),
})
const related = createResource({
	url: 'seminary.seminary.discipleship.feed_api.related_posts',
	makeParams: () => ({ post: expandedPost.value }),
})
const createPost = createResource({ url: 'seminary.seminary.discipleship.feed_api.create_post' })
const addComment = createResource({ url: 'seminary.seminary.discipleship.feed_api.add_comment' })
const toggleReaction = createResource({ url: 'seminary.seminary.discipleship.feed_api.toggle_reaction' })
const markSeen = createResource({ url: 'seminary.seminary.discipleship.feed_api.mark_seen' })
const markAnswered = createResource({ url: 'seminary.seminary.discipleship.feed_api.mark_prayer_answered' })
const reopenPrayer = createResource({ url: 'seminary.seminary.discipleship.feed_api.reopen_prayer' })
const linkPost = createResource({ url: 'seminary.seminary.discipleship.feed_api.link_post' })
const canModerateRes = createResource({ url: 'seminary.seminary.discipleship.moderation.can_moderate', auto: true })
const canBroadcastRes = createResource({ url: 'seminary.seminary.discipleship.api.can_broadcast', auto: true })
const searchRecipientsRes = createResource({ url: 'seminary.seminary.discipleship.feed_api.search_recipients' })
const flagsRes = createResource({ url: 'seminary.seminary.discipleship.moderation.list_flags' })
const flagContent = createResource({ url: 'seminary.seminary.discipleship.moderation.flag_content' })
const resolveFlagRes = createResource({ url: 'seminary.seminary.discipleship.moderation.resolve_flag' })
const setPostStatusRes = createResource({ url: 'seminary.seminary.discipleship.moderation.set_post_status' })
const editPostRes = createResource({ url: 'seminary.seminary.discipleship.feed_api.edit_post' })
const deletePostRes = createResource({ url: 'seminary.seminary.discipleship.feed_api.delete_post' })
const toggleSaveRes = createResource({ url: 'seminary.seminary.discipleship.feed_api.toggle_save' })
const passageRes = createResource({ url: 'seminary.seminary.integrations.bible.passage_text' })
const membersRes = createResource({ url: 'seminary.seminary.discipleship.api.cohort_members' })
const inviteRes = createResource({ url: 'seminary.seminary.discipleship.api.invite_member' })
const resendRes = createResource({ url: 'seminary.seminary.discipleship.api.resend_invite' })
const pendingRes = createResource({ url: 'seminary.seminary.discipleship.api.my_pending_invites', auto: true })
const acceptInviteRes = createResource({ url: 'seminary.seminary.discipleship.api.accept_invite' })
const declineInviteRes = createResource({ url: 'seminary.seminary.discipleship.api.decline_invite' })
const reassignRes = createResource({ url: 'seminary.seminary.discipleship.api.reassign_leader' })
const splitRes = createResource({ url: 'seminary.seminary.discipleship.api.split_cohort' })
const passagePostsRes = createResource({ url: 'seminary.seminary.discipleship.scripture.posts_in_range' })
const passageRefRes = createResource({ url: 'seminary.seminary.discipleship.feed_api.posts_for_passage' })
const searchRes = createResource({ url: 'seminary.seminary.discipleship.feed_api.search_posts' })
const broadcastRes = createResource({ url: 'seminary.seminary.discipleship.api.broadcast_to_leaders' })

// --- derived ---
const cohorts = computed(() => cohortsRes.data?.cohorts || [])
// New posts in the selection: one cohort's, or all of them.
const totalNew = computed(() => cohortsRes.data?.new || 0)
const newCount = computed(() =>
	selectedCohort.value
		? cohorts.value.find((c) => c.name === selectedCohort.value)?.new || 0
		: totalNew.value
)
const sinceLabel = computed(() => {
	const since = cohortsRes.data?.since
	if (!since) return ''
	const d = siteDate(since).toDate()
	if (isNaN(d)) return ''
	const days = (Date.now() - d.getTime()) / 86400000
	const when = days < 6
		? d.toLocaleDateString(undefined, { weekday: 'long' })
		: d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
	return __('since {0}').format(when)
})
const selectedCohortName = computed(
	() => cohorts.value.find((c) => c.name === selectedCohort.value)?.cohort_name || ''
)
// Named, not just "My cohort": someone who leads two of them is one click from
// inviting a person into the wrong one, and the switcher sits behind the dialog
// where they cannot check it.
const scopeLabel = computed(() => {
	if (selectedCohortName.value) return selectedCohortName.value
	const n = cohorts.value.length
	return n === 1 ? __('All my cohorts · 1 cohort') : __('All my cohorts · {0} cohorts').format(n)
})
const membersTitle = computed(() =>
	selectedCohortName.value
		? __('Cohort: {0}').format(selectedCohortName.value)
		: __('My cohort')
)
const channels = computed(() => channelsRes.data || [])
const channelCounts = computed(() => channelCountsRes.data || {})
const composeChannels = computed(() => composeChannelsRes.data || channels.value)
function channelName(name) {
	return channels.value.find((c) => c.name === name)?.channel_name || name
}
const selectedChannelKind = computed(() => channels.value.find((c) => c.name === channelFilter.value)?.channel_kind || null)
const isPrayerChannel = computed(() => selectedChannelKind.value === 'prayer')
const composeChannelKind = computed(() => composeChannels.value.find((c) => c.name === draft.channel)?.channel_kind || null)
const composeCohort = computed(() => cohorts.value.find((c) => c.name === draft.cohort) || null)
// Who each choice reaches, said plainly (section 5.6). Whole-community posts
// reach only cohorts that offer the channel (section 1.3), so the hint names it.
const visMenuOpen = ref(false)
const visOptions = computed(() => {
	const c = composeCohort.value
	const name = c?.cohort_name || __('this cohort')
	const n = c?.members || 0
	const channel = composeChannels.value.find((ch) => ch.name === draft.channel)?.channel_name
	return [
		{ value: 'cohort_only', label: __('Cohort only'), hint: n === 1 ? __('1 member of {0}').format(name) : __('{0} members of {1}').format(n, name) },
		{ value: 'portal_users', label: __('Whole community'), hint: channel ? __('Every cohort with {0}').format(channel) : __('Everyone in all cohorts') },
		...(canBroadcast.value ? [{ value: 'mentors', label: __('Mentors in this cohort'), hint: __('Only mentors of {0}').format(name) }] : []),
		{ value: 'direct', label: __('One person'), hint: __('Choose someone — like a private note') },
		{ value: 'private', label: __('Only me'), hint: __('A private draft or journal entry') },
	]
})
const currentVis = computed(() => visOptions.value.find((o) => o.value === draft.visibility) || visOptions.value[0])
function onVisFocusOut(e) {
	if (!e.currentTarget.contains(e.relatedTarget)) visMenuOpen.value = false
}
const reactionTypes = computed(() => reactionTypesRes.data || [])
const searchActive = computed(() => searchQuery.value.trim().length >= 2)
// Posts about the picked passage in this cohort (or all), before the channel
// filter, so the note can say what the channel filter hides.
const passagePosts = computed(() => {
	if (!passageFilter.value) return []
	const rows = (passageFilter.value.ref ? passageRefRes.data : passagePostsRes.data) || []
	const inView = (p) => (view.value === 'saved' ? p.saved : view.value === 'mine' ? p.is_mine : true)
	return rows.filter((p) => (!selectedCohort.value || p.cohort === selectedCohort.value) && inView(p))
})
const posts = computed(() => {
	if (searchActive.value) return searchRes.data || []
	if (passageFilter.value) {
		return channelFilter.value
			? passagePosts.value.filter((p) => p.channel === channelFilter.value)
			: passagePosts.value
	}
	return feed.data || []
})
const otherChannelPosts = computed(() =>
	passageFilter.value && channelFilter.value && !searchActive.value
		? passagePosts.value.filter((p) => p.channel !== channelFilter.value)
		: []
)
const otherChannelNames = computed(() =>
	[...new Set(otherChannelPosts.value.map((p) => channelName(p.channel)))].join(', ')
)
// Saved splits prayers you are praying for from answered ones (section 3.2).
const sections = computed(() => {
	if (view.value !== 'saved' || searchActive.value) return [{ key: 'all', label: '', posts: posts.value }]
	const prayer = (p) => p.channel_kind === 'prayer'
	return [
		{ key: 'praying', label: __('Praying for'), posts: posts.value.filter((p) => prayer(p) && !p.prayer_answered) },
		{ key: 'answered', label: __('Answered'), posts: posts.value.filter((p) => prayer(p) && p.prayer_answered) },
		{ key: 'other', label: __('Other saved posts'), posts: posts.value.filter((p) => !prayer(p)) },
	]
})
const lastNewIndex = computed(() => {
	let idx = -1
	posts.value.forEach((p, i) => { if (p.is_new) idx = i })
	return idx
})
const unread = computed(() => unreadRes.data || {})
const threadComments = computed(() => buildThread(thread.data?.comments || []))

function buildThread(comments) {
	// order = as returned (creation asc); compute depth from parent chain
	const byName = {}
	comments.forEach((c) => (byName[c.name] = c))
	const depthOf = (c) => {
		let d = 0, cur = c
		while (cur.parent_comment && byName[cur.parent_comment]) { d++; cur = byName[cur.parent_comment] }
		return d
	}
	// depth-first order so replies sit under their parent
	const children = {}
	comments.forEach((c) => {
		const key = c.parent_comment || '__root'
		;(children[key] = children[key] || []).push(c)
	})
	const out = []
	const walk = (key) => (children[key] || []).forEach((c) => {
		out.push({ ...c, depth: depthOf(c) })
		walk(c.name)
	})
	walk('__root')
	return out
}

function reactionFor(post, rtName) {
	return (post.reactions || []).find((r) => r.reaction_type === rtName)
}
function reactionCount(post, rtName) { return reactionFor(post, rtName)?.count || 0 }
// The reactions the post's channel offers (section 2); a channel with no list,
// or one outside the caller's channels, offers them all.
function reactionsFor(post) {
	const offered = channels.value.find((c) => c.name === post.channel)?.reactions
	if (!offered?.length) return reactionTypes.value
	return offered.map((n) => reactionTypes.value.find((r) => r.name === n)).filter(Boolean)
}
function reactionTitle(post, rt) {
	const people = reactionFor(post, rt.name)?.people || []
	return people.length ? `${rt.label}: ${people.join(', ')}` : rt.label
}
function initials(name) {
	return (name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join('')
}
const DOTS = ['var(--ink-blue-3)', 'var(--ink-amber-3)', 'var(--ink-green-3)', 'var(--ink-red-4)', 'var(--ink-gray-6)']
function dotColor(i) { return DOTS[i % DOTS.length] }
function toggleReader(post) { openReaders[post.name] = !openReaders[post.name] }
function reactionMine(post, rtName) { return !!reactionFor(post, rtName)?.mine }

const visIconMap = { cohort_only: Users, portal_users: Globe, mentors: Shield, private: Lock, direct: User }
function visIcon(v) { return visIconMap[v] || Users }

// --- actions ---
function refresh() {
	// No early return on a missing cohort any more: "" is the All-posts view,
	// not an unready state. list_feed/unread_counts both treat an absent cohort
	// as "everything I may see".
	feed.fetch()
	unreadRes.fetch()
	channelCountsRes.fetch()
}
function setChannel(name) {
	channelFilter.value = name // watch → refresh; feed onSuccess marks seen
}
function openEdit(post) {
	Object.assign(editDraft, {
		name: post.name,
		title: post.title || '',
		content: post.content || '',
		visibility: post.visibility,
		direct_recipient: post.direct_recipient || '',
		topics: [...(post.topics || [])],
		scripture: (post.scripture || []).map((s) => s.display).join('\n'),
		video_url: post.video_url || '',
		channel_kind: post.channel_kind || '',
	})
	editKey.value++
	showEdit.value = true
}
function submitEdit() {
	editPostRes
		.submit({
			post: editDraft.name,
			title: editDraft.title || null,
			content: editDraft.content,
			visibility: editDraft.visibility,
			direct_recipient: editDraft.visibility === 'direct' ? editDraft.direct_recipient : null,
			topics: editDraft.topics,
			scripture: editDraft.scripture.split('\n').map((s) => s.trim()).filter(Boolean),
			video_url: editDraft.channel_kind === 'video_timestamp' ? editDraft.video_url : null,
		})
		.then(() => { showEdit.value = false; refresh() })
		.catch((e) => createToast({ title: e.messages?.[0] || __('Could not save.'), icon: 'alert-circle', iconClasses: 'text-ink-red-3' }))
}
function confirmDelete(post) {
	if (window.confirm(__('Delete this post? This cannot be undone.'))) {
		deletePostRes.submit({ post: post.name }).then(() => {
			if (expandedPost.value === post.name) expandedPost.value = null
			refresh()
		})
	}
}
function toggleThread(post) {
	if (expandedPost.value === post.name) { expandedPost.value = null; return }
	expandedPost.value = post.name
	replyTo.value = null
	thread.fetch()
	related.fetch()
}
function plain(html) {
	return (html || '').replace(/<[^>]+>/g, '').slice(0, 60)
}
function setPrayerView(v) {
	prayerView.value = v
	refresh()
}
function openAnswer(post) {
	answerPost.value = post.name
	answerNote.value = ''
	showAnswer.value = true
}
function confirmAnswer() {
	markAnswered.submit({ post: answerPost.value, note: answerNote.value || null }).then(() => {
		showAnswer.value = false
		refresh()
		if (expandedPost.value) thread.fetch()
	})
}
function reopen(post) {
	reopenPrayer.submit({ post: post.name }).then(() => { refresh(); if (expandedPost.value) thread.fetch() })
}
function submitLink(post) {
	if (!linkTarget.value.trim()) return
	linkPost
		.submit({ post: post.name, linked_post: linkTarget.value.trim(), relation_type: 'reflection' })
		.then(() => { linkTarget.value = ''; thread.fetch() })
		.catch((e) => createToast({ title: e.messages?.[0] || __('Could not link.'), icon: 'alert-circle', iconClasses: 'text-ink-red-3' }))
}

// --- moderation ---
const canModerate = computed(() => !!canModerateRes.data)
// Same authority as the leader broadcast (ADR 076): staff, or a leader of a
// cohort. It gates only what the composer *shows*; create_post re-checks.
const canBroadcast = computed(() => !!canBroadcastRes.data)
const recipientQuery = ref('')
const recipientResults = ref([])
const recipientLabel = ref('')
let recipientTimer = null
function searchRecipients() {
	clearTimeout(recipientTimer)
	const q = recipientQuery.value.trim()
	if (q.length < 2) { recipientResults.value = []; return }
	// Debounced: the picker searches, it never enumerates.
	recipientTimer = setTimeout(() => {
		searchRecipientsRes.submit({ query: q }).then((rows) => { recipientResults.value = rows || [] })
	}, 250)
}
function pickRecipient(r) {
	draft.direct_recipient = r.person
	recipientLabel.value = r.full_name
	recipientQuery.value = ''
	recipientResults.value = []
}
const showReport = ref(false)
const reportTarget = ref(null)
const reportReason = ref('Inappropriate')
const reportDetail = ref('')
const showModeration = ref(false)

function openReport(doctype, name) {
	reportTarget.value = { doctype, name }
	reportReason.value = 'Inappropriate'
	reportDetail.value = ''
	showReport.value = true
}
function submitReport() {
	flagContent
		.submit({
			target_doctype: reportTarget.value.doctype,
			target_name: reportTarget.value.name,
			reason: reportReason.value,
			detail: reportDetail.value || null,
		})
		.then(() => { showReport.value = false; createToast({ title: __('Reported. Thank you.'), icon: 'check' }) })
		.catch((e) => createToast({ title: e.messages?.[0] || __('Could not report.'), icon: 'alert-circle', iconClasses: 'text-ink-red-3' }))
}
function openModeration() {
	showModeration.value = true
	flagsRes.fetch()
}
function resolveFlag(flag, action) {
	resolveFlagRes.submit({ flag, action }).then(() => { flagsRes.fetch(); refresh() })
}
function moderatePost(post, status) {
	setPostStatusRes.submit({ post: post.name, status }).then(() => refresh())
}

// --- save ---
function toggleSave(post) {
	toggleSaveRes.submit({ post: post.name }).then((r) => { post.saved = r.saved })
}

// --- passage popover (Bible badge click) ---
function openPassage(ref) {
	passageRes.data = null
	showPassage.value = true
	passageRes.submit({ resolved_ref: ref.resolved_ref }).catch(() => {})
}

// --- my cohort ---
function openMembers() {
	showMembers.value = true
	membersRes.fetch({ cohort: selectedCohort.value })
}
function acceptInvite(inv) {
	acceptInviteRes.submit({ membership: inv.membership }).then(() => {
		pendingRes.reload()
		cohortsRes.reload()
		createToast({ title: __('Joined {0}.').format(inv.cohort_name), icon: 'check' })
	})
}
function declineInvite(inv) {
	declineInviteRes.submit({ membership: inv.membership }).then(() => {
		pendingRes.reload()
		createToast({ title: __('Invitation declined.'), icon: 'check' })
	})
}
function inviteMember() {
	if (!inviteDraft.first_name.trim() || !inviteDraft.email.trim())
		return createToast({ title: __('First name and email are required.'), icon: 'alert-circle', iconClasses: 'text-ink-red-3' })
	inviteRes
		.submit({
			cohort: selectedCohort.value,
			first_name: inviteDraft.first_name.trim(),
			last_name: inviteDraft.last_name.trim() || null,
			email: inviteDraft.email.trim(),
			mobile: inviteDraft.mobile.trim() || null,
		})
		.then(() => {
			Object.assign(inviteDraft, { first_name: '', last_name: '', email: '', mobile: '' })
			membersRes.fetch({ cohort: selectedCohort.value })
			createToast({ title: __('Invitation sent.'), icon: 'check' })
		})
		.catch((e) => createToast({ title: e.messages?.[0] || __('Could not invite.'), icon: 'alert-circle', iconClasses: 'text-ink-red-3' }))
}
function invitePerson(candidate) {
	// The person already exists on the spine, so only the id travels — the
	// search deliberately returns no email or phone.
	inviteRes
		.submit({ cohort: selectedCohort.value, person: candidate.person })
		.then(() => {
			alumniQuery.value = ''
			alumniSearch.data = []
			membersRes.fetch({ cohort: selectedCohort.value })
			createToast({ title: __('Invitation sent.'), icon: 'check' })
		})
		.catch((e) => createToast({ title: e.messages?.[0] || __('Could not invite.'), icon: 'alert-circle', iconClasses: 'text-ink-red-3' }))
}
function resendInvite(m) {
	resendRes.submit({ membership: m.membership }).then(() => createToast({ title: __('Invite re-sent.'), icon: 'check' }))
}
function inviteMessage(m) {
	const url = window.location.origin + '/seminary/community'
	return __('Hi {0}, you are invited to join the cohort "{1}". Sign in at {2} to accept — first time? use "Forgot password" to set your password.')
		.format(m.name || '', selectedCohortName.value, url)
}
function copyInvite(m) {
	navigator.clipboard?.writeText(inviteMessage(m)).then(() => createToast({ title: __('Invite copied.'), icon: 'check' }))
}
function whatsappUrl(m) {
	return `https://wa.me/${(m.mobile || '').replace(/[^0-9]/g, '')}?text=${encodeURIComponent(inviteMessage(m))}`
}
function telegramUrl(m) {
	const url = window.location.origin + '/seminary/community'
	return `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent(inviteMessage(m))}`
}
function makeLeader(m) {
	if (!window.confirm(__('Make this person the cohort leader?'))) return
	reassignRes.submit({ cohort: selectedCohort.value, new_leader: m.person }).then(() => membersRes.fetch({ cohort: selectedCohort.value }))
}
function openSplit() {
	showMembers.value = false
	splitName.value = ''
	splitMoving.value = []
	splitLeader.value = null
	// everyone except the current leader can be moved to the new cohort
	splitOriginal.value = (membersRes.data?.members || []).filter((m) => !m.is_leader)
	showSplit.value = true
}
function moveToNew(m) {
	splitOriginal.value = splitOriginal.value.filter((x) => x.person !== m.person)
	splitMoving.value = [...splitMoving.value, m]
}
function moveToOriginal(m) {
	splitMoving.value = splitMoving.value.filter((x) => x.person !== m.person)
	splitOriginal.value = [...splitOriginal.value, m]
	if (splitLeader.value === m.person) splitLeader.value = null
}
function submitSplit() {
	if (!splitName.value.trim())
		return createToast({ title: __('Name the new cohort.'), icon: 'alert-circle', iconClasses: 'text-ink-red-3' })
	if (!splitMoving.value.length)
		return createToast({ title: __('Move at least one member.'), icon: 'alert-circle', iconClasses: 'text-ink-red-3' })
	if (!splitLeader.value)
		return createToast({ title: __('Choose a leader for the new cohort.'), icon: 'alert-circle', iconClasses: 'text-ink-red-3' })
	splitRes
		.submit({
			cohort: selectedCohort.value,
			new_cohort_name: splitName.value.trim(),
			member_ids: JSON.stringify(splitMoving.value.map((m) => m.membership)),
			new_leader: splitLeader.value,
		})
		.then(() => { showSplit.value = false; cohortsRes.reload(); refresh(); createToast({ title: __('New cohort created.'), icon: 'check' }) })
		.catch((e) => createToast({ title: e.messages?.[0] || __('Could not split.'), icon: 'alert-circle', iconClasses: 'text-ink-red-3' }))
}

// --- passage filter (section 5.3) ---
function fetchPassage() {
	const f = passageFilter.value
	if (!f) return
	if (f.ref) passageRefRes.fetch({ ref: f.ref })
	else passagePostsRes.fetch({ start_ord: f.start, end_ord: f.end, cohort: selectedCohort.value || null })
}
watch(passageFilter, (f) => { if (f) { searchQuery.value = ''; fetchPassage() } })
function react(post, rtName) {
	toggleReaction
		.submit({ reaction_type: rtName, post: post.name })
		.then(() => {
			feed.fetch()
			if (passageFilter.value) fetchPassage()
			if (expandedPost.value) thread.fetch()
		})
		.catch((e) => createToast({ title: e.messages?.[0] || __('Could not react.'), icon: 'alert-circle', iconClasses: 'text-ink-red-3' }))
}
function submitReply(post) {
	if (!replyText.value.trim()) return
	addComment
		.submit({
			post: post.name,
			content: replyText.value,
			parent_comment: replyTo.value?.name || null,
			is_private: replyPrivate.value ? 1 : 0,
		})
		.then(() => { replyText.value = ''; replyTo.value = null; replyPrivate.value = false; thread.fetch(); feed.fetch() })
}
function openBroadcast() {
	broadcastSubject.value = ''
	broadcastMessage.value = ''
	broadcastEmail.value = false
	showBroadcast.value = true
}
function submitBroadcast() {
	if (!broadcastSubject.value.trim() || !broadcastMessage.value.trim())
		return createToast({ title: __('Subject and message are required.'), icon: 'alert-circle', iconClasses: 'text-ink-red-3' })
	broadcastRes
		.submit({ subject: broadcastSubject.value, message: broadcastMessage.value, email: broadcastEmail.value ? 1 : 0 })
		.then((r) => { showBroadcast.value = false; createToast({ title: __('Sent to {0} leader(s).').format(r.sent), icon: 'check' }) })
		.catch((e) => createToast({ title: e.messages?.[0] || __('Could not send.'), icon: 'alert-circle', iconClasses: 'text-ink-red-3' }))
}
function openCompose() {
	// A post always belongs to a cohort (ADR 064 keeps `cohort` for attribution
	// and lineage), so in the All-posts view the composer has to ask. Default to
	// the starred cohort, else the first one.
	Object.assign(draft, { cohort: selectedCohort.value || cohorts.value[0]?.name || '', channel: channelFilter.value || '', title: '', content: '', visibility: 'cohort_only', direct_recipient: '', topics: [], scripture: '', video_url: '', reference_doctype: '', reference_name: '' })
	recipientQuery.value = ''
	recipientResults.value = []
	recipientLabel.value = ''
	visMenuOpen.value = false
	composeKey.value++ // force the editor to remount with empty content
	showCompose.value = true
	loadComposeChannels()
}
function loadComposeChannels() {
	if (!draft.cohort) return
	composeChannelsRes.fetch({ cohort: draft.cohort }).then((rows) => {
		const names = (rows || []).map((r) => r.name)
		if (!names.includes(draft.channel)) draft.channel = names[0] || ''
	})
}
watch(() => draft.cohort, () => { if (showCompose.value) loadComposeChannels() })
// ADR 087: "Discuss" on a reading-plan step opens the composer filled in from
// the step. Nothing is posted until the member presses Post.
const discussionDraftRes = createResource({ url: 'seminary.seminary.discipleship.reading_plans.discussion_draft' })
function openDiscussion(run, step) {
	discussionDraftRes.submit({ run, step }).then((d) => {
		openCompose()
		const passageChannel = d.scripture?.length && composeChannels.value.find((c) => c.channel_kind === 'bible_passage')
		Object.assign(draft, {
			cohort: d.cohort,
			channel: passageChannel?.name || draft.channel,
			title: d.title,
			content: d.content,
			scripture: (d.scripture || []).join('\n'),
			reference_doctype: d.reference_doctype,
			reference_name: d.reference_name,
		})
		composeKey.value++ // remount the editor with the step's message
	}).catch((e) => createToast({ title: e.messages?.[0] || __('Could not open the discussion.'), icon: 'alert-circle', iconClasses: 'text-ink-red-3' }))
}
function submitPost() {
	if (!draft.cohort || !draft.channel || !draft.content?.trim()) {
		createToast({ title: __('A cohort, a channel and some content are required.'), icon: 'alert-circle', iconClasses: 'text-ink-red-3' })
		return
	}
	if (composeChannelKind.value === 'video_timestamp' && !draft.video_url?.trim()) {
		createToast({ title: __('Sermon Lab posts need a YouTube link.'), icon: 'alert-circle', iconClasses: 'text-ink-red-3' })
		return
	}
	createPost
		.submit({
			cohort: draft.cohort,
			channel: draft.channel,
			title: draft.title || null,
			content: draft.content,
			visibility: draft.visibility,
			direct_recipient: draft.visibility === 'direct' ? draft.direct_recipient : null,
			topics: draft.topics,
			scripture: draft.scripture.split('\n').map((s) => s.trim()).filter(Boolean),
			video_url: draft.video_url || null,
			reference_doctype: draft.reference_doctype || null,
			reference_name: draft.reference_name || null,
		})
		.then(() => { showCompose.value = false; refresh(); cohortsRes.reload() })
		.catch((e) => createToast({ title: e.messages?.[0] || __('Could not post.'), icon: 'alert-circle', iconClasses: 'text-ink-red-3' }))
}

// --- reactive refetch + realtime ---
watch([selectedCohort, channelFilter, view], () => { expandedPost.value = null; refresh() })

// debounced search: cohort-scoped, only fires at 2+ chars
let searchTimer = null
watch(searchQuery, (q) => {
	clearTimeout(searchTimer)
	const term = (q || '').trim()
	if (term.length < 2) { searchRes.data = []; return }
	if (passageFilter.value) passageFilter.value = null
	searchTimer = setTimeout(
		() => searchRes.submit({ cohort: selectedCohort.value || null, query: term }),
		300,
	)
})
watch(selectedCohort, () => { searchQuery.value = '' })

// Mark-on-LEAVE (not on load): the "New" divider baseline stays frozen while you
// read a channel, and only advances when you leave it, switch cohort, or close
// the page — so posts that arrived since your last visit stay flagged new.
function markLeaving(cohort, channel) {
	if (!cohort) return
	markSeen.submit({ cohort, channel: channel || null }).then(() => unreadRes.fetch())
}
// Leaving a specific channel marks just that one seen (its divider resets next
// time). Leaving the cohort or the page marks everything seen — a clean "since
// your last visit" baseline. The "All" view never mass-marks mid-session, so
// its divider survives channel hops.
watch(channelFilter, (nv, ov) => { if (ov) markLeaving(selectedCohort.value, ov) })
watch(selectedCohort, (nv, ov) => {
	if (ov) markLeaving(ov, null)
	writeLast(nv)
	channelsRes.fetch()
	if (passageFilter.value) fetchPassage()
})

function onFeedUpdate(data) {
	if (data?.cohort === selectedCohort.value) refresh()
}
onMounted(() => socket && socket.on('cohort_feed_update', onFeedUpdate))
onUnmounted(() => {
	socket && socket.off('cohort_feed_update', onFeedUpdate)
	markLeaving(selectedCohort.value, null)
})
</script>
