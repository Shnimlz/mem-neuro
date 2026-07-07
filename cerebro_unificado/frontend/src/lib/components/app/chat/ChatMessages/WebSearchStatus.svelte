<script lang="ts">
	interface SearchResult {
		title: string;
		url: string;
		icon?: string;
		content?: string;
	}

	interface Props {
		query: string;
		results: SearchResult[];
	}

	let { query, results }: Props = $props();
	let isOpen = $state(false);

	function getDomain(urlStr: string): string {
		try {
			const url = new URL(urlStr);
			return url.hostname.replace('www.', '');
		} catch {
			return 'web';
		}
	}

	function getFavicon(urlStr: string): string {
		try {
			const url = new URL(urlStr);
			return `https://www.google.com/s2/favicons?sz=32&domain=${url.hostname}`;
		} catch {
			return '';
		}
	}
</script>

<div class="web-search-status">
	<button class="ws-header" onclick={() => (isOpen = !isOpen)}>
		<div class="ws-header-left">
			<svg
				width="16"
				height="16"
				viewBox="0 0 24 24"
				fill="none"
				stroke="#58a6ff"
				stroke-width="2"
				stroke-linecap="round"
				stroke-linejoin="round"
			>
				<circle cx="12" cy="12" r="10"></circle>
				<line x1="2" y1="12" x2="22" y2="12"></line>
				<path
					d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"
				></path>
			</svg>
			<span class="ws-query-text">
				Buscando en la web: <em class="ws-query-value">"{query}"</em>
			</span>
		</div>
		<div class="ws-header-right">
			<span class="ws-count">{results.length} {results.length === 1 ? 'fuente' : 'fuentes'}</span>
			<span class="ws-chevron" class:ws-chevron-open={isOpen}>▶</span>
		</div>
	</button>

	{#if isOpen}
		<div class="ws-results">
			{#each results as result, idx}
				<a
					href={result.url}
					target="_blank"
					rel="noopener noreferrer"
					class="ws-result-item"
				>
					<div class="ws-result-left">
						{#if result.icon || getFavicon(result.url)}
							<img
								src={result.icon || getFavicon(result.url)}
								alt=""
								class="ws-favicon"
								onerror={(e) => {
									const target = e.currentTarget as HTMLImageElement;
									target.style.display = 'none';
									const fallback = target.nextElementSibling as HTMLElement;
									if (fallback) fallback.style.display = 'flex';
								}}
							/>
						{/if}
						<div class="ws-favicon-fallback" style="display: {result.icon || getFavicon(result.url) ? 'none' : 'flex'}">
							{getDomain(result.url)[0].toUpperCase()}
						</div>
						<span class="ws-result-title">{result.title}</span>
					</div>
					<span class="ws-result-domain">{getDomain(result.url)}</span>
				</a>
			{/each}
		</div>
	{/if}
</div>

<style>
	.web-search-status {
		background-color: rgba(37, 35, 32, 0.4);
		border: 1px solid rgba(88, 166, 255, 0.15);
		border-radius: 8px;
		padding: 12px;
		margin-bottom: 16px;
		color: #dcd6cc;
		font-family: system-ui, -apple-system, sans-serif;
	}

	.ws-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		cursor: pointer;
		user-select: none;
		width: 100%;
		background: none;
		border: none;
		color: inherit;
		padding: 0;
		font: inherit;
		text-align: left;
	}

	.ws-header-left {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
	}

	.ws-header-left svg {
		flex-shrink: 0;
	}

	.ws-query-text {
		font-size: 13px;
		font-weight: 500;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.ws-query-value {
		color: #58a6ff;
		font-style: italic;
	}

	.ws-header-right {
		display: flex;
		align-items: center;
		gap: 8px;
		flex-shrink: 0;
	}

	.ws-count {
		font-size: 11px;
		color: #7a7266;
	}

	.ws-chevron {
		font-size: 10px;
		color: #7a7266;
		transition: transform 0.15s ease;
		display: inline-block;
	}

	.ws-chevron-open {
		transform: rotate(90deg);
	}

	.ws-results {
		margin-top: 12px;
		border-top: 1px solid rgba(87, 83, 78, 0.15);
		padding-top: 8px;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.ws-result-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 8px 10px;
		border-radius: 6px;
		background-color: rgba(19, 18, 16, 0.3);
		border: 1px solid rgba(87, 83, 78, 0.1);
		text-decoration: none;
		color: inherit;
		transition: all 0.15s ease;
	}

	.ws-result-item:hover {
		background-color: rgba(19, 18, 16, 0.6);
		border-color: rgba(88, 166, 255, 0.3);
	}

	.ws-result-left {
		display: flex;
		align-items: center;
		gap: 8px;
		min-width: 0;
		flex: 1;
	}

	.ws-favicon {
		width: 16px;
		height: 16px;
		border-radius: 2px;
		flex-shrink: 0;
	}

	.ws-favicon-fallback {
		width: 16px;
		height: 16px;
		border-radius: 2px;
		background-color: rgba(88, 166, 255, 0.15);
		color: #58a6ff;
		font-size: 10px;
		font-weight: bold;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}

	.ws-result-title {
		font-size: 12px;
		font-weight: 500;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		color: #e8e2d8;
	}

	.ws-result-domain {
		font-size: 11px;
		color: #8e8c89;
		margin-left: 12px;
		flex-shrink: 0;
	}
</style>
