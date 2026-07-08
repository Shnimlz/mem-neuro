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

	import { animate } from 'animejs';

	interface FlamePoint {
		x: number;
		y: number;
		angle: number;
	}

	// Geometría del borde del badge (rounded rect de 80x24px con rx=12px)
	const BADGE_WIDTH = 80;
	const BADGE_HEIGHT = 24;
	const BADGE_RX = 12;

	function calculateFlamePoints(w: number, h: number, r: number, spacing: number = 13): FlamePoint[] {
		const points: FlamePoint[] = [];
		const L_top = w - 2 * r;
		const L_right = h - 2 * r;
		const L_bottom = w - 2 * r;
		const L_left = h - 2 * r;
		const L_arc = (Math.PI * r) / 2;

		const segments = [
			{ type: 'line', len: L_top, x1: r, y1: 0, x2: w - r, y2: 0, angle: -90 },
			{ type: 'arc', len: L_arc, cx: w - r, cy: r, aStart: -Math.PI / 2, aEnd: 0 },
			{ type: 'line', len: L_right, x1: w, y1: r, x2: w, y2: h - r, angle: 0 },
			{ type: 'arc', len: L_arc, cx: w - r, cy: h - r, aStart: 0, aEnd: Math.PI / 2 },
			{ type: 'line', len: L_bottom, x1: w - r, y1: h, x2: r, y2: h, angle: 90 },
			{ type: 'arc', len: L_arc, cx: r, cy: h - r, aStart: Math.PI / 2, aEnd: Math.PI },
			{ type: 'line', len: L_left, x1: 0, y1: h - r, x2: 0, y2: r, angle: 180 },
			{ type: 'arc', len: L_arc, cx: r, cy: r, aStart: Math.PI, aEnd: (3 * Math.PI) / 2 }
		];

		const perimeter = segments.reduce((sum, seg) => sum + seg.len, 0);
		const numPoints = Math.max(8, Math.round(perimeter / spacing));
		const step = perimeter / numPoints;

		for (let i = 0; i < numPoints; i++) {
			const t = i * step;
			let accumulated = 0;
			for (const seg of segments) {
				if (t >= accumulated && t < accumulated + seg.len + 0.001) {
					const local_t = t - accumulated;
					const ratio = seg.len > 0 ? local_t / seg.len : 0;
					if (seg.type === 'line') {
						const x = seg.x1 + ratio * (seg.x2 - seg.x1);
						const y = seg.y1 + ratio * (seg.y2 - seg.y1);
						points.push({ x, y, angle: seg.angle });
					} else {
						const angle_rad = seg.aStart + ratio * (seg.aEnd - seg.aStart);
						const x = seg.cx + r * Math.cos(angle_rad);
						const y = seg.cy + r * Math.sin(angle_rad);
						points.push({ x, y, angle: (angle_rad * 180) / Math.PI });
					}
					break;
				}
				accumulated += seg.len;
			}
		}
		return points;
	}

	const flamePoints = $derived(
		thinkingEnabled && currentEffort === 'max'
			? calculateFlamePoints(BADGE_WIDTH, BADGE_HEIGHT, BADGE_RX, 13)
			: []
	);

	// Referencias de elementos DOM para animar
	let triggerEl: HTMLElement | undefined = $state();
	let unlimitedTextEl: HTMLElement | undefined = $state();
	let flameElements = $state<SVGElement[]>([]);

	// Control del ciclo de vida de animaciones de anime.js
	$effect(() => {
		const isMaxActive = thinkingEnabled && currentEffort === 'max';
		if (!isMaxActive) {
			flameElements = [];
			return;
		}

		const activeAnimations: any[] = [];

		// 1. Animar cada llama individualmente de forma asíncrona/desfasada
		const elements = flameElements.filter(Boolean);
		elements.forEach((el) => {
			const anim = animate(el, {
				scaleY: [
					{ value: 0.75, duration: 200 + Math.random() * 100, easing: 'easeOutSine' },
					{ value: 1.25, duration: 250 + Math.random() * 150, easing: 'easeInOutQuad' },
					{ value: 0.85, duration: 200 + Math.random() * 100, easing: 'easeInSine' },
					{ value: 1.15, duration: 250 + Math.random() * 100, easing: 'easeInOutQuad' },
					{ value: 0.8, duration: 200 + Math.random() * 100, easing: 'easeOutSine' }
				],
				scaleX: [
					{ value: 0.85, duration: 250 + Math.random() * 100, easing: 'easeInOutSine' },
					{ value: 1.15, duration: 300 + Math.random() * 100, easing: 'easeInOutQuad' },
					{ value: 0.9, duration: 250 + Math.random() * 100, easing: 'easeInOutSine' },
					{ value: 1.1, duration: 250 + Math.random() * 100, easing: 'easeInOutQuad' },
					{ value: 0.85, duration: 200 + Math.random() * 100, easing: 'easeInOutSine' }
				],
				rotate: [
					{ value: '-=6', duration: 300 + Math.random() * 200, easing: 'easeInOutSine' },
					{ value: '+=12', duration: 350 + Math.random() * 200, easing: 'easeInOutSine' },
					{ value: '-=6', duration: 300 + Math.random() * 200, easing: 'easeInOutSine' }
				],
				duration: 900 + Math.random() * 600,
				delay: Math.random() * 500,
				direction: 'alternate',
				loop: true,
				easing: 'easeInOutQuad'
			});
			activeAnimations.push(anim);
		});

		// 2. Animar el glow pulsante del contenedor del badge
		if (triggerEl) {
			const glow = animate(triggerEl, {
				boxShadow: [
					{ value: '0 0 8px 1px rgba(255, 106, 26, 0.2), inset 0 0 2px rgba(255, 106, 26, 0.1)', duration: 600, easing: 'easeInOutSine' },
					{ value: '0 0 16px 4px rgba(255, 106, 26, 0.55), inset 0 0 4px rgba(255, 106, 26, 0.2)', duration: 700, easing: 'easeInOutSine' }
				],
				borderColor: [
					{ value: 'rgba(255, 106, 26, 0.3)', duration: 650, easing: 'easeInOutSine' },
					{ value: 'rgba(255, 106, 26, 0.65)', duration: 650, easing: 'easeInOutSine' }
				],
				loop: true,
				direction: 'alternate'
			});
			activeAnimations.push(glow);
		}

		// 3. Animar color del texto "Unlimited"
		if (unlimitedTextEl) {
			const textAnim = animate(unlimitedTextEl, {
				color: [
					{ value: '#ff6a1a', duration: 800, easing: 'easeInOutSine' },
					{ value: '#ffd24c', duration: 800, easing: 'easeInOutSine' }
				],
				loop: true,
				direction: 'alternate'
			});
			activeAnimations.push(textAnim);
		}

		return () => {
			activeAnimations.forEach((a) => a?.pause());
		};
	});
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
							? 'bg-gradient-to-r from-red-500 via-orange-500 to-yellow-500 bg-clip-text text-transparent font-bold'
							: 'text-foreground'
					]}>
						{level.label}
					</span>

					{#if !level.isOff}
						<!-- Si es Max, vinculamos el elemento para animarlo con animejs -->
						{#if isMax}
							<span
								bind:this={unlimitedTextEl}
								class="text-[10px] tabular-nums font-semibold"
							>
								Unlimited
							</span>
						{:else}
							<span class="text-[11px] text-muted-foreground opacity-60">
								{REASONING_EFFORT_TOKENS[level.value] === -1
									? 'Unlimited'
									: `Max ${REASONING_EFFORT_TOKENS[level.value].toLocaleString()} tokens`}
							</span>
						{/if}
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
	/* Animaciones manejadas 100% por anime.js de forma imperativa. Estilos CSS limpios y estáticos. */
</style>
