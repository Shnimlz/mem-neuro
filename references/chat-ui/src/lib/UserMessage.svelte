<script>
  import Icon from './Icon.svelte'
  export let text = ''
</script>

<div class="group flex flex-col items-end mb-1">
  <div
    class="max-w-[75%] bg-surface-3 text-ink-primary rounded-2xl rounded-tr-sm px-4 py-2.5 text-[15px] leading-relaxed"
  >
    {text}
  </div>
  <div class="flex gap-1 mt-1.5 pr-1 opacity-0 group-hover:opacity-100 transition-opacity">
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
      title="Ramificar"><Icon name="branch" size={14} /></button
    >
    <button
      class="text-ink-tertiary hover:text-ink-primary p-1 rounded-md hover:bg-surface-3 transition-colors"
      title="Eliminar"><Icon name="trash" size={14} /></button
    >
  </div>
</div>
