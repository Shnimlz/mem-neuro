<script lang="ts">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import Globe from '@lucide/svelte/icons/globe';
	import Search from '@lucide/svelte/icons/search';
	import FileText from '@lucide/svelte/icons/file-text';
	import Sparkles from '@lucide/svelte/icons/sparkles';
	import Check from '@lucide/svelte/icons/check';
	import ExternalLink from '@lucide/svelte/icons/external-link';
	import * as Collapsible from '$lib/components/ui/collapsible/index.js';
	import { Card } from '$lib/components/ui/card';
	import * as Tooltip from '$lib/components/ui/tooltip';
	import type { Component } from 'svelte';

	// ─── Types ───────────────────────────────────────────────────────────

	interface SearchResult {
		title: string;
		url: string;
		icon?: string;
		content?: string;
	}

	type SearchPhase = 'analyzing' | 'searching' | 'extracting' | 'synthesizing' | 'done';

	interface PhaseConfig {
		id: SearchPhase;
		label: string;
		icon: Component;
	}

	interface Props {
		query: string;
		results: SearchResult[];
		/** If true, stepper animates through phases. If false/omitted, jumps to 'done'. */
		isSearching?: boolean;
	}

	// ─── Props & State ───────────────────────────────────────────────────

	let { query, results, isSearching = false }: Props = $props();
	let isOpen = $state(false);

	// ─── Phase Stepper ───────────────────────────────────────────────────

	const phases: PhaseConfig[] = [
		{ id: 'analyzing', label: 'Analizando consulta y abstrayendo palabras clave…', icon: Search },
		{ id: 'searching', label: 'Buscando en la web a través de Google…', icon: Globe },
		{
			id: 'extracting',
			label: 'Extrayendo contenido de los enlaces encontrados…',
			icon: FileText
		},
		{
			id: 'synthesizing',
			label: 'Sintetizando información para el modelo…',
			icon: Sparkles
		}
	];

	let currentPhaseIdx = $state(0);
	let phaseTimerId: ReturnType<typeof setTimeout> | undefined;

	// Phase progression intervals (ms) — simulate latency perception
	const PHASE_INTERVALS = [1200, 1800, 2200, 1500];

	function advancePhase() {
		if (currentPhaseIdx < phases.length - 1) {
			currentPhaseIdx++;
			phaseTimerId = setTimeout(advancePhase, PHASE_INTERVALS[currentPhaseIdx] ?? 1500);
		}
	}

	$effect(() => {
		if (isSearching && results.length === 0) {
			// Reset and start stepper
			currentPhaseIdx = 0;
			phaseTimerId = setTimeout(advancePhase, PHASE_INTERVALS[0]);
		}

		return () => {
			if (phaseTimerId) clearTimeout(phaseTimerId);
		};
	});

	const currentPhase: SearchPhase = $derived(
		!isSearching || results.length > 0 ? 'done' : phases[currentPhaseIdx].id
	);

	const isDone = $derived(currentPhase === 'done');

	// ─── Helpers ─────────────────────────────────────────────────────────

	function getDomain(urlStr: string): string {
		try {
			return new URL(urlStr).hostname.replace('www.', '');
		} catch {
			return 'web';
		}
	}

	function getFavicon(urlStr: string): string {
		try {
			const hostname = new URL(urlStr).hostname;
			return `https://www.google.com/s2/favicons?sz=32&domain=${hostname}`;
		} catch {
			return '';
		}
	}

	function getSnippet(result: SearchResult): string {
		const raw = result.content || result.title || '';
		return raw.length > 180 ? raw.slice(0, 177) + '…' : raw;
	}

	let faviconErrors: Record<number, boolean> = $state({});

	function handleFaviconError(idx: number) {
		faviconErrors[idx] = true;
	}
</script>

<!-- ─── Template ────────────────────────────────────────────────────── -->

<Collapsible.Root
	open={isOpen}
	onOpenChange={(value) => {
		isOpen = value;
	}}
	class="my-2"
>
	<Card
		class="gap-0 border-border/60 bg-card/45 backdrop-blur-md hover:bg-card/55
		       transition-all duration-300 rounded-xl shadow-[0_2px_8px_rgba(0,0,0,0.06)]
		       py-0 overflow-hidden"
	>
		<!-- ─── Trigger Header ─────────────────────────────────────── -->
		<Collapsible.Trigger
			class="flex w-full cursor-pointer items-center justify-between gap-3
			       p-3.5 hover:text-foreground text-muted-foreground
			       transition-colors duration-150"
		>
			<div class="flex min-w-0 items-center gap-2.5">
				<!-- Globe icon -->
				<div class="relative flex-shrink-0">
					{#if !isDone}
						<!-- Pulsing ring while searching -->
						<span
							class="absolute inset-0 rounded-full animate-ping
							       bg-primary/20 duration-1000"
						></span>
					{/if}
					<Globe
						class="relative h-4 w-4 {isDone
							? 'text-primary'
							: 'text-primary animate-pulse'}"
					/>
				</div>

				<!-- Status text -->
				<div class="flex min-w-0 flex-col gap-0.5">
					{#if isDone}
						<span class="text-xs font-semibold tracking-wide text-foreground/80">
							Buscó en la web
						</span>
						<span
							class="truncate text-[11px] text-muted-foreground/70 max-w-[220px] sm:max-w-[360px]"
						>
							"{query}"
						</span>
					{:else}
						<span class="text-xs font-semibold tracking-wide text-foreground/80">
							Buscando en la web…
						</span>
						<span
							class="truncate text-[11px] text-primary/80 italic max-w-[220px] sm:max-w-[360px]"
						>
							"{query}"
						</span>
					{/if}
				</div>
			</div>

			<!-- Right side: count badge + chevron -->
			<div class="flex flex-shrink-0 items-center gap-2">
				{#if isDone && results.length > 0}
					<span
						class="rounded-full bg-primary/10 px-2 py-0.5 text-[10px]
						       font-semibold text-primary tabular-nums"
					>
						{results.length}
						{results.length === 1 ? 'fuente' : 'fuentes'}
					</span>
				{/if}
				<div
					class="flex h-6 w-6 items-center justify-center rounded-md
					       text-muted-foreground transition-colors hover:bg-muted/50
					       hover:text-foreground"
				>
					<ChevronDown
						class="h-3.5 w-3.5 transition-transform duration-300
						       {isOpen ? 'rotate-180' : ''}"
					/>
				</div>
			</div>
		</Collapsible.Trigger>

		<!-- ─── Collapsible Body ───────────────────────────────────── -->
		<Collapsible.Content>
			<div
				class="border-t border-border/40 px-4 pb-4 pt-3.5 bg-muted/5
				       space-y-4"
			>
				<!-- ─── Phase Stepper ─────────────────────────────── -->
				{#if !isDone}
					<div class="flex flex-col gap-1.5">
						{#each phases as phase, idx}
							{@const PhaseIcon = phase.icon}
							{@const isActive = idx === currentPhaseIdx}
							{@const isCompleted = idx < currentPhaseIdx}
							<div
								class="flex items-center gap-2.5 py-1 px-2 rounded-md
								       transition-all duration-500 ease-out
								       {isActive
									? 'bg-primary/5 text-foreground'
									: isCompleted
										? 'text-muted-foreground/60'
										: 'text-muted-foreground/30'}"
							>
								<!-- Step indicator -->
								<div class="relative flex-shrink-0">
									{#if isCompleted}
										<div
											class="flex h-5 w-5 items-center justify-center
											       rounded-full bg-primary/15"
										>
											<Check class="h-3 w-3 text-primary" />
										</div>
									{:else if isActive}
										<div
											class="flex h-5 w-5 items-center justify-center
											       rounded-full bg-primary/10"
										>
											<PhaseIcon class="h-3 w-3 text-primary animate-pulse" />
										</div>
									{:else}
										<div
											class="flex h-5 w-5 items-center justify-center
											       rounded-full bg-muted/40"
										>
											<PhaseIcon class="h-3 w-3 text-muted-foreground/40" />
										</div>
									{/if}
								</div>

								<!-- Step label -->
								<span
									class="text-[11px] font-medium leading-tight
									       transition-opacity duration-300
									       {isActive ? 'opacity-100' : isCompleted ? 'opacity-60' : 'opacity-30'}"
								>
									{phase.label}
								</span>
							</div>
						{/each}
					</div>
				{/if}

				<!-- ─── Sources Grid ──────────────────────────────── -->
				{#if isDone && results.length > 0}
					<div>
						<span
							class="mb-2 block text-[10px] font-semibold uppercase
							       tracking-widest text-muted-foreground/50"
						>
							Fuentes consultadas
						</span>
						<div
							class="grid gap-2
							       grid-cols-1 sm:grid-cols-2 lg:grid-cols-3"
						>
							{#each results as result, idx}
								<Tooltip.Provider>
									<Tooltip.Root delayDuration={300}>
										<Tooltip.Trigger asChild>
											{#snippet children({ props })}
												<a
													{...props}
													href={result.url}
													target="_blank"
													rel="noopener noreferrer"
													class="group flex items-center gap-2.5 rounded-lg
													       border border-border/40 bg-card/30
													       px-3 py-2.5 text-left
													       transition-all duration-200
													       hover:border-primary/30 hover:bg-card/60
													       hover:shadow-[0_2px_12px_rgba(0,0,0,0.08)]
													       active:scale-[0.98]"
												>
													<!-- Favicon -->
													<div class="flex-shrink-0">
														{#if !faviconErrors[idx] && (result.icon || getFavicon(result.url))}
															<img
																src={result.icon || getFavicon(result.url)}
																alt=""
																class="h-5 w-5 rounded-sm object-contain"
																onerror={() => handleFaviconError(idx)}
															/>
														{:else}
															<div
																class="flex h-5 w-5 items-center justify-center
																       rounded-sm bg-primary/10 text-[10px]
																       font-bold text-primary"
															>
																{getDomain(result.url)[0]?.toUpperCase() ?? 'W'}
															</div>
														{/if}
													</div>

													<!-- Title + domain -->
													<div class="flex min-w-0 flex-1 flex-col gap-0.5">
														<span
															class="truncate text-[12px] font-medium
															       leading-tight text-foreground/85
															       group-hover:text-foreground"
														>
															{result.title || getDomain(result.url)}
														</span>
														<span
															class="flex items-center gap-1 text-[10px]
															       text-muted-foreground/60"
														>
															{getDomain(result.url)}
															<ExternalLink
																class="h-2.5 w-2.5 opacity-0
																       transition-opacity duration-200
																       group-hover:opacity-100"
															/>
														</span>
													</div>
												</a>
											{/snippet}
										</Tooltip.Trigger>
										<Tooltip.Content
											side="top"
											class="max-w-xs text-xs leading-relaxed"
										>
											{getSnippet(result) || 'Sin extracto disponible'}
										</Tooltip.Content>
									</Tooltip.Root>
								</Tooltip.Provider>
							{/each}
						</div>
					</div>
				{:else if isDone && results.length === 0}
					<p class="text-center text-[11px] italic text-muted-foreground/50 py-2">
						No se encontraron fuentes para esta consulta.
					</p>
				{/if}
			</div>
		</Collapsible.Content>
	</Card>
</Collapsible.Root>
