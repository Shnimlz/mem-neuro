export const BOX_BORDER =
	'border border-border/30 focus-within:border-primary/40 dark:border-border/20 dark:focus-within:border-primary/40';

export const INPUT_CLASSES = `
    bg-card/75 dark:bg-card/45
    backdrop-blur-md
    ${BOX_BORDER}
    shadow-sm focus-within:shadow-md
    focus-within:ring-2 focus-within:ring-primary/10
    transition-all duration-300 ease-out
    outline-none
    text-foreground
`;

export const PANEL_CLASSES = `
    bg-background
    border border-border/30 dark:border-border/20
    shadow-sm backdrop-blur-lg!
    rounded-t-lg!
`;

export const CHAT_FORM_POPOVER_MAX_HEIGHT = 'max-h-80';
