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

		// ─── Interceptar consultas de Clima (Nominatim + Open-Meteo) ───
		const isWeatherQuery = /clima|tiempo|pronostico|weather|temperatura/i.test(query);
		if (isWeatherQuery) {
			try {
				// Extraer la ciudad de la consulta (o usar "Reynosa, Tamaulipas" por defecto)
				const match = query.match(/(?:clima|tiempo|pronostico|temperatura)\s+(?:en|de|para|de\s+estos\s+dias\s+en)?\s*([^?.,\n]+)/i);
				const city = match ? match[1].trim() : 'Reynosa, Tamaulipas';

				// 1. Geocodificación
				const geoUrl = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(city)}&format=json&limit=1`;
				const geoRes = await fetch(geoUrl, {
					headers: { 'User-Agent': 'CerebroAutonomo/1.0' },
					signal
				});

				if (geoRes.ok) {
					const geoData = await geoRes.json();
					if (geoData.length > 0) {
						const { lat, lon, display_name } = geoData[0];

						// 2. Consultar clima en Open-Meteo
						const weatherUrl = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=auto`;
						const weatherRes = await fetch(weatherUrl, { signal });

						if (weatherRes.ok) {
							const weatherData = await weatherRes.json();
							
							// Estructura consolidada
							const weatherPayload = {
								location: display_name.split(',')[0] + ', ' + display_name.split(',').slice(-1)[0].trim(),
								current: weatherData.current_weather,
								daily: weatherData.daily
							};

							// Formato resumen en texto para la lectura del LLM
							const summaryText = `Resultados del clima en ${weatherPayload.location}: Temperatura actual de ${weatherPayload.current.temperature}°C, estado del tiempo: código WMO ${weatherPayload.current.weathercode}. Máxima prevista hoy: ${weatherData.daily.temperature_2m_max[0]}°C, Mínima: ${weatherData.daily.temperature_2m_min[0]}°C, Probabilidad de lluvia: ${weatherData.daily.precipitation_probability_max[0]}%.`;

							return {
								content: `<weather_data>${JSON.stringify(weatherPayload)}</weather_data>\n\n${summaryText}`,
								isError: false
							};
						}
					}
				}
			} catch (weatherErr) {
				console.warn('Weather API query failed, falling back to default web search:', weatherErr);
			}
		}

		try {
			const youtubeApiKey = config().youtubeApiKey;
			const isYoutubeQuery = /youtube|video|musica|music|song|cancion|reproducir|videoclip/i.test(query);

			if (youtubeApiKey && isYoutubeQuery) {
				try {
					const ytUrl = `https://www.googleapis.com/youtube/v3/search?part=snippet&q=${encodeURIComponent(query)}&type=video&maxResults=4&key=${youtubeApiKey}`;
					const res = await fetch(ytUrl, { signal });
					if (res.ok) {
						const data = await res.json();
						const items = data.items || [];
						if (items.length > 0) {
							const lines = items.map((item: any, idx: number) => {
								const videoId = item.id?.videoId;
								const videoUrl = videoId ? `https://www.youtube.com/watch?v=${videoId}` : '';
								return `[${idx + 1}] Title: ${item.snippet?.title || 'Video'}\n    URL: ${videoUrl}\n    Summary: ${item.snippet?.description || '[No description]'}`;
							});
							return { content: lines.join('\n\n'), isError: false };
						}
					}
				} catch (ytError) {
					console.warn('YouTube API query failed, falling back to default web search:', ytError);
				}
			}

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
				const route = config().browserlessRoute;
				const apiKey = config().browserlessApiKey;

				let scrapeUrl = '';
				if (route && (route.startsWith('http://') || route.startsWith('https://'))) {
					const baseRoute = route.endsWith('/') ? route.slice(0, -1) : route;
					scrapeUrl = baseRoute.includes('/scrape') ? baseRoute : `${baseRoute}/scrape`;
					if (apiKey) {
						scrapeUrl += `?token=${apiKey}`;
					}
				} else {
					const tokenParam = apiKey ? `?token=${apiKey}` : '';
					const path = route ? (route.startsWith('/') ? route : `/${route}`) : '/scrape';
					scrapeUrl = `https://chrome.browserless.io${path}${tokenParam}`;
				}

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
