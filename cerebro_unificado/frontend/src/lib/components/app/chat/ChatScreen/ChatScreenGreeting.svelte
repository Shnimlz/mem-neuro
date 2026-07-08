<script lang="ts">
	import { serverStore } from '$lib/stores/server.svelte';
	import { onMount } from 'svelte';
	import { createTimeline, stagger } from 'animejs';

	interface Props {
		isEmpty: boolean;
	}

	let { isEmpty = false }: Props = $props();

	let titleElement = $state<HTMLElement>();
	let pElement = $state<HTMLElement>();

	onMount(() => {
		if (!isEmpty) return;

		// Dividir el texto del título en letras individuales envueltas en spans
		if (titleElement) {
			const text = titleElement.textContent || '';
			titleElement.innerHTML = text
				.split('')
				.map((char) => `<span class="letter inline-block min-w-[0.25em]">${char === ' ' ? '&nbsp;' : char}</span>`)
				.join('');
		}

		// Animación con Anime.js v4
		createTimeline({ loop: false })
			.add({
				targets: '.letter',
				scale: [0.3, 1],
				opacity: [0, 1],
				translateY: [20, 0],
				ease: 'easeOutElastic(1, 0.6)',
				duration: 800,
				delay: stagger(40)
			})
			.add({
				targets: pElement,
				opacity: [0, 1],
				translateY: [15, 0],
				ease: 'easeOutCubic',
				duration: 600
			}, '-=400');
	});
</script>

<div
	class={[
		'pointer-events-none mb-4 hidden px-4 text-center text-balance',
		isEmpty && 'mb-[calc(50dvh-8rem)] md:mb-6 pointer-events-auto block!'
	]}
>
	<h1 bind:this={titleElement} class="mb-2 text-2xl font-semibold tracking-tight md:text-3xl">Hello there</h1>

	<p bind:this={pElement} class="text-muted-foreground md:text-lg opacity-0">
		{serverStore.props?.modalities?.audio ? 'Record audio, type a message ' : 'Type a message'} or upload
		files to get started
	</p>
</div>
