<script>
  import ReasoningPanel from './ReasoningPanel.svelte'
  import ModelMetadataBar from './ModelMetadataBar.svelte'
  import Icon from './Icon.svelte'

  export let reasoning = ''
  export let response = ''
  export let model = 'DeepSeek-R1-Llama'
  export let modelSize = '8B'
  export let tokens = 0
  export let seconds = 0
  export let tokensPerSec = 0
</script>

<div class="group flex flex-col mb-6 max-w-[85%]">
  <ReasoningPanel content={reasoning} />

  <p class="text-[15px] leading-relaxed text-ink-primary mt-3">
    {response}
  </p>

  <div class="flex items-center justify-between mt-4 flex-wrap gap-2">
    <ModelMetadataBar {model} {modelSize} {tokens} {seconds} {tokensPerSec} />
  </div>

  <div class="flex gap-1 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
    <button
      class="text-ink-tertiary hover:text-ink-primary p-1 rounded-md hover:bg-surface-3 transition-colors"
      title="Copiar"><Icon name="copy" size={14} /></button
    >
    <button
      class="text-ink-tertiary hover:text-ink-primary p-1 rounded-md hover:bg-surface-3 transition-colors"
      title="Editar"><Icon name="edit" size={14} /></button
    >
    <button
      class="text-ink-tertiary hover:text-ink-primary p-1 rounded-md hover:bg-surface-3 transition-colors"
      title="Regenerar"><Icon name="refresh" size={14} /></button
    >
    <button
      class="text-ink-tertiary hover:text-ink-primary p-1 rounded-md hover:bg-surface-3 transition-colors"
      title="Ramificar"><Icon name="branch" size={14} /></button
    >
    <button
      class="text-ink-tertiary hover:text-ink-primary p-1 rounded-md hover:bg-surface-3 transition-colors"
      title="Eliminar"><Icon name="trash" size={14} /></button
    >
  </div>
</div>
