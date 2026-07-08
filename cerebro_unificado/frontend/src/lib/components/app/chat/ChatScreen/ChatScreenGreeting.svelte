<script lang="ts">
	import { serverStore } from '$lib/stores/server.svelte';
	import { createTimeline, stagger, createScope } from 'animejs';

	interface Props {
		isEmpty: boolean;
	}

	let { isEmpty = false }: Props = $props();

	let containerEl = $state<HTMLElement>();
	let titleElement = $state<HTMLElement>();
	let pElement = $state<HTMLElement>();

	$effect(() => {
		if (!isEmpty || !containerEl || !titleElement || !pElement) return;

		// Check prefers-reduced-motion
		const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
		if (prefersReduced) {
			titleElement.style.opacity = '1';
			pElement.style.opacity = '1';
			return;
		}

		// Split title text into individual letter spans
		const text = titleElement.textContent || '';
		titleElement.innerHTML = text
			.split('')
			.map(
				(char) =>
					`<span class="letter inline-block min-w-[0.25em]">${char === ' ' ? '&nbsp;' : char}</span>`
			)
			.join('');

		// Reveal the title container now that its children (letters) are prepared and will animate from opacity 0
		titleElement.classList.remove('opacity-0');

		// Create scoped animation for proper cleanup
		const scope = createScope({ root: containerEl }).add(() => {
			createTimeline({ loop: false })
				.add('.letter', {
					scale: [0.3, 1],
					opacity: [0, 1],
					translateY: [20, 0],
					ease: 'outElastic(1, 0.6)',
					duration: 800,
					delay: stagger(40)
				})
				.add(
					pElement!,
					{
						opacity: [0, 1],
						translateY: [15, 0],
						ease: 'outCubic',
						duration: 600
					},
					'-=400'
				);
		});

		return () => {
			scope.revert();
		};
	});
</script>

<div
	bind:this={containerEl}
	class={[
		'pointer-events-none mb-4 hidden px-4 text-center text-balance',
		isEmpty && 'mb-[calc(50dvh-8rem)] md:mb-6 pointer-events-auto block!'
	]}
>
	<h1
		bind:this={titleElement}
		class="mb-2 text-2xl font-semibold tracking-tight md:text-3xl opacity-0"
	>
		Hello there
	</h1>

	<p bind:this={pElement} class="text-muted-foreground md:text-lg opacity-0">
		{serverStore.props?.modalities?.audio ? 'Record audio, type a message ' : 'Type a message'} or upload
		files to get started
	</p>
</div>
