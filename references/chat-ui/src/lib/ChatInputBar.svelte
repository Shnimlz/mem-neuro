<script>
  import Icon from './Icon.svelte'

  let menuOpen = false
  let message = ''

  const menuItems = [
    { icon: 'paperclip', label: 'Add files', hasSubmenu: true },
    { icon: 'message', label: 'System Message', hasSubmenu: false },
    { icon: 'tool', label: 'Tools', hasSubmenu: true },
    { icon: 'server', label: 'MCP Servers', hasSubmenu: true },
  ]

  function toggleMenu() {
    menuOpen = !menuOpen
  }
</script>

<div class="relative">
  {#if menuOpen}
    <div
      class="absolute bottom-full left-0 mb-2 w-56 bg-surface-2 border border-line-subtle rounded-xl2 shadow-xl py-1.5 z-10"
    >
      {#each menuItems as item}
        <button
          class="w-full flex items-center justify-between px-3 py-2 text-sm text-ink-secondary hover:bg-surface-3 hover:text-ink-primary transition-colors"
        >
          <span class="flex items-center gap-2.5">
            <Icon name={item.icon} size={15} />
            {item.label}
          </span>
          {#if item.hasSubmenu}
            <Icon name="chevronRight" size={14} />
          {/if}
        </button>
      {/each}
    </div>
  {/if}

  <div class="bg-surface-2 border border-line-subtle rounded-2xl p-3">
    <textarea
      bind:value={message}
      placeholder="Escribe un mensaje..."
      rows="1"
      class="w-full bg-transparent resize-none outline-none text-[15px] text-ink-primary placeholder:text-ink-tertiary px-1"
    ></textarea>

    <div class="flex items-center justify-between mt-2">
      <button
        class="w-8 h-8 flex items-center justify-center rounded-full text-ink-secondary hover:bg-surface-3 hover:text-ink-primary transition-colors"
        on:click={toggleMenu}
      >
        <Icon name="plus" size={18} />
      </button>

      <div class="flex items-center gap-2">
        <span
          class="flex items-center gap-1.5 text-xs text-ink-secondary bg-surface-3 rounded-full px-2.5 py-1"
        >
          <Icon name="bulb" size={13} />
          DeepSeek-R1-Llama
          <span class="bg-surface text-ink-tertiary rounded px-1.5 py-0.5 text-[10px] font-medium"
            >8B</span
          >
        </span>

        <button
          class="w-8 h-8 flex items-center justify-center rounded-full bg-accent-indigo text-white hover:opacity-90 transition-opacity"
        >
          <Icon name="send" size={16} />
        </button>
      </div>
    </div>
  </div>
</div>
