<script lang="ts">
	import { Download, Upload, Trash2, RefreshCw } from '@lucide/svelte';
	import {
		DialogConversationSelection,
		DialogConfirmation,
		DialogExportSettings
	} from '$lib/components/app';
	import { createMessageCountMap } from '$lib/utils';
	import { settingsStore } from '$lib/stores/settings.svelte';
	import { conversationsStore, conversations } from '$lib/stores/conversations.svelte';
	import { toast } from 'svelte-sonner';
	import { fade } from 'svelte/transition';
	import { ConversationSelectionMode, HtmlInputType, FileExtensionText } from '$lib/enums';
	import SettingsChatImportExportSection from './SettingsChatImportExportSection.svelte';
	import SettingsGroup from '$lib/components/app/settings/SettingsGroup.svelte';

	let exportedConversations = $state<DatabaseConversation[]>([]);
	let importedConversations = $state<DatabaseConversation[]>([]);
	let showExportSummary = $state(false);
	let showImportSummary = $state(false);

	let showExportDialog = $state(false);
	let showImportDialog = $state(false);
	let availableConversations = $state<DatabaseConversation[]>([]);
	let messageCountMap = $state<Map<string, number>>(new Map());
	let fullImportData = $state<Array<{ conv: DatabaseConversation; messages: DatabaseMessage[] }>>(
		[]
	);

	// Delete functionality state
	let showDeleteDialog = $state(false);

	// Settings import/export state
	let showSettingsExportSummary = $state(false);
	let showSettingsImportSummary = $state(false);
	let showSettingsExportDialog = $state(false);
	let includeSensitiveData = $state(false);

	function handleSettingsExport() {
		showSettingsExportDialog = true;
		includeSensitiveData = false;
	}

	function handleSettingsExportConfirm() {
		showSettingsExportDialog = false;

		try {
			const data = settingsStore.exportSettings(includeSensitiveData);
			const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `llama_settings_${new Date().toISOString().split('T')[0]}.json`;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(url);

			showSettingsExportSummary = true;
			showSettingsImportSummary = false;
			toast.success('Settings exported');
		} catch (err) {
			console.error('Failed to export settings:', err);
			toast.error('Failed to export settings');
		}
	}

	function handleSettingsExportCancel() {
		showSettingsExportDialog = false;
	}

	function handleSettingsImport() {
		try {
			const input = document.createElement('input');
			input.type = HtmlInputType.FILE;
			input.accept = FileExtensionText.JSON;

			input.onchange = async (e) => {
				const file = (e.target as HTMLInputElement)?.files?.[0];
				if (!file) return;

				try {
					const text = await file.text();
					const data = JSON.parse(text);

					if (!data || typeof data !== 'object' || !data.config) {
						toast.error('Invalid settings file: missing config');
						return;
					}

					settingsStore.importSettings(data);

					showSettingsImportSummary = true;
					showSettingsExportSummary = false;
					toast.success('Settings imported successfully');
				} catch (err) {
					console.error('Failed to import settings:', err);
					toast.error('Failed to import settings');
				}
			};

			input.click();
		} catch (err) {
			console.error('Failed to open file picker:', err);
			toast.error('Failed to open file picker');
		}
	}

	async function handleExportClick() {
		try {
			const allConversations = conversations();
			if (allConversations.length === 0) {
				toast.info('No conversations to export');
				return;
			}

			const conversationsWithMessages = await Promise.all(
				allConversations.map(async (conv: DatabaseConversation) => {
					const messages = await conversationsStore.getConversationMessages(conv.id);
					return { conv, messages };
				})
			);

			messageCountMap = createMessageCountMap(conversationsWithMessages);
			availableConversations = allConversations;
			showExportDialog = true;
		} catch (err) {
			console.error('Failed to load conversations:', err);
			alert('Failed to load conversations');
		}
	}

	async function handleExportConfirm(selectedConversations: DatabaseConversation[]) {
		try {
			const allData: ExportedConversation[] = await Promise.all(
				selectedConversations.map(async (conv) => {
					const messages = await conversationsStore.getConversationMessages(conv.id);
					return { conv: $state.snapshot(conv), messages: $state.snapshot(messages) };
				})
			);

			if (allData.length === 1) {
				conversationsStore.downloadConversationFile(allData[0]);
			} else {
				conversationsStore.downloadConversationsArchive(allData);
			}

			exportedConversations = selectedConversations;
			showExportSummary = true;
			showImportSummary = false;
			showExportDialog = false;
		} catch (err) {
			console.error('Export failed:', err);
			alert('Failed to export conversations');
		}
	}

	async function handleImportClick() {
		try {
			const input = document.createElement('input');

			input.type = HtmlInputType.FILE;
			input.accept = `${FileExtensionText.JSON},${FileExtensionText.JSONL},${FileExtensionText.ZIP}`;

			input.onchange = async (e) => {
				const file = (e.target as HTMLInputElement)?.files?.[0];
				if (!file) return;

				try {
					const importedData = await conversationsStore.parseImportFile(file);

					if (importedData.length === 0) {
						throw new Error('No conversations found in file');
					}

					fullImportData = importedData;
					availableConversations = importedData.map((item) => item.conv);
					messageCountMap = createMessageCountMap(importedData);
					showImportDialog = true;
				} catch (err: unknown) {
					const message = err instanceof Error ? err.message : 'Unknown error';

					console.error('Failed to parse file:', err);
					alert(`Failed to parse file: ${message}`);
				}
			};

			input.click();
		} catch (err) {
			console.error('Import failed:', err);
			alert('Failed to import conversations');
		}
	}

	async function handleImportConfirm(selectedConversations: DatabaseConversation[]) {
		try {
			const selectedIds = new Set(selectedConversations.map((c) => c.id));
			const selectedData = $state
				.snapshot(fullImportData)
				.filter((item) => selectedIds.has(item.conv.id));

			await conversationsStore.importConversationsData(selectedData);

			importedConversations = selectedConversations;
			showImportSummary = true;
			showExportSummary = false;
			showImportDialog = false;
		} catch (err) {
			console.error('Import failed:', err);
			alert('Failed to import conversations. Please check the file format.');
		}
	}

	async function handleDeleteAllClick() {
		try {
			const allConversations = conversations();

			if (allConversations.length === 0) {
				toast.info('No conversations to delete');
				return;
			}

			showDeleteDialog = true;
		} catch (err) {
			console.error('Failed to load conversations for deletion:', err);
			toast.error('Failed to load conversations');
		}
	}

	async function handleDeleteAllConfirm() {
		try {
			await conversationsStore.deleteAll();

			showDeleteDialog = false;
		} catch (err) {
			console.error('Failed to delete conversations:', err);
		}
	}

	function handleDeleteAllCancel() {
		showDeleteDialog = false;
	}

	// Database reset state
	let showResetDialog = $state(false);
	let isResetting = $state(false);

	function handleResetDbClick() {
		showResetDialog = true;
	}

	async function handleResetDbConfirm() {
		if (isResetting) return;
		isResetting = true;

		try {
			const res = await fetch('/api/database/reset', { method: 'POST' });
			if (!res.ok) {
				throw new Error('Fallo al restablecer la base de datos');
			}
			toast.success('El cerebro autónomo se ha restablecido correctamente.');
			showResetDialog = false;
			setTimeout(() => {
				window.location.reload();
			}, 1000);
		} catch (err) {
			console.error('Error al restablecer base de datos:', err);
			toast.error('Ocurrió un error al intentar restablecer la base de datos.');
		} finally {
			isResetting = false;
		}
	}

	function handleResetDbCancel() {
		if (!isResetting) {
			showResetDialog = false;
		}
	}
</script>

<div class="space-y-12" in:fade={{ duration: 150 }}>
	<SettingsGroup title="Conversations">
		<SettingsChatImportExportSection
			title="Export"
			description="Download your conversations as a ZIP of JSONL files. This includes all messages, attachments, and conversation history."
			IconComponent={Download}
			buttonText="Export conversations"
			onclick={handleExportClick}
			summary={{ show: showExportSummary, verb: 'Exported', items: exportedConversations }}
		/>

		<SettingsChatImportExportSection
			title="Import"
			description="Import one or more conversations from a previously exported ZIP or JSONL file. This will merge with your existing conversations."
			IconComponent={Upload}
			buttonText="Import conversations"
			onclick={handleImportClick}
			summary={{ show: showImportSummary, verb: 'Imported', items: importedConversations }}
		/>

		<SettingsChatImportExportSection
			title="Delete All"
			description="Permanently delete all conversations and their messages. This action cannot be undone. Consider exporting your conversations first if you want to keep a backup."
			IconComponent={Trash2}
			buttonText="Delete all conversations"
			onclick={handleDeleteAllClick}
			titleClass="text-destructive"
			buttonVariant="destructive"
			buttonClass="text-destructive-foreground justify-start justify-self-start bg-destructive hover:bg-destructive/80 md:w-auto"
		/>
	</SettingsGroup>

	<SettingsGroup title="Settings">
		<SettingsChatImportExportSection
			title="Export"
			description="Export your chat settings and preferences as a JSON file."
			IconComponent={Download}
			buttonText="Export settings"
			onclick={handleSettingsExport}
			summary={{ show: showSettingsExportSummary, verb: 'Exported', items: [] }}
		/>

		<SettingsChatImportExportSection
			title="Import"
			description="Import chat settings from a previously exported JSON file. This will merge with your existing settings."
			IconComponent={Upload}
			buttonText="Import settings"
			onclick={handleSettingsImport}
			summary={{ show: showSettingsImportSummary, verb: 'Imported', items: [] }}
		/>
	</SettingsGroup>

	<SettingsGroup title="Base de Datos">
		<SettingsChatImportExportSection
			title="Restablecer base de datos"
			description="Borra permanentemente todo el historial de chat, embeddings vectoriales, clasificaciones y fuentes guardadas de la base de datos local."
			IconComponent={RefreshCw}
			buttonText="Restablecer Cerebro Autónomo"
			onclick={handleResetDbClick}
			titleClass="text-destructive font-semibold"
			buttonVariant="destructive"
			buttonClass="text-destructive-foreground justify-start justify-self-start bg-destructive hover:bg-destructive/80 md:w-auto"
		/>
	</SettingsGroup>
</div>

<DialogExportSettings
	bind:open={showSettingsExportDialog}
	bind:includeSensitiveData
	onConfirm={handleSettingsExportConfirm}
	onCancel={handleSettingsExportCancel}
/>

<DialogConversationSelection
	conversations={availableConversations}
	{messageCountMap}
	mode={ConversationSelectionMode.EXPORT}
	bind:open={showExportDialog}
	onCancel={() => (showExportDialog = false)}
	onConfirm={handleExportConfirm}
/>

<DialogConversationSelection
	conversations={availableConversations}
	{messageCountMap}
	mode={ConversationSelectionMode.IMPORT}
	bind:open={showImportDialog}
	onCancel={() => (showImportDialog = false)}
	onConfirm={handleImportConfirm}
/>

<DialogConfirmation
	bind:open={showDeleteDialog}
	title="Delete all conversations"
	description="Are you sure you want to delete all conversations? This action cannot be undone and will permanently remove all your conversations and messages."
	confirmText="Delete All"
	cancelText="Cancel"
	variant="destructive"
	icon={Trash2}
	onConfirm={handleDeleteAllConfirm}
	onCancel={handleDeleteAllCancel}
/>

<DialogConfirmation
	bind:open={showResetDialog}
	title="Restablecer Cerebro Autónomo"
	description="¿Estás seguro de que deseas restablecer el cerebro autónomo? Esta acción borrará permanentemente todo el historial de chat, embeddings vectoriales, clasificaciones y fuentes guardadas."
	confirmText={isResetting ? 'Restableciendo...' : 'Restablecer'}
	cancelText="Cancelar"
	variant="destructive"
	icon={RefreshCw}
	onConfirm={handleResetDbConfirm}
	onCancel={handleResetDbCancel}
>
	{#if isResetting}
		<div class="flex items-center justify-center gap-2 py-4">
			<span class="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent"></span>
			<span class="text-xs text-muted-foreground">Procesando reinicio físico de base de datos...</span>
		</div>
	{/if}
</DialogConfirmation>
