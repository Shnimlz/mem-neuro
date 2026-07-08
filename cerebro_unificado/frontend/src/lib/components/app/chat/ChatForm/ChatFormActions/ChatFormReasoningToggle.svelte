<script lang="ts">
	import { Lightbulb, LightbulbOff, Check, Info } from '@lucide/svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import * as Tooltip from '$lib/components/ui/tooltip';
	import { ReasoningEffort, MessageRole } from '$lib/enums';
	import { REASONING_EFFORT_TOKENS } from '$lib/constants/reasoning-effort-tokens';
	import { REASONING_EFFORT_LEVELS } from '$lib/constants/reasoning-effort';
	import type { ReasoningEffortLevel } from '$lib/types';
	import {
		modelsStore,
		checkModelSupportsThinking,
		supportsThinking,
		propsCacheVersion,
		loadedModelIds
	} from '$lib/stores/models.svelte';
	import { chatStore } from '$lib/stores/chat.svelte';
	import { conversationsStore, activeMessages } from '$lib/stores/conversations.svelte';
	import { isRouterMode } from '$lib/stores/server.svelte';
	import type { DatabaseMessage } from '$lib/types/database';

	let thinkingEnabled = $derived(conversationsStore.getThinkingEnabled());
	let currentEffort = $derived(conversationsStore.getReasoningEffort());
	let isOff = $derived(!thinkingEnabled);
	let tooltipText = $derived(thinkingEnabled ? `${currentEffort} Reasoning` : 'Disabled Reasoning');
	let subOpen = $state(false);

	// Get conversation model from message history
	let conversationModel = $derived(
		chatStore.getConversationModel(activeMessages() as DatabaseMessage[])
	);

	// Fallback: if model props aren't available, check if any assistant messages
	// for this model in the active conversation have reasoning content.
	let modelSupportsThinkingFromMessages = $derived.by(() => {
		const modelId = isRouterMode() ? modelsStore.selectedModelName || conversationModel : null;
		if (!modelId) return false;
		const messages = conversationsStore.activeMessages;
		return messages.some(
			(m: DatabaseMessage) =>
				m.role === MessageRole.ASSISTANT && m.model === modelId && !!m.reasoningContent
		);
	});

	// Check if model supports thinking. Primary: chat template from /props.
	// Fallback: message history (reasoning content in assistant messages).
	let modelSupportsThinking = $derived.by(() => {
		loadedModelIds();
		propsCacheVersion();

		if (isRouterMode()) {
			const modelId = modelsStore.selectedModelName || conversationModel;
			return checkModelSupportsThinking(modelId ?? '') || modelSupportsThinkingFromMessages;
		}

		// In non-router mode, use the built-in supportsThinking
		return supportsThinking() || modelSupportsThinkingFromMessages;
	});

	// Check if current item is selected
	function isSelected(item: ReasoningEffortLevel): boolean {
		if (item.isOff) {
			return isOff;
		}
		return thinkingEnabled && currentEffort === item.value;
	}

	function handleSelection(item: ReasoningEffortLevel) {
		if (item.isOff) {
			conversationsStore.setThinkingEnabled(false);
		} else {
			conversationsStore.setThinkingEnabled(true);
			conversationsStore.setReasoningEffort(item.value as ReasoningEffort);
		}
		subOpen = false;
	}
</script>

{#if modelSupportsThinking}
	<DropdownMenu.Root bind:open={subOpen}>
		<Tooltip.Root>
			<Tooltip.Trigger>
					<DropdownMenu.Trigger
					class={[
						'flex h-6 w-6 cursor-pointer items-center justify-center rounded-full p-0 transition-all duration-300 ease-out focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 group hover:scale-110 active:scale-95 relative overflow-hidden',
						thinkingEnabled
							? currentEffort === 'max'
								? 'bg-orange-500/10 hover:bg-orange-500/25 border border-orange-500/30 hover:border-orange-500/60 shadow-[0_0_15px_rgba(249,115,22,0.4)] animate-fire-pulse'
								: 'bg-amber-400/10 hover:bg-amber-400/20 hover:shadow-[0_0_12px_rgba(251,191,36,0.3)]'
							: 'bg-muted hover:bg-muted/80'
					]}
					aria-label={`${tooltipText}. Click to configure.`}
				>
					<!-- Efecto de partículas de fuego de fondo -->
					{#if thinkingEnabled && currentEffort === 'max'}
						<div class="absolute inset-0 bg-gradient-to-t from-red-600/20 via-orange-500/10 to-transparent pointer-events-none animate-flame-flicker"></div>
					{/if}

					{#if thinkingEnabled}
						{#if currentEffort === 'max'}
							<Lightbulb class="h-3 w-3 text-orange-500 transition-transform duration-300 group-hover:rotate-12 drop-shadow-[0_0_5px_rgba(239,68,68,0.9)] animate-wiggle" />
						{:else}
							<Lightbulb class="h-3 w-3 text-amber-400 transition-transform duration-300 group-hover:rotate-12" />
						{/if}
					{:else}
						<LightbulbOff class="h-3 w-3 text-muted-foreground transition-transform duration-300 group-hover:-rotate-12" />
					{/if}
				</DropdownMenu.Trigger>
			</Tooltip.Trigger>

			<Tooltip.Content>
				<p class="capitalize">
					{tooltipText}
					{#if thinkingEnabled && currentEffort === 'max'}
						🔥
					{/if}
				</p>
			</Tooltip.Content>
		</Tooltip.Root>

		<DropdownMenu.Content
			align="start"
			class="w-65 rounded-xl bg-popover p-3 text-popover-foreground shadow-md outline-none border border-border/50"
		>
			<div class="mb-2 px-2.5 text-sm font-semibold tracking-wide text-foreground/90">Reasoning effort</div>

			{#each REASONING_EFFORT_LEVELS as level (level.value)}
				{@const isMax = level.value === 'max'}
				<button
					type="button"
					class="flex w-full cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition-all duration-150 hover:bg-accent relative overflow-hidden"
					class:bg-accent={isSelected(level)}
					class:border-orange-500-glow={isMax && isSelected(level)}
					onclick={() => handleSelection(level)}
				>
					{#if isSelected(level)}
						<Check class="h-4 w-4 shrink-0 text-foreground" />
					{:else}
						<div class="h-4 w-4 shrink-0"></div>
					{/if}

					<span class={[
						'flex-1 font-medium transition-colors',
						isMax 
							? 'bg-gradient-to-r from-red-500 via-orange-500 to-yellow-500 bg-clip-text text-transparent font-bold animate-pulse'
							: 'text-foreground'
					]}>
						{level.label}
						{#if isMax}
							🔥
						{/if}
					</span>

					{#if !level.isOff}
						<span class={[
							'text-[10px] tabular-nums',
							isMax
								? 'text-orange-500/80 font-semibold'
								: 'text-muted-foreground opacity-60'
						]}>
							{REASONING_EFFORT_TOKENS[level.value] === -1
								? 'Unlimited'
								: `Max ${REASONING_EFFORT_TOKENS[level.value].toLocaleString()} tokens`}
						</span>
					{/if}

					{#if level.hasInfo}
						<Tooltip.Root>
							<Tooltip.Trigger>
								<Info class="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
							</Tooltip.Trigger>
							<Tooltip.Content side="left">
								<p>Maximum reasoning effort with extended context usage</p>
							</Tooltip.Content>
						</Tooltip.Root>
					{/if}
				</button>
			{/each}
		</DropdownMenu.Content>
	</DropdownMenu.Root>
{/if}

<style>
	@keyframes fire-pulse {
		0%, 100% {
			box-shadow: 0 0 10px 1px rgba(249, 115, 22, 0.4), inset 0 0 4px rgba(239, 68, 68, 0.2);
			border-color: rgba(249, 115, 22, 0.4);
		}
		50% {
			box-shadow: 0 0 20px 4px rgba(239, 68, 68, 0.65), inset 0 0 8px rgba(249, 115, 22, 0.4);
			border-color: rgba(239, 68, 68, 0.7);
		}
	}
	@keyframes flame-flicker {
		0%, 100% { opacity: 0.8; transform: translateY(0) scaleY(1); }
		50% { opacity: 1; transform: translateY(-1px) scaleY(1.15); }
	}
	@keyframes wiggle {
		0%, 100% { transform: rotate(0); }
		25% { transform: rotate(-5deg); }
		75% { transform: rotate(5deg); }
	}
	:global(.animate-fire-pulse) {
		animation: fire-pulse 1.5s infinite ease-in-out !important;
	}
	:global(.animate-flame-flicker) {
		animation: flame-flicker 0.2s infinite ease-in-out !important;
		transform-origin: bottom center;
	}
	:global(.animate-wiggle) {
		animation: wiggle 0.6s infinite ease-in-out !important;
	}
	.border-orange-500-glow {
		box-shadow: 0 0 8px rgba(249, 115, 22, 0.25) !important;
		border: 1px solid rgba(249, 115, 22, 0.4) !important;
	}
</style>
