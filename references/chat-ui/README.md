# Chat UI (Svelte + Tailwind + Vite)

Réplica del chat estilo "LM Studio" con panel de razonamiento colapsable, barra de
metadata del modelo (tokens, tiempo, velocidad) y menú flotante de herramientas (+).

## Instalación

```bash
npm install
npm run dev
```

Abre la URL que te muestre Vite (normalmente http://localhost:5173).

## Estructura

```
src/
├── App.svelte                  # Layout principal (mensajes + input)
└── lib/
    ├── UserMessage.svelte       # Burbuja de usuario + acciones al hover
    ├── AssistantMessage.svelte  # Reasoning + respuesta + metadata + acciones
    ├── ReasoningPanel.svelte    # Panel colapsable "REASONING"
    ├── ModelMetadataBar.svelte  # Chip de modelo + tokens + tiempo + t/s
    ├── ChatInputBar.svelte      # Textarea + menú (+) + selector de modelo + enviar
    ├── Icon.svelte              # Componente de ícono genérico
    └── icons.js                 # Mapa de paths SVG (sin dependencias externas)
```

## Design tokens (tailwind.config.js)

| Token             | Hex       | Uso                              |
|-------------------|-----------|-----------------------------------|
| surface           | #15151f   | Fondo general                    |
| surface-2         | #1c1c29   | Paneles (reasoning, input, menú) |
| surface-3         | #242435   | Burbujas, chips, hover           |
| line-subtle       | #2a2a3c   | Bordes sutiles                   |
| ink-primary       | #e7e7ee   | Texto principal                  |
| ink-secondary     | #9797ab   | Texto secundario                 |
| ink-tertiary      | #6c6c80   | Texto terciario / iconos         |
| accent-indigo     | #6366f1   | Botón de enviar                  |
| accent-amber      | #f5b942   | Reservado para acentos           |

## Personalizar

- **Mensajes**: edita el array de mensajes directamente en `App.svelte`, o
  conviértelo en un `{#each mensajes as m}` si vas a conectarlo a datos reales.
- **Iconos nuevos**: agrega una entrada al objeto `icons` en `src/lib/icons.js`
  con el markup interno del SVG (paths/rects/etc).
- **Colores**: todo vive en `tailwind.config.js`, así que puedes cambiar el tema
  completo editando solo esos valores.
