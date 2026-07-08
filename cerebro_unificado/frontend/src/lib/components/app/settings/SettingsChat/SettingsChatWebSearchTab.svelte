<script lang="ts">
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { Label } from '$lib/components/ui/label';
	import { Input } from '$lib/components/ui/input';
	import { Textarea } from '$lib/components/ui/textarea';
	import { Switch } from '$lib/components/ui/switch';
	import { getChatSettingsConfigContext } from '$lib/contexts';

	const context = getChatSettingsConfigContext();
	const localConfig = $derived(context.localConfig);
	const handleConfigChange = context.handleConfigChange;

	// Set defaults on mount if undefined
	$effect(() => {
		if (localConfig.webSearchEnabled === undefined) handleConfigChange('webSearchEnabled', false);
		if (localConfig.webSearchProvider === undefined) handleConfigChange('webSearchProvider', 'searxng');
		if (localConfig.browserlessApiKey === undefined) handleConfigChange('browserlessApiKey', '');
		if (localConfig.browserlessSystemPrompt === undefined) handleConfigChange('browserlessSystemPrompt', '');
		if (localConfig.browserlessStealth === undefined) handleConfigChange('browserlessStealth', true);
		if (localConfig.browserlessStealthRoute === undefined) handleConfigChange('browserlessStealthRoute', false);
		if (localConfig.browserlessBlockAds === undefined) handleConfigChange('browserlessBlockAds', false);
		if (localConfig.browserlessHeadless === undefined) handleConfigChange('browserlessHeadless', true);
		if (localConfig.browserlessLocale === undefined) handleConfigChange('browserlessLocale', 'en-US');
		if (localConfig.browserlessTimezone === undefined) handleConfigChange('browserlessTimezone', 'America/Los_Angeles');
		if (localConfig.browserlessUserAgent === undefined) handleConfigChange('browserlessUserAgent', '');
		if (localConfig.browserlessRoute === undefined) handleConfigChange('browserlessRoute', '');
		if (localConfig.googleApiKey === undefined) handleConfigChange('googleApiKey', '');
		if (localConfig.googleEngineId === undefined) handleConfigChange('googleEngineId', '');
		if (localConfig.searxngUrl === undefined) handleConfigChange('searxngUrl', 'http://127.0.0.1:8888');
		if (localConfig.youtubeApiKey === undefined) handleConfigChange('youtubeApiKey', '');
	});
</script>

<div class="space-y-6">
	<!-- Web Search master toggle -->
	<div class="flex items-center justify-between rounded-lg border border-border/40 p-4 bg-muted/20">
		<div class="space-y-0.5">
			<Label class="text-sm font-semibold">Enable Web Search</Label>
			<p class="text-xs text-muted-foreground">Master switch to enable or disable web search functionality.</p>
		</div>
		<Switch
			checked={!!localConfig.webSearchEnabled}
			onCheckedChange={(val) => handleConfigChange('webSearchEnabled', val)}
		/>
	</div>

	{#if localConfig.webSearchEnabled}
		<!-- Provider Selection -->
		<div class="space-y-2">
			<Label class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Search Provider</Label>
			<select
				class="w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
				value={localConfig.webSearchProvider || 'searxng'}
				onchange={(e) => handleConfigChange('webSearchProvider', e.currentTarget.value)}
			>
				<option value="searxng">SearXNG (Local Self-Hosted / Docker)</option>
				<option value="browserless">Browserless.io (Playwright automation)</option>
				<option value="googlepse">Google Programmable Search Engine</option>
			</select>
			<p class="text-xs text-muted-foreground/80">Choose which provider to use when Web Search is enabled.</p>
		</div>

		<!-- SEARXNG Settings -->
		{#if localConfig.webSearchProvider === 'searxng'}
			<div class="space-y-4 rounded-xl border border-border/30 p-5 bg-card/30">
				<h4 class="text-sm font-semibold text-foreground/90 border-b border-border/20 pb-2">SearXNG Settings</h4>
				
				<div class="space-y-2">
					<Label class="text-xs font-medium">SearXNG Server URL</Label>
					<Input
						type="text"
						placeholder="http://127.0.0.1:8888"
						value={localConfig.searxngUrl || 'http://127.0.0.1:8888'}
						oninput={(e) => handleConfigChange('searxngUrl', e.currentTarget.value)}
						class="font-mono text-xs"
					/>
					<p class="text-[11px] text-muted-foreground">
						The URL of your running SearXNG docker container instance.
					</p>
				</div>
			</div>
		{/if}

		<!-- BROWSERLESS Settings -->
		{#if localConfig.webSearchProvider === 'browserless'}
			<div class="space-y-5 rounded-xl border border-border/30 p-5 bg-card/30">
				<h4 class="text-sm font-semibold text-foreground/90 border-b border-border/20 pb-2">Browserless Connection</h4>
				
				<div class="space-y-2">
					<Label class="text-xs font-medium">Browserless API Key / Token</Label>
					<Input
						type="password"
						placeholder="bl_..."
						value={localConfig.browserlessApiKey || ''}
						oninput={(e) => handleConfigChange('browserlessApiKey', e.currentTarget.value)}
						class="font-mono text-xs"
					/>
					<p class="text-[11px] text-muted-foreground">Your api token for production-sfo.browserless.io.</p>
				</div>

				<div class="space-y-2">
					<Label class="text-xs font-medium">Browserless System Prompt</Label>
					<Textarea
						placeholder="Guidance for browsing behavior when tools are enabled..."
						value={localConfig.browserlessSystemPrompt || ''}
						oninput={(e) => handleConfigChange('browserlessSystemPrompt', e.currentTarget.value)}
						rows={3}
						class="text-xs"
					/>
					<p class="text-[11px] text-muted-foreground">Guidance for browsing behavior when web scraping tools are active.</p>
				</div>

				<div class="border-t border-border/20 pt-4">
					<h5 class="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-4">Browserless Advanced Parameters</h5>
					
					<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
						<div class="flex items-center justify-between p-2 rounded-lg border border-border/10 bg-muted/10">
							<div class="space-y-0.5">
								<Label class="text-xs font-medium">Stealth evasions</Label>
								<p class="text-[10px] text-muted-foreground">Apply stealth patches.</p>
							</div>
							<Checkbox
								checked={localConfig.browserlessStealth !== false}
								onCheckedChange={(val) => handleConfigChange('browserlessStealth', !!val)}
							/>
						</div>

						<div class="flex items-center justify-between p-2 rounded-lg border border-border/10 bg-muted/10">
							<div class="space-y-0.5">
								<Label class="text-xs font-medium">Use stealth route</Label>
								<p class="text-[10px] text-muted-foreground">Route through stealth proxy.</p>
							</div>
							<Checkbox
								checked={!!localConfig.browserlessStealthRoute}
								onCheckedChange={(val) => handleConfigChange('browserlessStealthRoute', !!val)}
							/>
						</div>

						<div class="flex items-center justify-between p-2 rounded-lg border border-border/10 bg-muted/10">
							<div class="space-y-0.5">
								<Label class="text-xs font-medium">Block ads/trackers</Label>
								<p class="text-[10px] text-muted-foreground">Block tracking requests.</p>
							</div>
							<Checkbox
								checked={!!localConfig.browserlessBlockAds}
								onCheckedChange={(val) => handleConfigChange('browserlessBlockAds', !!val)}
							/>
						</div>

						<div class="flex items-center justify-between p-2 rounded-lg border border-border/10 bg-muted/10">
							<div class="space-y-0.5">
								<Label class="text-xs font-medium">Headless mode</Label>
								<p class="text-[10px] text-muted-foreground">Run browser without GUI.</p>
							</div>
							<Checkbox
								checked={localConfig.browserlessHeadless !== false}
								onCheckedChange={(val) => handleConfigChange('browserlessHeadless', !!val)}
							/>
						</div>
					</div>

					<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
						<div class="space-y-1.5">
							<Label class="text-xs font-medium">Locale</Label>
							<Input
								type="text"
								value={localConfig.browserlessLocale || 'en-US'}
								oninput={(e) => handleConfigChange('browserlessLocale', e.currentTarget.value)}
								class="text-xs"
							/>
						</div>

						<div class="space-y-1.5">
							<Label class="text-xs font-medium">Timezone</Label>
							<Input
								type="text"
								value={localConfig.browserlessTimezone || 'America/Los_Angeles'}
								oninput={(e) => handleConfigChange('browserlessTimezone', e.currentTarget.value)}
								class="text-xs"
							/>
						</div>
					</div>

					<div class="space-y-1.5 mt-4">
						<Label class="text-xs font-medium">User Agent override (optional)</Label>
						<Input
							type="text"
							placeholder="Custom UA string"
							value={localConfig.browserlessUserAgent || ''}
							oninput={(e) => handleConfigChange('browserlessUserAgent', e.currentTarget.value)}
							class="text-xs font-mono"
						/>
					</div>

					<div class="space-y-1.5 mt-4">
						<Label class="text-xs font-medium">Route override (optional)</Label>
						<Input
							type="text"
							placeholder="chromium or chromium/stealth"
							value={localConfig.browserlessRoute || ''}
							oninput={(e) => handleConfigChange('browserlessRoute', e.currentTarget.value)}
							class="text-xs font-mono"
						/>
					</div>
				</div>
			</div>
		{/if}

		<!-- GOOGLE PSE Settings -->
		{#if localConfig.webSearchProvider === 'googlepse'}
			<div class="space-y-4 rounded-xl border border-border/30 p-5 bg-card/30">
				<h4 class="text-sm font-semibold text-foreground/90 border-b border-border/20 pb-2">Google PSE Connection</h4>
				
				<div class="space-y-2">
					<Label class="text-xs font-medium">Google API Key</Label>
					<Input
						type="password"
						placeholder="AIzaSy..."
						value={localConfig.googleApiKey || ''}
						oninput={(e) => handleConfigChange('googleApiKey', e.currentTarget.value)}
						class="font-mono text-xs"
					/>
				</div>

				<div class="space-y-2">
					<Label class="text-xs font-medium">Google Search Engine ID (cx)</Label>
					<Input
						type="text"
						placeholder="0123456789..."
						value={localConfig.googleEngineId || ''}
						oninput={(e) => handleConfigChange('googleEngineId', e.currentTarget.value)}
						class="font-mono text-xs"
					/>
				</div>
			</div>
		{/if}
	{/if}

	<!-- YOUTUBE Search Settings -->
	<div class="space-y-4 rounded-xl border border-border/30 p-5 bg-card/30 mt-4">
		<h4 class="text-sm font-semibold text-foreground/90 border-b border-border/20 pb-2">YouTube Search Settings</h4>
		
		<div class="space-y-2">
			<Label class="text-xs font-medium">YouTube API Key</Label>
			<Input
				type="password"
				placeholder="AIzaSy..."
				value={localConfig.youtubeApiKey || ''}
				oninput={(e) => handleConfigChange('youtubeApiKey', e.currentTarget.value)}
				class="font-mono text-xs"
			/>
			<p class="text-[11px] text-muted-foreground">
				Your API Key for YouTube Data API v3 (used for precise music/video searches).
			</p>
		</div>
	</div>
</div>
