<script lang="ts">
	import { Card } from '$lib/components/ui/card';
	import { ChatAttachmentsList, MarkdownContent } from '$lib/components/app';
	import { config } from '$lib/stores/settings.svelte';
	import { chatStore } from '$lib/stores/chat.svelte';
	import type { DatabaseMessageExtra } from '$lib/types/database';

	interface Props {
		content: string;
		attachments?: DatabaseMessageExtra[];
		renderMarkdown?: boolean;
		textColorClass?: string;
		cardBgClass?: string;
		maxHeightStyle?: string;
	}

	let {
		content,
		attachments = [],
		renderMarkdown = false,
		textColorClass = 'text-foreground',
		cardBgClass = 'dark:bg-primary/15',
		maxHeightStyle = ''
	}: Props = $props();

	let messageElement = $state<HTMLElement>();
	const currentConfig = $derived(config());
	const isMultiline = $derived(content.includes('\n'));
</script>

{#if attachments && attachments.length > 0}
	<div class="mb-2 max-w-[80%]">
		<ChatAttachmentsList {attachments} readonly imageHeight="h-40" />
	</div>
{/if}

{#if content.trim()}
	<Card
		class="chat-message-user-bubble max-w-[80%] overflow-y-auto rounded-[1.25rem] border border-border/20 bg-primary/5 px-3.75 py-1.5 {textColorClass} backdrop-blur-lg transition-shadow duration-300 hover:shadow-[0_0_20px_var(--user-bubble-glow)] data-multiline:py-2.5 data-multiline:rounded-[1.125rem] {cardBgClass}"
		data-multiline={isMultiline ? '' : undefined}
		style="{maxHeightStyle} overflow-wrap: anywhere; word-break: break-word;"
	>
		{#if renderMarkdown && currentConfig.renderUserContentAsMarkdown}
			<div bind:this={messageElement}>
				<MarkdownContent
					class="markdown-user-content -my-4"
					{content}
					onMaximizeCode={(code, lang) => chatStore.showCodePreview(code, lang)}
				/>
			</div>
		{:else}
			<span bind:this={messageElement} class="text-md whitespace-pre-wrap">
				{content}
			</span>
		{/if}
	</Card>
{/if}
