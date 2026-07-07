<script lang="ts">
	import hljs from 'highlight.js';
	import { browser } from '$app/environment';
	import { mode } from 'mode-watcher';

	import githubDarkCss from 'highlight.js/styles/github-dark.css?inline';
	import githubLightCss from 'highlight.js/styles/github.css?inline';
	import { ColorMode } from '$lib/enums';
	import { copyToClipboard } from '$lib/utils';

	import Copy from '@lucide/svelte/icons/copy';
	import Check from '@lucide/svelte/icons/check';
	import Download from '@lucide/svelte/icons/download';
	import Maximize2 from '@lucide/svelte/icons/maximize-2';
	import * as Tooltip from '$lib/components/ui/tooltip';

	// ─── Types ───────────────────────────────────────────────────────────

	interface Props {
		code: string;
		language?: string;
		class?: string;
		maxHeight?: string;
		maxWidth?: string;
		/** Callback to open the fullscreen preview dialog */
		onMaximize?: (code: string, language: string) => void;
	}

	let {
		code,
		language = 'text',
		class: className = '',
		maxHeight = '60vh',
		maxWidth = '',
		onMaximize
	}: Props = $props();

	// ─── Highlighting ────────────────────────────────────────────────────

	let highlightedHtml = $state('');

	function loadHighlightTheme(isDark: boolean) {
		if (!browser) return;

		const existingThemes = document.querySelectorAll('style[data-highlight-theme-preview]');
		existingThemes.forEach((style) => style.remove());

		const style = document.createElement('style');
		style.setAttribute('data-highlight-theme-preview', 'true');
		style.textContent = isDark ? githubDarkCss : githubLightCss;

		document.head.appendChild(style);
	}

	$effect(() => {
		const currentMode = mode.current;
		const isDark = currentMode === ColorMode.DARK;

		loadHighlightTheme(isDark);
	});

	$effect(() => {
		if (!code) {
			highlightedHtml = '';
			return;
		}

		try {
			const lang = language.toLowerCase();
			const isSupported = hljs.getLanguage(lang);

			if (isSupported) {
				const result = hljs.highlight(code, { language: lang });
				highlightedHtml = result.value;
			} else {
				const result = hljs.highlightAuto(code);
				highlightedHtml = result.value;
			}
		} catch {
			highlightedHtml = code.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
		}
	});

	// ─── Line numbers ────────────────────────────────────────────────────

	const lineCount = $derived(code ? code.split('\n').length : 0);

	// ─── Copy feedback ───────────────────────────────────────────────────

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

	const LANG_EXTENSION_MAP: Record<string, string> = {
		javascript: 'js',
		typescript: 'ts',
		python: 'py',
		ruby: 'rb',
		shell: 'sh',
		bash: 'sh',
		zsh: 'sh',
		csharp: 'cs',
		cpp: 'cpp',
		c: 'c',
		java: 'java',
		go: 'go',
		rust: 'rs',
		swift: 'swift',
		kotlin: 'kt',
		scala: 'scala',
		php: 'php',
		html: 'html',
		css: 'css',
		scss: 'scss',
		less: 'less',
		json: 'json',
		yaml: 'yaml',
		yml: 'yml',
		xml: 'xml',
		sql: 'sql',
		markdown: 'md',
		svelte: 'svelte',
		vue: 'vue',
		jsx: 'jsx',
		tsx: 'tsx',
		dart: 'dart',
		r: 'r',
		lua: 'lua',
		perl: 'pl',
		haskell: 'hs',
		toml: 'toml',
		ini: 'ini',
		dockerfile: 'Dockerfile',
		makefile: 'Makefile',
		text: 'txt',
		plaintext: 'txt'
	};

	function getFileExtension(): string {
		const lang = language.toLowerCase();
		return LANG_EXTENSION_MAP[lang] || lang || 'txt';
	}

	function handleDownload() {
		const ext = getFileExtension();
		const filename = `code.${ext}`;
		const blob = new Blob([code], { type: 'text/plain;charset=utf-8' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = filename;
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(url);
	}

	// ─── Display language label ──────────────────────────────────────────

	const displayLanguage = $derived(
		language ? language.charAt(0).toUpperCase() + language.slice(1).toLowerCase() : 'Text'
	);
</script>

<!-- ─── Template ────────────────────────────────────────────────────── -->

<div
	class="code-block-enhanced group relative rounded-xl border border-border/50
	       bg-muted/30 backdrop-blur-sm overflow-hidden {className}"
	style="max-height: {maxHeight}; max-width: {maxWidth};"
>
	<!-- ─── Toolbar Header ─────────────────────────────────────────── -->
	<div
		class="flex items-center justify-between border-b border-border/30
		       bg-muted/40 px-3 py-1.5"
	>
		<!-- Language badge -->
		<span
			class="select-none rounded-md bg-primary/8 px-2 py-0.5 text-[10px]
			       font-semibold uppercase tracking-wider text-muted-foreground/70"
		>
			{displayLanguage}
		</span>

		<!-- Action buttons — always visible on mobile, opacity transition on desktop -->
		<div
			class="flex items-center gap-0.5
			       sm:opacity-0 sm:group-hover:opacity-100
			       transition-opacity duration-200"
		>
			<!-- Copy -->
			<Tooltip.Root>
				<Tooltip.Trigger asChild>
					{#snippet children({ props })}
						<button
							{...props}
							onclick={handleCopy}
							class="flex h-7 w-7 items-center justify-center rounded-md
							       text-muted-foreground transition-all duration-200
							       hover:bg-muted/80 hover:text-foreground
							       active:scale-95"
							aria-label={copied ? 'Copied' : 'Copy code'}
						>
							{#if copied}
								<Check class="h-3.5 w-3.5 text-green-500" />
							{:else}
								<Copy class="h-3.5 w-3.5" />
							{/if}
						</button>
					{/snippet}
				</Tooltip.Trigger>
				<Tooltip.Content side="top">
					<p>{copied ? 'Copiado' : 'Copiar código'}</p>
				</Tooltip.Content>
			</Tooltip.Root>

			<!-- Download -->
			<Tooltip.Root>
				<Tooltip.Trigger asChild>
					{#snippet children({ props })}
						<button
							{...props}
							onclick={handleDownload}
							class="flex h-7 w-7 items-center justify-center rounded-md
							       text-muted-foreground transition-all duration-200
							       hover:bg-muted/80 hover:text-foreground
							       active:scale-95"
							aria-label="Download as file"
						>
							<Download class="h-3.5 w-3.5" />
						</button>
					{/snippet}
				</Tooltip.Trigger>
				<Tooltip.Content side="top">
					<p>Descargar como .{getFileExtension()}</p>
				</Tooltip.Content>
			</Tooltip.Root>

			<!-- Maximize -->
			{#if onMaximize}
				<Tooltip.Root>
					<Tooltip.Trigger asChild>
						{#snippet children({ props })}
							<button
								{...props}
								onclick={() => onMaximize!(code, language)}
								class="flex h-7 w-7 items-center justify-center rounded-md
								       text-muted-foreground transition-all duration-200
								       hover:bg-muted/80 hover:text-foreground
								       active:scale-95"
								aria-label="Maximize"
							>
								<Maximize2 class="h-3.5 w-3.5" />
							</button>
						{/snippet}
					</Tooltip.Trigger>
					<Tooltip.Content side="top">
						<p>Abrir en pantalla completa</p>
					</Tooltip.Content>
				</Tooltip.Root>
			{/if}
		</div>
	</div>

	<!-- ─── Code area with line numbers ────────────────────────────── -->
	<div class="overflow-auto" style="max-height: calc({maxHeight} - 2rem);">
		<div class="flex">
			<!-- Line numbers gutter -->
			{#if lineCount > 1}
				<div
					class="sticky left-0 flex-shrink-0 select-none border-r border-border/20
					       bg-muted/20 px-3 py-3 text-right font-mono text-[11px]
					       leading-relaxed text-muted-foreground/30"
					aria-hidden="true"
				>
					{#each Array(lineCount) as _, i}
						<div>{i + 1}</div>
					{/each}
				</div>
			{/if}

			<!-- Code content -->
			<pre class="m-0 flex-1 bg-transparent"><code class="hljs block px-4 py-3 text-sm leading-relaxed">{@html highlightedHtml}</code></pre>
		</div>
	</div>
</div>

<style>
	.code-block-enhanced pre {
		background: transparent;
	}

	.code-block-enhanced code {
		background: transparent;
	}
</style>
