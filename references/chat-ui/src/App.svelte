<script>
  import UserMessage from './lib/UserMessage.svelte'
  import AssistantMessage from './lib/AssistantMessage.svelte'
  import ChatInputBar from './lib/ChatInputBar.svelte'
</script>

<div class="min-h-screen flex flex-col">
  <main class="flex-1 overflow-y-auto">
    <div class="max-w-2xl mx-auto px-4 pt-10 pb-6">
      <UserMessage text="¿Qué hora es en España?" />

      <AssistantMessage
        reasoning="El usuario pregunta la hora actual en España. Para responder con precisión necesito considerar la zona horaria vigente (CET o CEST según la época del año) y verificar la hora exacta contra una fuente confiable, ya que no tengo acceso a un reloj en tiempo real."
        response="España está en horario de verano (CEST, UTC+2) durante estas fechas. Para ver la hora exacta al segundo, te recomiendo consultar time.is/Madrid."
        model="DeepSeek-R1-Llama"
        modelSize="8B"
        tokens={700}
        seconds={20}
        tokensPerSec={34.74}
      />
    </div>
  </main>

  <div class="sticky bottom-0 bg-gradient-to-t from-surface via-surface to-transparent pt-6 pb-4">
    <div class="max-w-2xl mx-auto px-4">
      <ChatInputBar />
    </div>
  </div>
</div>
