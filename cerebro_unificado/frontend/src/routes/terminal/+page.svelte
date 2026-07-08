<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';

	// ─── Estado reactivo ───
	let lines: Array<{ type: 'prompt' | 'output' | 'error' | 'system'; text: string }> = $state([]);
	let inputValue = $state('');
	let isRunning = $state(false);
	let ws: WebSocket | null = $state(null);
	let connected = $state(false);
	let commandHistory: string[] = $state([]);
	let historyIndex = $state(-1);
	let scrollContainer: HTMLDivElement | undefined = $state();
	let inputRef: HTMLInputElement | undefined = $state();

	function scrollToBottom() {
		if (scrollContainer) {
			requestAnimationFrame(() => {
				scrollContainer!.scrollTop = scrollContainer!.scrollHeight;
			});
		}
	}

	function addLine(type: 'prompt' | 'output' | 'error' | 'system', text: string) {
		lines = [...lines, { type, text }];
		scrollToBottom();
	}

	function connectWS() {
		if (!browser) return;
		const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
		const wsUrl = `${protocol}//${window.location.host}/ws/terminal`;

		ws = new WebSocket(wsUrl);

		ws.onopen = () => {
			connected = true;
		};

		ws.onmessage = (event) => {
			try {
				const data = JSON.parse(event.data);

				if (data.event === 'connected') {
					addLine('system', `✓ ${data.message}`);
				} else if (data.event === 'running') {
					// Indicador visual mientras ejecuta
				} else if (data.event === 'output') {
					isRunning = false;
					addLine('output', data.output);
				} else if (data.event === 'error') {
					isRunning = false;
					addLine('error', data.message || 'Error desconocido');
				}
			} catch {
				addLine('error', 'Error parseando respuesta del servidor');
				isRunning = false;
			}
		};

		ws.onclose = () => {
			connected = false;
			addLine('system', '✗ Conexión cerrada. Reconectando en 3s...');
			setTimeout(connectWS, 3000);
		};

		ws.onerror = () => {
			connected = false;
		};
	}

	function sendCommand() {
		const cmd = inputValue.trim();
		if (!cmd || !ws || ws.readyState !== WebSocket.OPEN || isRunning) return;

		// Comando local: clear
		if (cmd === 'clear') {
			lines = [];
			inputValue = '';
			return;
		}

		addLine('prompt', `$ ${cmd}`);
		commandHistory = [...commandHistory, cmd];
		historyIndex = -1;
		isRunning = true;
		inputValue = '';

		ws.send(JSON.stringify({ command: cmd }));
	}

	function handleKeyDown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			sendCommand();
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			if (commandHistory.length === 0) return;
			if (historyIndex === -1) {
				historyIndex = commandHistory.length - 1;
			} else if (historyIndex > 0) {
				historyIndex--;
			}
			inputValue = commandHistory[historyIndex];
		} else if (e.key === 'ArrowDown') {
			e.preventDefault();
			if (historyIndex === -1) return;
			if (historyIndex < commandHistory.length - 1) {
				historyIndex++;
				inputValue = commandHistory[historyIndex];
			} else {
				historyIndex = -1;
				inputValue = '';
			}
		} else if (e.key === 'l' && e.ctrlKey) {
			e.preventDefault();
			lines = [];
		}
	}

	// Click en cualquier parte del terminal enfoca el input
	function handleContainerClick() {
		inputRef?.focus();
	}

	onMount(() => {
		connectWS();
		addLine('system', '🧠 Cerebro Autónomo — Terminal Interactiva');
		addLine('system', 'Escribe comandos bash. Usa "search <query>" para buscar en la web.');
		addLine('system', 'Ctrl+L o "clear" para limpiar. ↑/↓ para historial.');
		addLine('system', '─'.repeat(60));
	});

	onDestroy(() => {
		if (ws) {
			ws.onclose = null; // Evitar reconexión automática
			ws.close();
		}
	});
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="terminal-container" onclick={handleContainerClick}>
	<!-- Header -->
	<div class="terminal-header">
		<div class="terminal-dots">
			<span class="dot dot-red"></span>
			<span class="dot dot-yellow"></span>
			<span class="dot dot-green"></span>
		</div>
		<span class="terminal-title">terminal@cerebro:~</span>
		<div class="terminal-status">
			<span
				class="status-dot"
				class:status-connected={connected}
				class:status-disconnected={!connected}
			></span>
			<span class="status-text">{connected ? 'Conectado' : 'Desconectado'}</span>
		</div>
	</div>

	<!-- Output area -->
	<div class="terminal-output" bind:this={scrollContainer}>
		{#each lines as line}
			<div class="terminal-line {line.type}">
				{#if line.type === 'prompt'}
					<span class="prompt-prefix">terminal@cerebro:~</span><span class="prompt-dollar">$</span>
					<span class="prompt-cmd">{line.text.replace(/^\$ /, '')}</span>
				{:else if line.type === 'output'}
					<pre class="output-text">{line.text}</pre>
				{:else if line.type === 'error'}
					<pre class="error-text">{line.text}</pre>
				{:else if line.type === 'system'}
					<span class="system-text">{line.text}</span>
				{/if}
			</div>
		{/each}

		{#if isRunning}
			<div class="terminal-line system">
				<span class="running-indicator">⏳ ejecutando<span class="dots-anim">...</span></span>
			</div>
		{/if}
	</div>

	<!-- Input -->
	<div class="terminal-input-row">
		<span class="prompt-prefix">terminal@cerebro:~</span><span class="prompt-dollar">$</span>
		<input
			bind:this={inputRef}
			bind:value={inputValue}
			onkeydown={handleKeyDown}
			disabled={!connected || isRunning}
			placeholder={isRunning ? 'ejecutando...' : 'escribe un comando...'}
			class="terminal-input"
			autofocus
			spellcheck="false"
			autocomplete="off"
		/>
	</div>
</div>

<style>
	.terminal-container {
		display: flex;
		flex-direction: column;
		height: 100dvh;
		background-color: #0c0a09;
		font-family:
			'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'SF Mono', 'Menlo', 'Consolas', monospace;
		font-size: 13px;
		color: #e0e0e0;
		cursor: text;
		overflow: hidden;
	}

	.terminal-header {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 10px 16px;
		background: #1a1714;
		border-bottom: 1px solid #2a2520;
		flex-shrink: 0;
		user-select: none;
	}

	.terminal-dots {
		display: flex;
		gap: 6px;
	}

	.dot {
		width: 12px;
		height: 12px;
		border-radius: 50%;
	}
	.dot-red {
		background: #ff5f57;
	}
	.dot-yellow {
		background: #febc2e;
	}
	.dot-green {
		background: #28c840;
	}

	.terminal-title {
		flex: 1;
		text-align: center;
		color: #8a8580;
		font-size: 12px;
		font-weight: 500;
	}

	.terminal-status {
		display: flex;
		align-items: center;
		gap: 6px;
	}

	.status-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		transition: background 0.3s;
	}
	.status-connected {
		background: #28c840;
		box-shadow: 0 0 6px #28c84080;
	}
	.status-disconnected {
		background: #ff5f57;
		box-shadow: 0 0 6px #ff5f5780;
	}

	.status-text {
		font-size: 11px;
		color: #8a8580;
	}

	.terminal-output {
		flex: 1;
		overflow-y: auto;
		padding: 12px 16px;
		scroll-behavior: smooth;
	}

	.terminal-output::-webkit-scrollbar {
		width: 6px;
	}
	.terminal-output::-webkit-scrollbar-track {
		background: transparent;
	}
	.terminal-output::-webkit-scrollbar-thumb {
		background: #3a3530;
		border-radius: 3px;
	}

	.terminal-line {
		margin-bottom: 2px;
		line-height: 1.5;
		word-break: break-word;
	}

	.prompt-prefix {
		color: #4ade80;
		font-weight: 600;
	}

	.prompt-dollar {
		color: #facc15;
		font-weight: 700;
		margin: 0 4px 0 2px;
	}

	.prompt-cmd {
		color: #f0f0f0;
	}

	.output-text {
		color: #d4d4d4;
		margin: 0;
		padding: 0;
		white-space: pre-wrap;
		word-break: break-word;
		font-family: inherit;
		font-size: inherit;
		line-height: 1.45;
	}

	.error-text {
		color: #f87171;
		margin: 0;
		padding: 0;
		white-space: pre-wrap;
		word-break: break-word;
		font-family: inherit;
		font-size: inherit;
		line-height: 1.45;
	}

	.system-text {
		color: #60a5fa;
		font-style: italic;
	}

	.running-indicator {
		color: #facc15;
	}

	.dots-anim {
		animation: blink 1.2s infinite steps(3, start);
	}

	@keyframes blink {
		0% {
			opacity: 0;
		}
		50% {
			opacity: 1;
		}
		100% {
			opacity: 0;
		}
	}

	.terminal-input-row {
		display: flex;
		align-items: center;
		padding: 8px 16px 12px;
		background: #1a1714;
		border-top: 1px solid #2a2520;
		flex-shrink: 0;
	}

	.terminal-input {
		flex: 1;
		background: transparent;
		border: none;
		outline: none;
		color: #f0f0f0;
		font-family: inherit;
		font-size: inherit;
		caret-color: #4ade80;
		padding: 0;
	}

	.terminal-input::placeholder {
		color: #555;
		font-style: italic;
	}

	.terminal-input:disabled {
		opacity: 0.5;
	}
</style>
