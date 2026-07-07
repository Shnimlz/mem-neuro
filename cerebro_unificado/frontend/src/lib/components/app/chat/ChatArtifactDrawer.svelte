<script lang="ts">
	import { slide } from 'svelte/transition';
	import { chatStore } from '$lib/stores/chat.svelte';
	import hljs from 'highlight.js';
	import { browser } from '$app/environment';
	import { copyToClipboard } from '$lib/utils';
	import { isMobile } from '$lib/stores/viewport.svelte';

	import githubDarkCss from 'highlight.js/styles/github-dark.css?inline';

	import XIcon from '@lucide/svelte/icons/x';
	import Copy from '@lucide/svelte/icons/copy';
	import Check from '@lucide/svelte/icons/check';
	import Download from '@lucide/svelte/icons/download';
	import Code2 from '@lucide/svelte/icons/code-2';
	import Eye from '@lucide/svelte/icons/eye';
	import Maximize2 from '@lucide/svelte/icons/maximize-2';
	import Minimize2 from '@lucide/svelte/icons/minimize-2';
	import * as Tooltip from '$lib/components/ui/tooltip';

	type TabMode = 'source' | 'preview';

	// ─── State ───────────────────────────────────────────────────────────

	let activeTab = $state<TabMode>('source');
	let iframeRef = $state<HTMLIFrameElement | null>(null);
	let highlightedHtml = $state('');
	let copied = $state(false);
	let copyTimer: ReturnType<typeof setTimeout> | undefined;
	let isExpanded = $state(false); // Squeeze/Expand width

	// Bind to the global chatStore codePreviewState
	let previewState = $derived(chatStore.codePreviewState);
	let isOpen = $derived(previewState.open);
	let code = $derived(previewState.code);
	let language = $derived(previewState.language);

	// ─── Highlighting ────────────────────────────────────────────────────

	function loadHighlightTheme() {
		if (!browser) return;
		const existing = document.querySelectorAll('style[data-highlight-theme-drawer]');
		existing.forEach((s) => s.remove());
		const style = document.createElement('style');
		style.setAttribute('data-highlight-theme-drawer', 'true');
		style.textContent = githubDarkCss;
		document.head.appendChild(style);
	}

	$effect(() => {
		if (!isOpen) return;
		loadHighlightTheme();

		if (!code) {
			highlightedHtml = '';
			return;
		}

		try {
			const lang = language.toLowerCase();
			const isSupported = hljs.getLanguage(lang);
			if (isSupported) {
				highlightedHtml = hljs.highlight(code, { language: lang }).value;
			} else {
				highlightedHtml = hljs.highlightAuto(code).value;
			}
		} catch {
			highlightedHtml = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
		}
	});

	// ─── Line numbers ────────────────────────────────────────────────────

	const lines = $derived(code ? code.split('\n') : []);
	const lineCount = $derived(lines.length);

	// ─── Iframe preview ──────────────────────────────────────────────────

	const canPreview = $derived(
		['html', 'svg'].includes(language?.toLowerCase() ?? '')
	);

	// Automatically default to 'preview' tab if HTML/SVG, otherwise 'source'
	$effect(() => {
		if (isOpen) {
			activeTab = canPreview ? 'preview' : 'source';
		}
	});

	$effect(() => {
		if (!iframeRef) return;
		if (isOpen && activeTab === 'preview') {
			iframeRef.srcdoc = code;
		} else {
			iframeRef.srcdoc = '';
		}
	});

	// ─── Copy ────────────────────────────────────────────────────────────

	async function handleCopy() {
		await copyToClipboard(code);
		copied = true;
		if (copyTimer) clearTimeout(copyTimer);
		copyTimer = setTimeout(() => {
			copied = false;
		}, 2000);
	}

	// ─── Download ────────────────────────────────────────────────────────

	const LANG_EXT: Record<string, string> = {
		javascript: 'js', typescript: 'ts', python: 'py', ruby: 'rb',
		shell: 'sh', bash: 'sh', csharp: 'cs', cpp: 'cpp', c: 'c',
		java: 'java', go: 'go', rust: 'rs', swift: 'swift', kotlin: 'kt',
		php: 'php', html: 'html', css: 'css', json: 'json', yaml: 'yaml',
		xml: 'xml', sql: 'sql', markdown: 'md', svelte: 'svelte', vue: 'vue',
		jsx: 'jsx', tsx: 'tsx', dart: 'dart', r: 'r', lua: 'lua',
		haskell: 'hs', toml: 'toml', text: 'txt', plaintext: 'txt'
	};

	function handleDownload() {
		const ext = LANG_EXT[language?.toLowerCase()] || language || 'txt';
		const blob = new Blob([code], { type: 'text/plain;charset=utf-8' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `code.${ext}`;
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(url);
	}

	// ─── Close ───────────────────────────────────────────────────────────

	function handleClose() {
		chatStore.codePreviewState.open = false;
	}

	const displayLanguage = $derived(
		language ? language.charAt(0).toUpperCase() + language.slice(1).toLowerCase() : 'Text'
	);
</script>

{#if isOpen}
	<div
		class="artifact-drawer-container border-l border-white/8 bg-[#0d1117] text-[#c9d1d9] flex flex-col h-full relative z-30 transition-all duration-300 ease-in-out shadow-2xl"
		class:w-full={isMobile.current}
		class:md:w-\[450px\]={!isExpanded && !isMobile.current}
		class:lg:w-\[550px\]={!isExpanded && !isMobile.current}
		class:xl:w-\[650px\]={!isExpanded && !isMobile.current}
		class:md:w-\[85vw\]={isExpanded && !isMobile.current}
		transition:slide={{ direction: 'right', duration: 300 }}
	>
		<!-- ─── Header ──────────────────────────────────────────────────── -->
		<div class="flex flex-shrink-0 items-center justify-between border-b border-white/8 bg-[#161b22] px-4 py-3">
			<div class="flex items-center gap-3">
				<span class="rounded-md bg-white/6 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-[#8b949e]">
					{displayLanguage}
				</span>

				<!-- Tabs -->
				<div class="flex items-center gap-1 rounded-lg bg-white/4 p-0.5">
					<button
						onclick={() => (activeTab = 'source')}
						class="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all duration-200
						       {activeTab === 'source'
							? 'bg-white/10 text-white shadow-sm'
							: 'text-[#8b949e] hover:text-[#c9d1d9] hover:bg-white/5'}"
					>
						<Code2 class="h-3.5 w-3.5" />
						Código
					</button>
					{#if canPreview}
						<button
							onclick={() => (activeTab = 'preview')}
							class="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all duration-200
							       {activeTab === 'preview'
								? 'bg-white/10 text-white shadow-sm'
								: 'text-[#8b949e] hover:text-[#c9d1d9] hover:bg-white/5'}"
						>
							<Eye class="h-3.5 w-3.5" />
							Vista previa
						</button>
					{/if}
				</div>
			</div>

			<!-- Header Actions -->
			<div class="flex items-center gap-1.5">
				<!-- Expand / Collapse width (Desktop only) -->
				{#if !isMobile.current}
					<Tooltip.Root>
						<Tooltip.Trigger asChild>
							{#snippet children({ props })}
								<button
									{...props}
									onclick={() => (isExpanded = !isExpanded)}
									class="flex h-8 w-8 items-center justify-center rounded-md text-[#8b949e] transition-all duration-200 hover:bg-white/8 hover:text-white"
									aria-label={isExpanded ? 'Collapse' : 'Expand'}
								>
									{#if isExpanded}
										<Minimize2 class="h-4 w-4" />
									{:else}
										<Maximize2 class="h-4 w-4" />
									{/if}
								</button>
							{/snippet}
						</Tooltip.Trigger>
						<Tooltip.Content side="bottom">
							<p>{isExpanded ? 'Contraer' : 'Expandir'}</p>
						</Tooltip.Content>
					</Tooltip.Root>
				{/if}

				<!-- Copy -->
				<Tooltip.Root>
					<Tooltip.Trigger asChild>
						{#snippet children({ props })}
							<button
								{...props}
								onclick={handleCopy}
								class="flex h-8 w-8 items-center justify-center rounded-md text-[#8b949e] transition-all duration-200 hover:bg-white/8 hover:text-white"
								aria-label="Copy"
							>
								{#if copied}
									<Check class="h-4 w-4 text-green-400" />
								{:else}
									<Copy class="h-4 w-4" />
								{/if}
							</button>
						{/snippet}
					</Tooltip.Trigger>
					<Tooltip.Content side="bottom">
						<p>{copied ? 'Copiado' : 'Copiar'}</p>
					</Tooltip.Content>
				</Tooltip.Root>

				<!-- Download -->
				<Tooltip.Root>
					<Tooltip.Trigger asChild>
						{#snippet children({ props })}
							<button
								{...props}
								onclick={handleDownload}
								class="flex h-8 w-8 items-center justify-center rounded-md text-[#8b949e] transition-all duration-200 hover:bg-white/8 hover:text-white"
								aria-label="Download"
							>
								<Download class="h-4 w-4" />
							</button>
						{/snippet}
					</Tooltip.Trigger>
					<Tooltip.Content side="bottom">
						<p>Descargar</p>
					</Tooltip.Content>
				</Tooltip.Root>

				<div class="h-4 w-px bg-white/10 mx-1"></div>

				<!-- Close -->
				<button
					onclick={handleClose}
					class="flex h-8 w-8 items-center justify-center rounded-md text-[#8b949e] transition-all duration-200 hover:bg-white/8 hover:text-white"
					aria-label="Close"
				>
					<XIcon class="h-4 w-4" />
				</button>
			</div>
		</div>

		<!-- ─── Content ─── -->
		<div class="flex-grow overflow-auto relative flex flex-col">
			{#if activeTab === 'source'}
				<div class="flex-grow overflow-auto font-mono text-xs leading-relaxed flex">
					<!-- Line numbers column -->
					<div class="select-none border-r border-white/5 bg-[#090d12] px-3.5 py-4 text-right text-[#484f58] min-w-[3.5rem]">
						{#each lines as _, i}
							<div>{i + 1}</div>
						{/each}
					</div>

					<!-- Highlights code -->
					<pre class="flex-grow overflow-x-auto bg-[#0d1117] p-4 text-[#c9d1d9]"><code class="hljs">{@html highlightedHtml}</code></pre>
				</div>
			{:else if activeTab === 'preview'}
				<div class="w-full flex-grow bg-white">
					<iframe
						bind:this={iframeRef}
						title="Artifact Live Preview"
						class="h-full w-full border-none bg-white"
						sandbox="allow-scripts"
					></iframe>
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	.artifact-drawer-container {
		height: 100dvh;
	}
</style>
