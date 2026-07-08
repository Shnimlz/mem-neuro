<script lang="ts">
	import { BadgeInfo } from '$lib/components/app';
	import * as Tooltip from '$lib/components/ui/tooltip';
	import { copyToClipboard } from '$lib/utils';
	import type { Component } from 'svelte';

	interface Props {
		class?: string;
		icon: Component;
		value: string | number;
		tooltipLabel?: string;
		useRgbEffect?: boolean;
	}

	let { class: className = '', icon: IconComponent, value, tooltipLabel, useRgbEffect = false }: Props = $props();

	function handleClick() {
		void copyToClipboard(String(value));
	}
</script>

{#if tooltipLabel}
	<Tooltip.Root>
		<Tooltip.Trigger>
			<!-- prevent another nested button element -->
			{#snippet child({ props })}
				<BadgeInfo {...props} class={className} onclick={handleClick}>
					{#snippet icon()}
						<IconComponent class="h-3 w-3" />
					{/snippet}

					<span class={useRgbEffect ? 'animate-gradient-rgb font-semibold' : ''}>{value}</span>
				</BadgeInfo>
			{/snippet}
		</Tooltip.Trigger>
		<Tooltip.Content>
			<p>{tooltipLabel}</p>
		</Tooltip.Content>
	</Tooltip.Root>
{:else}
	<BadgeInfo class={className} onclick={handleClick}>
		{#snippet icon()}
			<IconComponent class="h-3 w-3" />
		{/snippet}

		<span class={useRgbEffect ? 'animate-gradient-rgb font-semibold' : ''}>{value}</span>
	</BadgeInfo>
{/if}
