<script lang="ts">
	import { onMount } from 'svelte';
	import { animate, stagger } from 'animejs';
	import { 
		Sun, CloudSun, Cloud, CloudFog, CloudRain, 
		CloudSnow, CloudDrizzle, CloudLightning, Droplets, Calendar, Clock
	} from '@lucide/svelte';
	import { cn } from '$lib/components/ui/utils.js';

	interface WeatherData {
		location: string;
		current: {
			temperature: number;
			weathercode: number;
			windspeed: number;
		};
		daily: {
			time: string[];
			weathercode: number[];
			temperature_2m_max: number[];
			temperature_2m_min: number[];
			precipitation_probability_max: number[];
		};
	}

	interface Props {
		data: WeatherData;
	}

	let { data }: Props = $props();

	// View mode: 'today' | '3days' | 'week'
	let activeTab = $state<'today' | '3days' | 'week'>('today');
	let containerElement = $state<HTMLDivElement | null>(null);

	function getWeatherIcon(code: number) {
		if (code === 0) return Sun;
		if (code >= 1 && code <= 3) return CloudSun;
		if (code === 45 || code === 48) return CloudFog;
		if (code >= 51 && code <= 55) return CloudDrizzle;
		if (code >= 61 && code <= 65) return CloudRain;
		if (code >= 71 && code <= 77) return CloudSnow;
		if (code >= 80 && code <= 82) return CloudRain;
		if (code >= 95 && code <= 99) return CloudLightning;
		return Cloud;
	}

	function getWeatherDescription(code: number) {
		if (code === 0) return 'Soleado y despejado';
		if (code === 1) return 'Mayormente despejado';
		if (code === 2) return 'Parcialmente nublado';
		if (code === 3) return 'Nublado';
		if (code === 45 || code === 48) return 'Niebla';
		if (code >= 51 && code <= 55) return 'Llovizna ligera';
		if (code >= 61 && code <= 65) return 'Lluvia constante';
		if (code >= 71 && code <= 77) return 'Nevada';
		if (code >= 80 && code <= 82) return 'Chubascos dispersos';
		if (code >= 95 && code <= 99) return 'Tormenta eléctrica';
		return 'Nublado';
	}

	function getDayName(dateStr: string) {
		const date = new Date(dateStr + 'T00:00:00');
		return date.toLocaleDateString('es-ES', { weekday: 'long' });
	}

	// Filter daily data based on active tab
	let displayDays = $derived.by(() => {
		const days = [];
		const maxDays = activeTab === 'today' ? 1 : activeTab === '3days' ? 3 : 7;
		for (let i = 0; i < Math.min(data.daily.time.length, maxDays); i++) {
			days.push({
				time: data.daily.time[i],
				code: data.daily.weathercode[i],
				tempMax: Math.round(data.daily.temperature_2m_max[i]),
				tempMin: Math.round(data.daily.temperature_2m_min[i]),
				rainProb: data.daily.precipitation_probability_max[i]
			});
		}
		return days;
	});

	// Trigger animation on tab changes
	$effect(() => {
		if (containerElement && displayDays.length > 0) {
			// Trigger smooth stagger entry animation for forecast items
			requestAnimationFrame(() => {
				const items = containerElement?.querySelectorAll('.forecast-item');
				if (items && items.length > 0) {
					animate(items, {
						opacity: [0, 1],
						scale: [0.93, 1],
						translateY: [10, 0],
						easing: 'easeOutQuad',
						duration: 400,
						delay: stagger(40)
					});
				}
			});
		}
	});

	onMount(() => {
		if (containerElement) {
			// Initial fade-in of widget
			animate(containerElement, {
				opacity: [0, 1],
				scale: [0.98, 1],
				duration: 600,
				easing: 'easeOutQuad'
			});
		}
	});
</script>

<div 
	bind:this={containerElement}
	class="weather-widget opacity-0 flex flex-col w-full max-w-xl rounded-2xl border border-border/40 bg-card/25 backdrop-blur-md p-5 shadow-lg shadow-black/20 my-4 text-foreground transition-all duration-300"
>
	<!-- Header -->
	<div class="flex items-start justify-between border-b border-border/10 pb-4 mb-4">
		<div class="flex flex-col min-w-0">
			<span class="text-xs font-semibold text-muted-foreground uppercase tracking-widest leading-none">PRONÓSTICO DEL CLIMA</span>
			<span class="text-lg font-bold text-foreground mt-1 truncate">{data.location}</span>
		</div>
		
		<!-- Tabs switcher -->
		<div class="flex items-center gap-1 bg-muted/40 border border-border/10 rounded-lg p-0.5">
			{#each ['today', '3days', 'week'] as tab}
				<button
					type="button"
					onclick={() => activeTab = tab as any}
					class={cn(
						"text-[10px] sm:text-xs font-semibold px-2.5 py-1 rounded transition-all duration-200 capitalize",
						activeTab === tab 
							? "bg-primary text-primary-foreground shadow-sm" 
							: "text-muted-foreground hover:text-foreground"
					)}
				>
					{tab === 'today' ? 'Hoy' : tab === '3days' ? '3 días' : 'Semana'}
				</button>
			{/each}
		</div>
	</div>

	<!-- Weather display -->
	{#if activeTab === 'today'}
		{@const Icon = getWeatherIcon(data.current.weathercode)}
		<!-- Today details view -->
		<div class="forecast-item flex items-center justify-between gap-4 py-2">
			<div class="flex items-center gap-4">
				<div class="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 border border-primary/20 text-primary animate-pulse-subtle">
					<Icon class="h-10 w-10 stroke-[1.5]" />
				</div>
				<div class="flex flex-col">
					<span class="text-4xl font-extrabold tracking-tighter flex items-start">
						{Math.round(data.current.temperature)}<span class="text-xl font-medium ml-0.5">°C</span>
					</span>
					<span class="text-sm font-semibold text-foreground/90 mt-0.5 capitalize">
						{getWeatherDescription(data.current.weathercode)}
					</span>
				</div>
			</div>
			
			<div class="flex flex-col gap-1.5 text-right font-medium text-xs text-muted-foreground">
				<span class="flex items-center justify-end gap-1.5">
					<Droplets class="h-3.5 w-3.5 text-blue-400" />
					Lluvia: {data.daily.precipitation_probability_max[0]}%
				</span>
				<span class="flex items-center justify-end gap-1.5">
					<Clock class="h-3.5 w-3.5 text-emerald-400" />
					Viento: {data.current.windspeed} km/h
				</span>
			</div>
		</div>
	{:else}
		<!-- Multiple days list view -->
		<div class="flex flex-col gap-2">
			{#each displayDays as day, idx (day.time)}
				{@const Icon = getWeatherIcon(day.code)}
				<div class="forecast-item flex items-center justify-between border border-border/10 rounded-xl bg-muted/10 hover:bg-primary/5 hover:border-primary/20 p-3.5 transition-all duration-200">
					<div class="flex items-center gap-3.5 min-w-0">
						<div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-background border border-border/15 text-primary">
							<Icon class="h-5 w-5" />
						</div>
						<div class="flex flex-col min-w-0">
							<span class="text-xs font-semibold capitalize text-foreground/90 truncate">
								{idx === 0 ? 'Hoy' : getDayName(day.time)}
							</span>
							<span class="text-[11px] text-muted-foreground/80 truncate">
								{getWeatherDescription(day.code)}
							</span>
						</div>
					</div>

					<div class="flex items-center gap-4 text-right">
						<span class="flex items-center gap-1 text-[11px] font-medium text-blue-400/90 shrink-0">
							<Droplets class="h-3 w-3" />
							{day.rainProb}%
						</span>
						<div class="flex items-center gap-2 font-mono text-xs w-20 justify-end">
							<span class="font-bold text-foreground">{day.tempMax}°</span>
							<span class="text-muted-foreground/60">{day.tempMin}°</span>
						</div>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.animate-pulse-subtle {
		animation: pulse-subtle 3s cubic-bezier(0.4, 0, 0.6, 1) infinite;
	}
	@keyframes pulse-subtle {
		0%, 100% {
			opacity: 1;
			transform: scale(1);
		}
		50% {
			opacity: 0.95;
			transform: scale(0.98);
		}
	}
</style>
