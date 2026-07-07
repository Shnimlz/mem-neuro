import { JsonSchemaType, ToolCallType } from '$lib/enums';
import type { OpenAIToolDefinition } from '$lib/types';

export const TERMINAL_TOOL_NAME = 'run_terminal';

export const TERMINAL_TIMEOUT_MS = 10000;

/**
 * Tool definition sent to the LLM so it can invoke bash commands.
 * The description is a template — the UI replaces {os_info} at runtime
 * with real OS data from GET /api/terminal/info.
 */
export const TERMINAL_TOOL_DEFINITION: OpenAIToolDefinition = {
	type: ToolCallType.FUNCTION,
	function: {
		name: TERMINAL_TOOL_NAME,
		description:
			`Execute a bash terminal command on the user's local Linux PC. ` +
			`Use this to check disk space, list files, inspect processes, read logs, ` +
			`check systemd services, or run any read-only system command. ` +
			`NEVER use sudo or commands that modify/delete files unless explicitly asked. ` +
			`The system will block sudo automatically.`,
		parameters: {
			type: JsonSchemaType.OBJECT,
			properties: {
				command: {
					type: JsonSchemaType.STRING,
					description: 'The bash command to execute (e.g. "df -h", "ls -la", "systemctl --user status")'
				}
			},
			required: ['command']
		}
	}
};
