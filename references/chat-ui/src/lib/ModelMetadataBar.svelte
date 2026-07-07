<script>
  import Icon from './Icon.svelte'
  export let model = ''
  export let modelSize = ''
  export let tokens = 0
  export let seconds = 0
  export let tokensPerSec = 0
</script>

<div class="flex items-center gap-3 text-xs text-ink-tertiary flex-wrap">
  <span
    class="flex items-center gap-1.5 bg-surface-3 border border-line-subtle rounded-full px-2.5 py-1 text-ink-secondary"
  >
    <Icon name="bulb" size={13} />
    {model}
    <span class="bg-surface text-ink-tertiary rounded px-1.5 py-0.5 text-[10px] font-medium">
      {modelSize}
    </span>
  </span>

  <span class="flex items-center gap-1"><Icon name="hash" size={13} />{tokens} tokens</span>
  <span class="flex items-center gap-1"><Icon name="clock" size={13} />{seconds}s</span>
  <span class="flex items-center gap-1"><Icon name="zap" size={13} />{tokensPerSec} t/s</span>
</div>
