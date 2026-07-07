<script lang="ts">
	import { Dialog as DialogPrimitive } from 'bits-ui';
	import hljs from 'highlight.js';
	import { browser } from '$app/environment';
	import { mode } from 'mode-watcher';
	import { copyToClipboard } from '$lib/utils';
	import { ColorMode } from '$lib/enums';

	import githubDarkCss from 'highlight.js/styles/github-dark.css?inline';
	import githubLightCss from 'highlight.js/styles/github.css?inline';

	import XIcon from '@lucide/svelte/icons/x';
	import Copy from '@lucide/svelte/icons/copy';
	import Check from '@lucide/svelte/icons/check';
	import Download from '@lucide/svelte/icons/download';
	import Code2 from '@lucide/svelte/icons/code-2';
	import Eye from '@lucide/svelte/icons/eye';
	import * as Tooltip from '$lib/components/ui/tooltip';

	// ─── Types ───────────────────────────────────────────────────────────

	type TabMode = 'source' | 'preview';

	interface Props {
		open: boolean;
		code: string;
		language: string;
		onOpenChange?: (open: boolean) => void;
	}

	// ─── Props & State ───────────────────────────────────────────────────

	let { open = $bindable(), code, language, onOpenChange }: Props = $props();

	let activeTab: TabMode = $state('source');
	let iframeRef = $state<HTMLIFrameElement | null>(null);

	// ─── Highlighting ────────────────────────────────────────────────────

	let highlightedHtml = $state('');

	function loadHighlightTheme() {
		if (!browser) return;
		const existing = document.querySelectorAll('style[data-highlight-theme-dialog]');
		existing.forEach((s) => s.remove());
		const style = document.createElement('style');
		style.setAttribute('data-highlight-theme-dialog', 'true');
		// Always use dark theme inside the fullscreen dialog
		style.textContent = githubDarkCss;
		document.head.appendChild(style);
	}

	$effect(() => {
		if (!open) return;
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

	$effect(() => {
		if (!iframeRef) return;
		if (open && activeTab === 'preview') {
			iframeRef.srcdoc = code;
		} else {
			iframeRef.srcdoc = '';
		}
	});

	// ─── Copy ────────────────────────────────────────────────────────────

	let copied = $state(false);
	let copyTimer: ReturnType<typeof setTimeout> | undefined;

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

	// ─── Open/Close ──────────────────────────────────────────────────────

	function handleOpenChange(nextOpen: boolean) {
		open = nextOpen;
		if (!nextOpen) activeTab = 'source';
		onOpenChange?.(nextOpen);
	}

	const displayLanguage = $derived(
		language ? language.charAt(0).toUpperCase() + language.slice(1).toLowerCase() : 'Text'
	);
</script>

<!-- ─── Dialog ──────────────────────────────────────────────────────── -->

<DialogPrimitive.Root {open} onOpenChange={handleOpenChange}>
	<DialogPrimitive.Portal>
		<DialogPrimitive.Overlay class="dialog-code-overlay" />

		<DialogPrimitive.Content class="dialog-code-content">
			<div class="flex h-full w-full flex-col bg-[#0d1117] text-[#c9d1d9]">
				<!-- ─── Top Bar ─────────────────────────────────────── -->
				<div
					class="flex flex-shrink-0 items-center justify-between border-b
					       border-white/8 bg-[#161b22] px-4 py-2"
				>
					<!-- Left: Language badge + Tabs -->
					<div class="flex items-center gap-3">
						<span
							class="rounded-md bg-white/6 px-2.5 py-1 text-[11px]
							       font-semibold uppercase tracking-wider text-[#8b949e]"
						>
							{displayLanguage}
						</span>

						<!-- Tab buttons -->
						<div class="flex items-center gap-1 rounded-lg bg-white/4 p-0.5">
							<button
								onclick={() => (activeTab = 'source')}
								class="flex items-center gap-1.5 rounded-md px-3 py-1.5
								       text-xs font-medium transition-all duration-200
								       {activeTab === 'source'
									? 'bg-white/10 text-white shadow-sm'
									: 'text-[#8b949e] hover:text-[#c9d1d9] hover:bg-white/5'}"
							>
								<Code2 class="h-3.5 w-3.5" />
								Código fuente
							</button>
							{#if canPreview}
								<button
									onclick={() => (activeTab = 'preview')}
									class="flex items-center gap-1.5 rounded-md px-3 py-1.5
									       text-xs font-medium transition-all duration-200
									       {activeTab === 'preview'
										? 'bg-white/10 text-white shadow-sm'
										: 'text-[#8b949e] hover:text-[#c9d1d9] hover:bg-white/5'}"
								>
									<Eye class="h-3.5 w-3.5" />
									Vista previa
								</button>
							{/if}
						</div>

						<span class="text-[10px] font-mono text-[#484f58]">
							{lineCount} {lineCount === 1 ? 'línea' : 'líneas'}
						</span>
					</div>

					<!-- Right: Actions -->
					<div class="flex items-center gap-1">
						<!-- Copy -->
						<Tooltip.Root>
							<Tooltip.Trigger asChild>
								{#snippet children({ props })}
									<button
										{...props}
										onclick={handleCopy}
										class="flex h-8 w-8 items-center justify-center rounded-md
										       text-[#8b949e] transition-all duration-200
										       hover:bg-white/8 hover:text-white active:scale-95"
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
										class="flex h-8 w-8 items-center justify-center rounded-md
										       text-[#8b949e] transition-all duration-200
										       hover:bg-white/8 hover:text-white active:scale-95"
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

						<!-- Close -->
						<DialogPrimitive.Close
							class="ml-2 flex h-8 w-8 items-center justify-center rounded-md
							       text-[#8b949e] transition-all duration-200
							       hover:bg-red-500/15 hover:text-red-400 active:scale-95"
							aria-label="Close"
						>
							<XIcon class="h-4 w-4" />
						</DialogPrimitive.Close>
					</div>
				</div>

				<!-- ─── Body ───────────────────────────────────────── -->
				<div class="flex-1 overflow-hidden">
					{#if activeTab === 'source'}
						<!-- Source code view with line numbers -->
						<div class="h-full overflow-auto">
							<div class="flex min-h-full">
								<!-- Line numbers gutter -->
								<div
									class="sticky left-0 z-10 flex-shrink-0 select-none border-r
									       border-white/5 bg-[#0d1117] px-4 py-4
									       text-right font-mono text-[12px] leading-[1.65]
									       text-[#484f58]"
									aria-hidden="true"
								>
									{#each Array(lineCount) as _, i}
										<div>{i + 1}</div>
									{/each}
								</div>

								<!-- Code -->
								<pre
									class="m-0 flex-1 bg-transparent"
								><code
										class="hljs block px-5 py-4 font-mono text-[13px] leading-[1.65]"
									>{@html highlightedHtml}</code></pre>
							</div>
						</div>
					{:else if activeTab === 'preview'}
						<!-- HTML/SVG preview iframe -->
						<iframe
							bind:this={iframeRef}
							title="Preview {language}"
							sandbox="allow-scripts"
							class="h-full w-full border-0 bg-white"
						></iframe>
					{/if}
				</div>
			</div>
		</DialogPrimitive.Content>
	</DialogPrimitive.Portal>
</DialogPrimitive.Root>

<style lang="postcss">
	:global(.dialog-code-overlay) {
		position: fixed;
		inset: 0;
		background-color: rgba(0, 0, 0, 0.75);
		backdrop-filter: blur(4px);
		z-index: 100000;
	}

	:global(.dialog-code-content) {
		position: fixed;
		inset: 0;
		top: 0 !important;
		left: 0 !important;
		width: 100dvw;
		height: 100dvh;
		margin: 0;
		padding: 0;
		border: none;
		border-radius: 0;
		background-color: transparent;
		box-shadow: none;
		display: block;
		overflow: hidden;
		transform: none !important;
		z-index: 100001;
	}
</style>
