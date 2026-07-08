<script lang="ts">
	import { Label } from '$lib/components/ui/label';
	import { Textarea } from '$lib/components/ui/textarea';
	import { Button } from '$lib/components/ui/button';
	import { Save, RotateCcw } from '@lucide/svelte';

	let content = $state('');
	let savedContent = $state('');
	let loading = $state(true);
	let saving = $state(false);
	let statusMsg = $state('');

	async function loadInstructions() {
		try {
			const res = await fetch('/api/user_instructions');
			if (res.ok) {
				const data = await res.json();
				content = data.content || '';
				savedContent = content;
			}
		} catch {
			statusMsg = 'Error al cargar instrucciones.';
		} finally {
			loading = false;
		}
	}

	async function saveInstructions() {
		saving = true;
		statusMsg = '';
		try {
			const res = await fetch('/api/user_instructions', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ content })
			});
			if (res.ok) {
				savedContent = content;
				statusMsg = 'Instrucciones guardadas correctamente.';
				setTimeout(() => (statusMsg = ''), 3000);
			} else {
				statusMsg = 'Error al guardar.';
			}
		} catch {
			statusMsg = 'Error de conexión con el backend.';
		} finally {
			saving = false;
		}
	}

	function resetContent() {
		content = savedContent;
		statusMsg = '';
	}

	let hasChanges = $derived(content !== savedContent);

	$effect(() => {
		loadInstructions();
	});
</script>

<div class="space-y-6">
	<div class="rounded-lg border border-border/40 p-4 bg-muted/20 space-y-2">
		<Label class="text-sm font-semibold">Instrucciones Personales para la IA</Label>
		<p class="text-xs text-muted-foreground">
			Define cómo quieres que la IA te responda: estilo, preferencias técnicas, hardware, idioma,
			nivel de detalle, etc. Estas instrucciones se inyectan en cada conversación.
		</p>
	</div>

	{#if loading}
		<div class="flex items-center justify-center py-8">
			<div class="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent"></div>
			<span class="ml-2 text-sm text-muted-foreground">Cargando instrucciones...</span>
		</div>
	{:else}
		<div class="space-y-3">
			<Textarea
				bind:value={content}
				placeholder="Ejemplo: Puedo tener dificultad para concentrarme. Divide la información en partes pequeñas. Usa frases cortas y claras..."
				class="min-h-[280px] font-mono text-sm resize-y bg-background/50 border-border/40"
			/>

			<div class="flex items-center justify-between">
				<div class="flex items-center gap-2">
					{#if statusMsg}
						<span class="text-xs text-muted-foreground animate-in fade-in">{statusMsg}</span>
					{/if}
					{#if hasChanges}
						<span class="text-xs text-amber-500 font-medium">• Cambios sin guardar</span>
					{/if}
				</div>

				<div class="flex items-center gap-2">
					<Button
						variant="outline"
						size="sm"
						onclick={resetContent}
						disabled={!hasChanges || saving}
					>
						<RotateCcw class="h-3.5 w-3.5 mr-1" />
						Descartar
					</Button>
					<Button
						size="sm"
						onclick={saveInstructions}
						disabled={!hasChanges || saving}
					>
						<Save class="h-3.5 w-3.5 mr-1" />
						{saving ? 'Guardando...' : 'Guardar'}
					</Button>
				</div>
			</div>
		</div>

		<div class="rounded-md border border-border/30 p-3 bg-card/30 space-y-1.5">
			<p class="text-xs font-semibold text-muted-foreground">Ejemplos de instrucciones útiles:</p>
			<ul class="text-xs text-muted-foreground space-y-1 list-disc list-inside">
				<li>Divide la información en partes pequeñas. Usa frases cortas y claras.</li>
				<li>En temas de programación, primero explica simple, luego técnico.</li>
				<li>Mi hardware es: CPU AMD Ryzen 5, GPU RX 5500 XT, CachyOS Linux.</li>
				<li>Prioriza soluciones compatibles con AMD y Linux.</li>
				<li>Usa pacman para paquetes. Prioriza Arch Linux.</li>
			</ul>
		</div>
	{/if}
</div>
