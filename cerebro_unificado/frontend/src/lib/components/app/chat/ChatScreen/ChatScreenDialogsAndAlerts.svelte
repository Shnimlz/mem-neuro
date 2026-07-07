<script lang="ts">
	import { Trash2 } from '@lucide/svelte';
	import { ErrorDialogType } from '$lib/enums';
	import {
		DialogChatError,
		DialogConfirmation,
		DialogEmptyFileAlert,
		DialogFileUploadError,
		DialogCodePreview
	} from '$lib/components/app';
	import { chatStore } from '$lib/stores/chat.svelte';

	let {
		showDeleteDialog,
		handleDeleteConfirm,
		showEmptyFileDialog,
		emptyFileNames,
		activeErrorDialog,
		handleErrorDialogOpenChange,
		fileUpload
	} = $props();
</script>

<DialogFileUploadError
	bind:open={fileUpload.showFileErrorDialog}
	fileErrorData={fileUpload.fileErrorData}
/>

<DialogConfirmation
	bind:open={showDeleteDialog}
	title="Delete Conversation"
	description="Are you sure you want to delete this conversation? This action cannot be undone and will permanently remove all messages in this conversation."
	confirmText="Delete"
	cancelText="Cancel"
	variant="destructive"
	icon={Trash2}
	onConfirm={handleDeleteConfirm}
	onCancel={() => (showDeleteDialog = false)}
/>

<DialogEmptyFileAlert
	bind:open={showEmptyFileDialog}
	emptyFiles={emptyFileNames}
	onOpenChange={(open) => {
		if (!open) {
			emptyFileNames = [];
		}
	}}
/>

<DialogChatError
	message={activeErrorDialog?.message ?? ''}
	contextInfo={activeErrorDialog?.contextInfo}
	onOpenChange={handleErrorDialogOpenChange}
	open={Boolean(activeErrorDialog)}
	type={activeErrorDialog?.type ?? ErrorDialogType.SERVER}
/>

<DialogCodePreview
	bind:open={chatStore.codePreviewState.open}
	code={chatStore.codePreviewState.code}
	language={chatStore.codePreviewState.language}
/>
