<script lang="ts">
		import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import * as Collapsible from '$lib/components/ui/collapsible/index.js';
	import { buttonVariants } from '$lib/components/ui/button/index.js';
	import { Card } from '$lib/components/ui/card';
	import { createAutoScrollController } from '$lib/hooks/use-auto-scroll.svelte';
	import { useThrottle } from '$lib/hooks/use-throttle.svelte';
	import { formatReasoningPreview } from '$lib/utils';
	import { config } from '$lib/stores/settings.svelte';
	import type { Snippet } from 'svelte';
	import type { Component } from 'svelte';
	import { animate } from 'animejs';

	interface Props {
		open?: boolean;
		class?: string;
		icon?: Component;
		iconClass?: string;
		title: string;
		subtitle?: string;
		preview?: string;
		rawContent?: string;
		isStreaming?: boolean;
		onToggle?: () => void;
		children: Snippet;
	}

	let {
		open = $bindable(false),
		class: className = '',
		icon: IconComponent,
		iconClass = 'h-4 w-4',
		title,
		subtitle,
		preview,
		rawContent,
		isStreaming = false,
		onToggle,
		children
	}: Props = $props();

	let contentContainer: HTMLDivElement | undefined = $state();
	let iconWrapperEl: HTMLDivElement | undefined = $state();
	let cardEl: HTMLElement | undefined = $state();

	const showThoughtInProgress = $derived(config().showThoughtInProgress as boolean);

	let previewKey = useThrottle(() => rawContent ?? preview ?? '', 500);
	let displayedPreview = $state('');
	let displayedOverflow = $state(0);

	$effect(() => {
		void previewKey.key;
		const content = rawContent ?? preview ?? '';
		const result = formatReasoningPreview(content);
		displayedPreview = result.preview;
		displayedOverflow = result.overflow;
	});

	const autoScroll = createAutoScrollController();

	$effect(() => {
		autoScroll.setContainer(contentContainer);
	});

	$effect(() => {
		// Only auto-scroll when open and streaming
		autoScroll.updateInterval(open && isStreaming);
	});

	// Animación visual loca "PZ Fusion" con animejs cuando el cerebro está razonando
	$effect(() => {
		if (isStreaming && iconWrapperEl) {
			const anim = animate(iconWrapperEl, {
				scale: [
					{ value: 1.35, duration: 250, easing: 'easeOutElastic(1, .6)' },
					{ value: 0.85, duration: 200, easing: 'easeInQuad' },
					{ value: 1.15, duration: 200, easing: 'easeOutQuad' },
					{ value: 1.0, duration: 300, easing: 'easeOutElastic(1, .8)' }
				],
				rotate: [
					{ value: -15, duration: 200, easing: 'easeInOutSine' },
					{ value: 15, duration: 200, easing: 'easeInOutSine' },
					{ value: 0, duration: 300, easing: 'easeOutElastic(1, .6)' }
				],
				filter: [
					{ value: 'drop-shadow(0 0 8px rgba(139, 92, 246, 0.9))', duration: 200 },
					{ value: 'drop-shadow(0 0 2px rgba(139, 92, 246, 0.3))', duration: 500 }
				],
				loop: true,
				delay: 300
			});
			return () => anim.pause();
		}
	});

	// Animación de destello / border-glow en el Card cuando está razonando
	$effect(() => {
		if (isStreaming && cardEl) {
			const borderAnim = animate(cardEl, {
				boxShadow: [
					{ value: '0 0 15px 2px rgba(139, 92, 246, 0.25)', duration: 400, easing: 'easeInOutQuad' },
					{ value: '0 0 5px 0px rgba(139, 92, 246, 0.05)', duration: 600, easing: 'easeInOutQuad' }
				],
				borderColor: [
					{ value: 'rgba(139, 92, 246, 0.4)', duration: 400, easing: 'easeInOutQuad' },
					{ value: 'rgba(139, 92, 246, 0.1)', duration: 600, easing: 'easeInOutQuad' }
				],
				loop: true
			});
			return () => borderAnim.pause();
		}
	});

	function handleScroll() {
		autoScroll.handleScroll();
	}
</script>

<Collapsible.Root
	{open}
	onOpenChange={(value) => {
		open = value;
		onToggle?.();
	}}
	class={className}
>
	<Card bind:this={cardEl} class="gap-0 border-border/60 bg-card/45 backdrop-blur-md hover:bg-card/65 transition-all duration-300 rounded-xl shadow-[0_2px_8px_rgba(0,0,0,0.04)] py-0 overflow-hidden">
		<Collapsible.Trigger class="flex w-full cursor-pointer items-center justify-between gap-3 p-3.5 hover:text-foreground text-muted-foreground transition-colors duration-150">
			<div class="flex min-w-0 items-center gap-2.5">
				<div class="flex items-center gap-2">
					{#if IconComponent}
						<div bind:this={iconWrapperEl} class="flex items-center justify-center shrink-0">
							<IconComponent class="{iconClass} {isStreaming ? 'text-primary' : 'text-muted-foreground'}" />
						</div>
					{/if}

					<span class="font-sans text-xs font-semibold uppercase tracking-wider text-foreground/80">{title}</span>

					{#if subtitle}
						<span class="text-[11px] font-medium px-1.5 py-0.5 rounded bg-muted/60 text-muted-foreground select-none uppercase tracking-wide">{subtitle}</span>
					{/if}
				</div>

				{#if displayedPreview && !showThoughtInProgress}
					<div class="flex min-w-0 items-baseline justify-between gap-2 border-l border-border/40 pl-2.5">
						<div class="w-3/4 truncate text-xs text-muted-foreground/75">
							{displayedPreview}
						</div>
						{#if displayedOverflow > 0}
							<span class="shrink-0 text-[10px] text-muted-foreground/50 font-mono"
								>{displayedOverflow}+ chars</span
							>
						{/if}
					</div>
				{/if}
			</div>

			<div
				class={buttonVariants({
					variant: 'ghost',
					size: 'sm',
					class: 'h-7 w-7 p-0 text-muted-foreground hover:text-foreground hover:bg-muted/50 rounded-md transition-colors'
				})}
			>
				<ChevronDown class="h-4 w-4 transition-transform duration-300 {open ? 'rotate-180' : ''}" />

				<span class="sr-only">Toggle content</span>
			</div>
		</Collapsible.Trigger>

		<Collapsible.Content>
			<div
				bind:this={contentContainer}
				class="overflow-y-auto border-t border-border/40 px-4 pb-4 pt-3.5 bg-muted/10"
				onscroll={handleScroll}
				style="min-height: var(--min-message-height); max-height: var(--max-message-height);"
			>
				{@render children()}
			</div>
		</Collapsible.Content>
	</Card>
</Collapsible.Root>
