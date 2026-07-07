// Íconos en formato "feather-style": trazos, sin relleno, viewBox 0 0 24 24.
// Cada valor es el markup interno del <svg>, insertado vía {@html} en Icon.svelte.
export const icons = {
  copy: `<rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>`,
  edit: `<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>`,
  trash: `<polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>`,
  branch: `<line x1="6" y1="3" x2="6" y2="15"></line><circle cx="18" cy="6" r="3"></circle><circle cx="6" cy="18" r="3"></circle><path d="M18 9a9 9 0 0 1-9 9"></path>`,
  chevronDown: `<polyline points="6 9 12 15 18 9"></polyline>`,
  chevronRight: `<polyline points="9 18 15 12 9 6"></polyline>`,
  brain: `<path d="M9.5 2a2.5 2.5 0 0 0-2.5 2.5v.6A3 3 0 0 0 5 8v1a3 3 0 0 0-1 5.8V16a3 3 0 0 0 3 3 2.5 2.5 0 0 0 2.5 2.5 2.5 2.5 0 0 0 2.5-2.5V4.5A2.5 2.5 0 0 0 9.5 2z"></path><path d="M14.5 2a2.5 2.5 0 0 1 2.5 2.5v.6A3 3 0 0 1 19 8v1a3 3 0 0 1 1 5.8V16a3 3 0 0 1-3 3 2.5 2.5 0 0 1-2.5 2.5 2.5 2.5 0 0 1-2.5-2.5V4.5A2.5 2.5 0 0 1 14.5 2z"></path>`,
  clock: `<circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline>`,
  refresh: `<polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>`,
  hash: `<line x1="4" y1="9" x2="20" y2="9"></line><line x1="4" y1="15" x2="20" y2="15"></line><line x1="10" y1="3" x2="8" y2="21"></line><line x1="16" y1="3" x2="14" y2="21"></line>`,
  zap: `<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>`,
  plus: `<line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line>`,
  paperclip: `<path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path>`,
  message: `<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>`,
  tool: `<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.77z"></path>`,
  server: `<rect x="2" y="3" width="20" height="7" rx="1"></rect><rect x="2" y="14" width="20" height="7" rx="1"></rect><line x1="6" y1="6.5" x2="6.01" y2="6.5"></line><line x1="6" y1="17.5" x2="6.01" y2="17.5"></line>`,
  send: `<line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline>`,
  bulb: `<path d="M9 18h6"></path><path d="M10 22h4"></path><path d="M12 2a7 7 0 0 0-4 12.7c.5.4.8 1 .9 1.7l.1.6h6l.1-.6c.1-.7.4-1.3.9-1.7A7 7 0 0 0 12 2z"></path>`,
}
