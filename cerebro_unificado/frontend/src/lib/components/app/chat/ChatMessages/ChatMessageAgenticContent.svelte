<script lang="ts">
	import { Wrench, Loader2, Brain, Globe, Clock } from '@lucide/svelte';
	import {
		ChatMessageStatistics,
		CollapsibleContentBlock,
		MarkdownContent,
		SyntaxHighlightedCode,
		ChatMessageActionCardPermissionRequest,
		ChatMessageActionCardContinueRequest,
		WeatherWidget
	} from '$lib/components/app';
	import WebSearchStatus from './WebSearchStatus.svelte';
	import { animate, stagger } from 'animejs';

	import {
		AgenticSectionType,
		ChatMessageStatsView,
		FileTypeText,
		ToolPermissionDecision
	} from '$lib/enums';
	import type {
		ChatMessageAgenticTimings,
		ChatMessageAgenticTurnStats,
		DatabaseMessage
	} from '$lib/types';
	import {
		deriveAgenticSections,
		formatJsonPretty,
		parseToolResultWithImages,
		type AgenticSection,
		type ToolResultLine
	} from '$lib/utils';
	import {
		agenticPendingPermissionRequest,
		agenticResolvePermission,
		agenticPendingContinueRequest,
		agenticResolveContinue,
		agenticLastError
	} from '$lib/stores/agentic.svelte';
	import { config } from '$lib/stores/settings.svelte';
	import { chatStore } from '$lib/stores/chat.svelte';

	interface Props {
		message: DatabaseMessage;
		toolMessages?: DatabaseMessage[];
		isStreaming?: boolean;
		isLastAssistantMessage?: boolean;
		highlightTurns?: boolean;
	}

	let {
		message,
		toolMessages = [],
		isStreaming = false,
		isLastAssistantMessage = false,
		highlightTurns = false
	}: Props = $props();

	let expandedStates: Record<number, boolean> = $state({});

	const showToolCallInProgress = $derived(config().showToolCallInProgress as boolean);
	const showThoughtInProgress = $derived(config().showThoughtInProgress as boolean);
	const renderThinkingAsMarkdown = $derived(config().renderThinkingAsMarkdown as boolean);

	const hasReasoningError = $derived(
		isLastAssistantMessage ? !!agenticLastError(message.convId) : false
	);

	let permissionDismissed = $state(false);

	const pendingPermission = $derived(
		isStreaming && isLastAssistantMessage ? agenticPendingPermissionRequest(message.convId) : null
	);

	// Reset dismissed when pendingPermission changes (new request or cleared)
	let prevPendingRef: typeof pendingPermission = null;
	$effect(() => {
		if (pendingPermission !== prevPendingRef) {
			prevPendingRef = pendingPermission;
			if (pendingPermission) {
				permissionDismissed = false;
			}
		}
	});

	function handlePermission(decision: ToolPermissionDecision) {
		permissionDismissed = true;
		agenticResolvePermission(message.convId, decision);
	}

	let continueDismissed = $state(false);

	const pendingContinue = $derived(
		isStreaming && isLastAssistantMessage ? agenticPendingContinueRequest(message.convId) : false
	);

	let prevContinueRef = false;
	$effect(() => {
		if (pendingContinue !== prevContinueRef) {
			prevContinueRef = pendingContinue;
			if (pendingContinue) {
				continueDismissed = false;
			}
		}
	});

	function handleContinue(shouldContinue: boolean) {
		continueDismissed = true;
		agenticResolveContinue(message.convId, shouldContinue);
	}

	const sections = $derived(deriveAgenticSections(message, toolMessages, [], isStreaming));

	// Parse tool results with images
	const sectionsParsed = $derived(
		sections.map((section) => ({
			...section,
			parsedLines: section.toolResult
				? parseToolResultWithImages(section.toolResult, section.toolResultExtras || message?.extra)
				: ([] as ToolResultLine[])
		}))
	);

	// Group flat sections into agentic turns
	// A new turn starts when a non-tool section follows a tool section
	const turnGroups = $derived.by(() => {
		const turns: { sections: (typeof sectionsParsed)[number][]; flatIndices: number[] }[] = [];
		let currentTurn: (typeof sectionsParsed)[number][] = [];
		let currentIndices: number[] = [];
		let prevWasTool = false;

		for (let i = 0; i < sectionsParsed.length; i++) {
			const section = sectionsParsed[i];
			const isTool =
				section.type === AgenticSectionType.TOOL_CALL ||
				section.type === AgenticSectionType.TOOL_CALL_PENDING ||
				section.type === AgenticSectionType.TOOL_CALL_STREAMING;

			if (!isTool && prevWasTool && currentTurn.length > 0) {
				turns.push({ sections: currentTurn, flatIndices: currentIndices });
				currentTurn = [];
				currentIndices = [];
			}

			currentTurn.push(section);
			currentIndices.push(i);
			prevWasTool = isTool;
		}

		if (currentTurn.length > 0) {
			turns.push({ sections: currentTurn, flatIndices: currentIndices });
		}

		return turns;
	});

	// ─── Fuentes consolidadas (herramienta + markdown) al pie de la respuesta ───
	const consolidatedSources = $derived.by(() => {
		const sourcesList: Array<{ title: string; url: string; domain: string }> = [];
		const seenUrls = new Set<string>();

		// 1. Añadir fuentes reales del toolResult
		for (const section of sectionsParsed) {
			if (
				section.type === AgenticSectionType.TOOL_CALL &&
				section.toolName === 'web_search' &&
				section.toolResult
			) {
				const results = parseWebSearchResults(section.toolResult);
				for (const item of results) {
					if (!seenUrls.has(item.url)) {
						seenUrls.add(item.url);
						sourcesList.push({
							title: item.title,
							url: item.url,
							domain: item.domain
						});
					}
				}
			}
		}

		// 2. Extraer fuentes descritas en el markdown
		for (const section of sectionsParsed) {
			if (section.type === AgenticSectionType.TEXT && section.content) {
				const parsed = parseWebSearchTags(section.content);
				const weatherCleaned = parseWeatherDataTag(parsed.cleanText);
				const extracted = extractSourcesFromText(weatherCleaned.cleanText);
				for (const src of extracted.sources) {
					if (!seenUrls.has(src.url)) {
						seenUrls.add(src.url);
						sourcesList.push(src);
					}
				}
			}
		}

		return sourcesList;
	});

	function getDefaultExpanded(section: AgenticSection): boolean {
		if (
			section.type === AgenticSectionType.TOOL_CALL_PENDING ||
			section.type === AgenticSectionType.TOOL_CALL_STREAMING
		) {
			return showToolCallInProgress;
		}

		if (section.type === AgenticSectionType.REASONING_PENDING) {
			return showThoughtInProgress;
		}

		return false;
	}

	function isExpanded(index: number, section: AgenticSection): boolean {
		if (expandedStates[index] !== undefined) {
			return expandedStates[index];
		}

		return getDefaultExpanded(section);
	}

	function toggleExpanded(index: number, section: AgenticSection) {
		const currentState = isExpanded(index, section);

		expandedStates[index] = !currentState;
	}

	function buildTurnAgenticTimings(stats: ChatMessageAgenticTurnStats): ChatMessageAgenticTimings {
		return {
			turns: 1,
			toolCallsCount: stats.toolCalls.length,
			toolsMs: stats.toolsMs,
			toolCalls: stats.toolCalls,
			llm: stats.llm
		};
	}

	function parseWebSearchResults(text: string) {
		const items: Array<{ title: string; url: string; domain: string; summary: string }> = [];
		// Split by blocks starting with [number]
		const parts = text.split(/\[\d+\]/g);
		for (const part of parts) {
			if (!part.trim()) continue;
			
			const titleMatch = part.match(/Title:\s*([^\n]+)/i);
			const urlMatch = part.match(/URL:\s*([^\n]+)/i);
			const summaryMatch = part.match(/Summary:\s*([\s\S]+)/i);

			if (titleMatch && urlMatch) {
				const url = urlMatch[1].trim();
				let domain = '';
				try {
					domain = new URL(url).hostname.replace('www.', '');
				} catch {
					domain = url;
				}
				items.push({
					title: titleMatch[1].trim(),
					url,
					domain,
					summary: summaryMatch ? summaryMatch[1].trim() : ''
				});
			}
		}
		return items;
	}

	// ─── Parser de <web_search_results> para WebSearchStatus ───
	const WEB_SEARCH_TAG_RE = /<web_search_results>([\s\S]*?)<\/web_search_results>/g;
	const WEB_SEARCH_STATUS_RE = /<web_search_status>([\s\S]*?)<\/web_search_status>/g;

	interface WebSearchBlock {
		query: string;
		status?: 'analyzing' | 'searching' | 'extracting' | 'synthesizing' | 'done';
		results?: { title: string; url: string; icon?: string; content?: string }[];
	}

	function parseWebSearchTags(text: string): { cleanText: string; searches: WebSearchBlock[] } {
		const searches: WebSearchBlock[] = [];
		let cleanText = text.replace(WEB_SEARCH_TAG_RE, (_match, jsonStr) => {
			try {
				const parsed = JSON.parse(jsonStr.trim());
				if (parsed && parsed.query) {
					searches.push({
						query: parsed.query,
						status: 'done',
						results: parsed.results || []
					});
				}
			} catch (e) {
				// JSON inválido
			}
			return '';
		});

		cleanText = cleanText.replace(WEB_SEARCH_STATUS_RE, (_match, jsonStr) => {
			try {
				const parsed = JSON.parse(jsonStr.trim());
				if (parsed && parsed.query) {
					const existing = searches.find(s => s.query === parsed.query);
					if (existing) {
						if (existing.status !== 'done') {
							existing.status = parsed.status;
						}
					} else {
						searches.push({
							query: parsed.query,
							status: parsed.status,
							results: []
						});
					}
				}
			} catch (e) {
				// JSON inválido
			}
			return '';
		});

		return { cleanText: cleanText.trim(), searches };
	}

	function extractShortReasoning(text: string | undefined): string {
		if (!text) return '';
		const match = text.match(/^[^.!?\n]+(?:[.!?]|\n\n)?/);
		let sentence = match ? match[0].trim() : text.trim();
		sentence = sentence.replace(/\s+/g, ' ');
		if (sentence.length > 120) {
			sentence = sentence.slice(0, 117) + '…';
		}
		return sentence;
	}

	// ─── Extractor de fuentes de búsqueda Markdown a Widgets premium ───
	function extractSourcesFromText(text: string): { cleanText: string; sources: { title: string; url: string; domain: string }[] } {
		if (!text) return { cleanText: '', sources: [] };
		const lines = text.split('\n');
		const sources: { title: string; url: string; domain: string }[] = [];
		const remainingLines: string[] = [];
		let collectingSources = true;

		// Procesar de abajo hacia arriba para capturar las fuentes al final del mensaje
		for (let i = lines.length - 1; i >= 0; i--) {
			const line = lines[i].trim();
			if (!line) {
				if (sources.length > 0) continue;
				remainingLines.unshift(lines[i]);
				continue;
			}

			// Detectar líneas que siguen el formato "* Fuente X: [Título](URL)" o variantes
			const match = line.match(/^(?:[-*+•]|\d+\.)?\s*(?:\*\*?)?Fuente\s*\d+\s*:?\s*(?:\*\*?)?\s*\[([^\]]+)\]\(([^)]+)\)/i);
			if (match && collectingSources) {
				const title = match[1].trim();
				const url = match[2].trim();
				let domain = '';
				try {
					domain = new URL(url).hostname.replace('www.', '');
				} catch {
					domain = 'link';
				}
				sources.unshift({ title, url, domain });
			} else {
				collectingSources = false;
				remainingLines.unshift(lines[i]);
			}
		}

		return {
			cleanText: remainingLines.join('\n').trim(),
			sources
		};
	}

	function animateSources(node: HTMLElement) {
		requestAnimationFrame(() => {
			const cards = node.querySelectorAll('.source-card');
			if (cards.length > 0) {
				animate(cards, {
					opacity: [0, 1],
					scale: [0.93, 1],
					translateY: [12, 0],
					ease: 'easeOutElastic(1, 0.7)',
					duration: 800,
					delay: stagger(60)
				});
			}
		});
	}
	const WEATHER_DATA_TAG_RE = /<weather_data>([\s\S]*?)<\/weather_data>/g;

	function parseWeatherDataTag(text: string): { cleanText: string; weather: any | null } {
		if (!text) return { cleanText: '', weather: null };
		let weather: any | null = null;
		const cleanText = text.replace(WEATHER_DATA_TAG_RE, (_match, jsonStr) => {
			try {
				weather = JSON.parse(jsonStr.trim());
			} catch (e) {
				// JSON inválido
			}
			return '';
		});
		return { cleanText: cleanText.trim(), weather };
	}
</script>

{#snippet renderSection(section: (typeof sectionsParsed)[number], index: number)}
	{#if section.type === AgenticSectionType.TEXT}
		{@const parsed = parseWebSearchTags(section.content)}
		{#each parsed.searches as ws}
			<WebSearchStatus
				query={ws.query}
				results={ws.results || []}
				isSearching={ws.status !== 'done'}
				status={ws.status}
			/>
		{/each}
		{@const sourceData = extractSourcesFromText(parsed.cleanText)}
		{@const weatherParsed = parseWeatherDataTag(sourceData.cleanText)}
		<div class="agentic-text">
			<MarkdownContent
				content={weatherParsed.cleanText}
				attachments={message?.extra}
				onMaximizeCode={(code, lang) => chatStore.showCodePreview(code, lang)}
			/>
		</div>

		{#if weatherParsed.weather}
			<WeatherWidget data={weatherParsed.weather} />
		{/if}
	{:else if section.type === AgenticSectionType.TOOL_CALL_STREAMING}
		{@const streamingIcon = isStreaming ? Loader2 : Loader2}
		{@const streamingIconClass = isStreaming ? 'h-4 w-4 animate-spin' : 'h-4 w-4'}

		<CollapsibleContentBlock
			open={isExpanded(index, section)}
			class="my-2"
			icon={streamingIcon}
			iconClass={streamingIconClass}
			title={section.toolName || 'Tool call'}
			subtitle={isStreaming ? '' : 'incomplete'}
			{isStreaming}
			onToggle={() => toggleExpanded(index, section)}
		>
			<div class="pt-3">
				<div class="my-3 flex items-center gap-2 text-xs text-muted-foreground">
					<span>Arguments:</span>

					{#if isStreaming}
						<Loader2 class="h-3 w-3 animate-spin" />
					{/if}
				</div>
				{#if section.toolArgs}
					<SyntaxHighlightedCode
						code={formatJsonPretty(section.toolArgs)}
						language={FileTypeText.JSON}
						maxHeight="20rem"
						class="text-xs"
						onMaximize={(code, lang) => chatStore.showCodePreview(code, lang)}
					/>
				{:else if isStreaming}
					<div class="rounded bg-muted/30 p-2 text-xs text-muted-foreground italic">
						Receiving arguments...
					</div>
				{:else}
					<div
						class="rounded bg-yellow-500/10 p-2 text-xs text-yellow-600 italic dark:text-yellow-400"
					>
						Response was truncated
					</div>
				{/if}
			</div>
		</CollapsibleContentBlock>
	{:else if section.type === AgenticSectionType.TOOL_CALL || section.type === AgenticSectionType.TOOL_CALL_PENDING}
		{@const isPending = section.type === AgenticSectionType.TOOL_CALL_PENDING}
		{@const toolIcon = isPending ? Loader2 : Wrench}
		{@const toolIconClass = isPending ? 'h-4 w-4 animate-spin' : 'h-4 w-4'}

		<CollapsibleContentBlock
			open={isExpanded(index, section)}
			class="my-2"
			icon={toolIcon}
			iconClass={toolIconClass}
			title={section.toolName || ''}
			subtitle={isPending ? 'executing...' : undefined}
			isStreaming={isPending}
			onToggle={() => toggleExpanded(index, section)}
		>
			{#if section.toolArgs && section.toolArgs !== '{}'}
				<div class="pt-3">
					<div class="flex items-center gap-1.5 mb-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/80">
						<span class="w-1.5 h-1.5 rounded-full bg-primary/60"></span>
						Arguments
					</div>

					<div class="rounded-lg border border-border/40 overflow-hidden">
						<SyntaxHighlightedCode
							code={formatJsonPretty(section.toolArgs)}
							language={FileTypeText.JSON}
							maxHeight="20rem"
							class="text-[11px] font-mono leading-relaxed"
							onMaximize={(code, lang) => chatStore.showCodePreview(code, lang)}
						/>
					</div>
				</div>
			{/if}

			<div class="pt-3.5">
				<div class="flex items-center gap-2 mb-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground/80">
					<span class="w-1.5 h-1.5 rounded-full {isPending ? 'bg-amber-400 animate-pulse' : 'bg-green-400'}"></span>
					Result
				</div>

				{#if section.toolName === 'web_search'}
					{@const shortReason = extractShortReasoning(message?.reasoningContent)}
					{#if shortReason}
						<div class="flex items-center gap-2 mb-3 text-xs text-muted-foreground">
							<Clock class="h-3.5 w-3.5 shrink-0 text-muted-foreground/80" />
							<span>{shortReason}</span>
						</div>
					{/if}
				{/if}

				{#if isPending}
					<div class="flex flex-col gap-2 rounded-lg border border-border/20 bg-muted/40 p-4">
						<div class="flex items-center gap-2.5 text-xs text-muted-foreground/80">
							<Loader2 class="h-3.5 w-3.5 animate-spin text-primary" />
							<span class="font-sans italic">Buscando en la web...</span>
						</div>
						<div class="w-full bg-muted/70 rounded-full h-1 overflow-hidden mt-1.5 relative">
							<div class="bg-primary h-1 rounded-full absolute left-0 top-0 animate-[pulse_1.5s_infinite]" style="width: 45%; background: linear-gradient(90deg, var(--primary) 0%, #b4befe 100%)"></div>
						</div>
					</div>
				{:else if section.toolResult}
					{#if section.toolName === 'web_search'}
						{@const searchItems = parseWebSearchResults(section.toolResult)}
						{#if searchItems.length > 0}
							<div class="flex flex-col gap-2 rounded-xl border border-border/40 bg-card/30 p-4 shadow-sm">
								<div class="flex items-center justify-between text-xs text-muted-foreground/90 border-b border-border/20 pb-2 mb-2">
									<span class="font-medium flex items-center gap-1.5">
										<Globe class="h-3.5 w-3.5 text-primary" />
										Se buscó en la web
									</span>
									<span class="font-mono text-[10px] bg-muted px-2 py-0.5 rounded-full">
										{searchItems.length} resultados
									</span>
								</div>
								
								<div class="flex flex-col gap-2.5">
									{#each searchItems as item, i (i)}
										{@const favicon = `https://www.google.com/s2/favicons?domain=${item.domain}&sz=32`}
										<a
											href={item.url}
											target="_blank"
											rel="noopener noreferrer"
											class="group flex flex-col gap-1 rounded-lg border border-border/10 hover:border-primary/20 bg-muted/20 hover:bg-primary/5 p-3 transition-all duration-200"
										>
											<div class="flex items-start justify-between gap-2 w-full">
												<div class="flex items-start gap-2 min-w-0">
													<img
														src={favicon}
														class="h-4 w-4 rounded-sm shrink-0 mt-0.5"
														alt=""
														loading="lazy"
														onerror={(e) => { e.currentTarget.style.display = 'none'; }}
													/>
													<span class="text-xs font-semibold text-foreground/90 group-hover:text-primary transition-colors leading-tight">
														{item.title}
													</span>
												</div>
												<span class="shrink-0 flex items-center gap-1 text-[10px] text-muted-foreground font-medium bg-muted/80 px-1.5 py-0.5 rounded border border-border/15">
													{item.domain}
												</span>
											</div>
											{#if item.summary}
												<p class="text-[11px] text-muted-foreground/85 line-clamp-2 leading-relaxed">
													{item.summary}
												</p>
											{/if}
										</a>
									{/each}
								</div>
								
								<div class="flex items-center gap-1.5 text-[10px] font-semibold text-green-500 uppercase tracking-wider mt-2 pt-2 border-t border-border/20">
									<span class="w-1.5 h-1.5 rounded-full bg-green-500"></span>
									Listo
								</div>
							</div>
						{:else}
							<div class="overflow-auto rounded-lg border border-border/40 bg-[#0b0d13]/90 p-4 shadow-inner">
								<pre class="font-mono text-xs leading-relaxed text-[#cdd6f4] whitespace-pre-wrap">{section.toolResult}</pre>
							</div>
						{/if}
					{:else}
						<div class="overflow-auto rounded-lg border border-border/40 bg-[#0b0d13]/90 p-4 shadow-inner">
							{#each section.parsedLines as line, i (i)}
								<div class="font-mono text-xs leading-relaxed text-[#cdd6f4] whitespace-pre-wrap">
									{line.text}
								</div>
								{#if line.image}
									<img
										src={line.image.base64Url}
										alt={line.image.name}
										class="mt-3 mb-3 h-auto max-w-full rounded-lg border border-border/20"
										loading="lazy"
									/>
								{/if}
							{/each}
						</div>
					{/if}
				{:else}
					<div class="rounded-lg border border-border/20 bg-muted/30 p-3 text-xs text-muted-foreground/60 italic text-center">No output returned</div>
				{/if}
			</div>
		</CollapsibleContentBlock>
	{:else if section.type === AgenticSectionType.REASONING}
		{@const reasoningSubtitle = section.wasInterrupted
			? hasReasoningError
				? 'Error'
				: 'Cancelled'
			: isStreaming
				? ''
				: undefined}

		<CollapsibleContentBlock
			open={isExpanded(index, section)}
			class="my-2"
			icon={Brain}
			title="Reasoning"
			subtitle={reasoningSubtitle}
			rawContent={section.content}
			onToggle={() => toggleExpanded(index, section)}
		>
			<div class="pt-3">
				{#if renderThinkingAsMarkdown}
					<MarkdownContent
						content={section.content}
						attachments={message?.extra}
						onMaximizeCode={(code, lang) => chatStore.showCodePreview(code, lang)}
					/>
				{:else}
					<div class="text-xs leading-relaxed break-words whitespace-pre-wrap">
						{section.content}
					</div>
				{/if}
			</div>
		</CollapsibleContentBlock>
	{:else if section.type === AgenticSectionType.REASONING_PENDING}
		{@const reasoningTitle = isStreaming ? 'Reasoning...' : 'Reasoning'}
		{@const reasoningSubtitle = isStreaming ? '' : hasReasoningError ? 'Error' : 'Cancelled'}

		<CollapsibleContentBlock
			open={isExpanded(index, section)}
			class="my-2"
			icon={Brain}
			title={reasoningTitle}
			subtitle={reasoningSubtitle}
			rawContent={section.content}
			{isStreaming}
			onToggle={() => toggleExpanded(index, section)}
		>
			<div class="pt-3">
				{#if renderThinkingAsMarkdown}
					<MarkdownContent
						content={section.content}
						attachments={message?.extra}
						onMaximizeCode={(code, lang) => chatStore.showCodePreview(code, lang)}
					/>
				{:else}
					<div class="text-xs leading-relaxed break-words whitespace-pre-wrap">
						{section.content}
					</div>
				{/if}
			</div>
		</CollapsibleContentBlock>
	{/if}
{/snippet}

<div class="agentic-content">
	{#if highlightTurns && turnGroups.length > 1}
		{#each turnGroups as turn, turnIndex (turnIndex)}
			{@const turnStats = message?.timings?.agentic?.perTurn?.[turnIndex]}
			<div class="agentic-turn my-2 hover:bg-muted/80 dark:hover:bg-muted/30">
				<span class="agentic-turn-label">Turn {turnIndex + 1}</span>
				{#each turn.sections as section, sIdx (turn.flatIndices[sIdx])}
					{@render renderSection(section, turn.flatIndices[sIdx])}
				{/each}
				{#if turnStats}
					<div class="turn-stats">
						<ChatMessageStatistics
							promptTokens={turnStats.llm.prompt_n}
							promptMs={turnStats.llm.prompt_ms}
							predictedTokens={turnStats.llm.predicted_n}
							predictedMs={turnStats.llm.predicted_ms}
							agenticTimings={turnStats.toolCalls.length > 0
								? buildTurnAgenticTimings(turnStats)
								: undefined}
							initialView={ChatMessageStatsView.GENERATION}
							hideSummary
						/>
					</div>
				{/if}
			</div>
		{/each}
	{:else}
		{#each sectionsParsed as section, index (index)}
			{@render renderSection(section, index)}
		{/each}
	{/if}

	{#if consolidatedSources.length > 0}
		<div
			use:animateSources
			class="sources-container grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5 mt-4 pt-3 border-t border-border/10 w-full max-w-3xl"
		>
			{#each consolidatedSources as source, i (i)}
				{@const favicon = `https://www.google.com/s2/favicons?domain=${source.domain}&sz=32`}
				<a
					href={source.url}
					target="_blank"
					rel="noopener noreferrer"
					class="source-card group flex items-start gap-2.5 rounded-lg border border-border/10 hover:border-primary/30 bg-muted/20 hover:bg-primary/5 p-2.5 transition-all duration-300 shadow-sm opacity-0 hover:shadow-md"
				>
					<div class="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-background shadow-sm border border-border/10 group-hover:border-primary/20 transition-colors">
						<img
							src={favicon}
							class="h-3.5 w-3.5"
							alt=""
							loading="lazy"
							onerror={(e) => { e.currentTarget.style.display = 'none'; }}
						/>
					</div>
					<div class="flex flex-col min-w-0 leading-tight">
						<span class="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider group-hover:text-primary transition-colors">
							{source.domain}
						</span>
						<span class="text-xs text-foreground/80 line-clamp-1 font-medium mt-0.5 group-hover:text-foreground transition-colors">
							{source.title}
						</span>
					</div>
				</a>
			{/each}
		</div>
	{/if}

	{#if pendingPermission && !permissionDismissed}
		<ChatMessageActionCardPermissionRequest
			toolName={pendingPermission.toolName}
			serverLabel={pendingPermission.serverLabel}
			onDecision={handlePermission}
		/>
	{/if}

	{#if pendingContinue && !continueDismissed}
		<ChatMessageActionCardContinueRequest onDecision={handleContinue} />
	{/if}
</div>

<style>
	.agentic-content {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		width: 100%;
		max-width: 48rem;
	}

	.agentic-text {
		width: 100%;
	}

	.agentic-turn {
		position: relative;
		border: 1.5px dashed var(--muted-foreground);
		border-radius: 0.75rem;
		padding: 1rem;
		transition: background 0.1s;
	}

	.agentic-turn-label {
		position: absolute;
		top: -1rem;
		left: 0.75rem;
		padding: 0 0.375rem;
		background: var(--background);
		font-size: 0.7rem;
		font-weight: 500;
		color: var(--muted-foreground);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.turn-stats {
		margin-top: 0.75rem;
		padding-top: 0.5rem;
		border-top: 1px solid hsl(var(--muted) / 0.5);
	}
</style>
