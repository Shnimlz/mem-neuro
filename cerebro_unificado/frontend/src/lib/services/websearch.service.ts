import { WEB_SEARCH_TOOL_NAME } from '$lib/constants';
import type { ToolExecutionResult } from '$lib/types';
import { config } from '$lib/stores/settings.svelte';

export class WebSearchService {
	static async executeTool(
		toolName: string,
		params: Record<string, unknown>,
		signal?: AbortSignal
	): Promise<ToolExecutionResult> {
		if (toolName !== WEB_SEARCH_TOOL_NAME) {
			return { content: `Unknown web search tool: ${toolName}`, isError: true };
		}

		const query = params.query;
		if (!query || typeof query !== 'string') {
			return { content: 'Missing or invalid "query" parameter', isError: true };
		}

		const enabled = config().webSearchEnabled;
		if (!enabled) {
			return { content: 'Web search is currently disabled in Settings.', isError: true };
		}

		const provider = config().webSearchProvider || 'searxng';

		try {
			if (provider === 'searxng') {
				const serverUrl = config().searxngUrl || 'http://127.0.0.1:8888';
				const searchUrl = `${serverUrl}/search?q=${encodeURIComponent(query)}&format=json`;

				const res = await fetch(searchUrl, { signal });
				if (!res.ok) {
					return { content: `SearXNG request failed (${res.status})`, isError: true };
				}

				const data = await res.json();
				const results = data.results || [];
				if (results.length === 0) {
					return { content: `No results found for query: "${query}"`, isError: false };
				}

				const lines = results.slice(0, 4).map((r: any, idx: number) => {
					return `[${idx + 1}] Title: ${r.title}\n    URL: ${r.url}\n    Summary: ${r.content || r.snippet || '[No description]'}`;
				});

				return { content: lines.join('\n\n'), isError: false };
			}

			if (provider === 'googlepse') {
				const apiKey = config().googleApiKey;
				const cx = config().googleEngineId;
				if (!apiKey || !cx) {
					return { content: 'Google PSE is not configured in Settings.', isError: true };
				}

				const searchUrl = `https://www.googleapis.com/customsearch/v1?q=${encodeURIComponent(query)}&cx=${cx}&key=${apiKey}`;

				const res = await fetch(searchUrl, { signal });
				if (!res.ok) {
					return { content: `Google PSE request failed (${res.status})`, isError: true };
				}

				const data = await res.json();
				const items = data.items || [];
				if (items.length === 0) {
					return { content: `No results found for query: "${query}"`, isError: false };
				}

				const lines = items.slice(0, 4).map((item: any, idx: number) => {
					return `[${idx + 1}] Title: ${item.title}\n    URL: ${item.link}\n    Summary: ${item.snippet || '[No description]'}`;
				});

				return { content: lines.join('\n\n'), isError: false };
			}

			if (provider === 'browserless') {
				const apiKey = config().browserlessApiKey;
				if (!apiKey) {
					return { content: 'Browserless API token is missing in Settings.', isError: true };
				}

				// Simple search using browserless's scrape api
				const scrapeUrl = `https://chrome.browserless.io/scrape?token=${apiKey}`;
				const res = await fetch(scrapeUrl, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						url: `https://html.duckduckgo.com/html/?q=${encodeURIComponent(query)}`,
						elements: [{ selector: '.result' }]
					}),
					signal
				});

				if (!res.ok) {
					return { content: `Browserless scraping failed (${res.status})`, isError: true };
				}

				const data = await res.json();
				const results = data.data?.[0]?.results || [];
				if (results.length === 0) {
					return { content: `No results scraped for query: "${query}"`, isError: false };
				}

				const lines = results.slice(0, 3).map((item: any, idx: number) => {
					return `[${idx + 1}] Snippet: ${item.text || '[No text]'}`;
				});

				return { content: lines.join('\n\n'), isError: false };
			}

			return { content: `Unknown web search provider: ${provider}`, isError: true };
		} catch (error) {
			if (error instanceof DOMException && error.name === 'AbortError') {
				throw error;
			}
			return {
				content: `Web search error: ${error instanceof Error ? error.message : String(error)}`,
				isError: true
			};
		}
	}
}
