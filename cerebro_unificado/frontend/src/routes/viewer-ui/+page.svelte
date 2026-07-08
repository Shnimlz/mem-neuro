<script lang="ts">
	import { onMount } from 'svelte';
	import { animate } from 'animejs';

	let iframeContainer = $state<HTMLElement>();

	onMount(() => {
		if (iframeContainer) {
			animate(iframeContainer, {
				opacity: [0, 1],
				scale: [0.97, 1],
				ease: 'easeOutCubic',
				duration: 800
			});
		}
	});
</script>

<div
	bind:this={iframeContainer}
	class="w-full h-dvh flex flex-col p-0 m-0 overflow-hidden bg-stone-950 opacity-0"
>
	<!-- Cabecera de Control Premium (Material/Glassmorphism) -->
	<div class="flex items-center justify-between px-6 py-3 border-b border-border/20 bg-card/60 backdrop-blur-md z-10">
		<div class="flex items-center gap-3">
			<div class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></div>
			<span class="text-xs font-semibold uppercase tracking-wider text-muted-foreground select-none">Grafo Neuronal Activo</span>
		</div>
		<div class="flex items-center gap-2">
			<button
				onclick={() => {
					const iframe = document.querySelector('iframe');
					if (iframe) iframe.src = iframe.src;
				}}
				class="inline-flex cursor-pointer items-center justify-center rounded-lg bg-muted-foreground/10 hover:bg-muted-foreground/20 px-3 py-1.5 text-xs font-medium text-foreground transition-all duration-200"
			>
				Recargar Vista
			</button>
		</div>
	</div>

	<iframe
		src="./viewer.html"
		title="Visualizador Neuronal Cognitivo"
		class="w-full grow border-0 m-0 p-0"
	></iframe>
</div>
