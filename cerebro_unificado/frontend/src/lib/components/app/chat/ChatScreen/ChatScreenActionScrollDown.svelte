<script lang="ts">
	import { ArrowDown } from '@lucide/svelte';
	import ActionIcon from '$lib/components/app/actions/ActionIcon.svelte';

	let { onclick }: { onclick: (e?: MouseEvent) => void } = $props();
</script>

<div class="pointer-events-auto flex justify-center relative h-0">
	<ActionIcon
		icon={ArrowDown}
		{onclick}
		ariaLabel="Scroll to bottom"
		tooltip="Scroll to bottom"
		size="lg"
		iconSize="h-4 w-4"
		class="scroll-down-btn h-9 w-9 rounded-full bg-accent/80 text-accent-foreground absolute bottom-4 shadow-lg backdrop-blur-sm border border-border/30 transition-all duration-300 hover:shadow-xl hover:bg-accent hover:scale-110 animate-in fade-in slide-in-from-bottom-2 duration-300"
	/>
</div>

<style>
	:global(.scroll-down-btn svg) {
		animation: gentle-bounce 2s ease-in-out infinite;
	}

	@keyframes gentle-bounce {
		0%, 100% {
			transform: translateY(0);
		}
		50% {
			transform: translateY(2px);
		}
	}
</style>
