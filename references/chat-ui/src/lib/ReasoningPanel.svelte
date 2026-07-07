<script>
  import Icon from './Icon.svelte'
  export let content = ''
  let open = true
</script>

<div class="border border-line-subtle rounded-xl2 bg-surface-2 overflow-hidden">
  <button
    class="w-full flex items-center justify-between px-4 py-3 text-ink-secondary hover:text-ink-primary transition-colors"
    on:click={() => (open = !open)}
  >
    <span class="flex items-center gap-2 text-xs font-semibold tracking-wider uppercase">
      <Icon name="brain" size={15} />
      Reasoning
    </span>
    <span class="transition-transform duration-200" class:rotate-180={open}>
      <Icon name="chevronDown" size={16} />
    </span>
  </button>

  {#if open}
    <div
      class="px-4 pb-4 pt-3 text-[15px] leading-relaxed text-ink-secondary border-t border-line-subtle"
    >
      {content}
    </div>
  {/if}
</div>
