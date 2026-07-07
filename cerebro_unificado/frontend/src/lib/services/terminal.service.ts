import { TERMINAL_TOOL_NAME } from '$lib/constants';
import type { ToolExecutionResult } from '$lib/types';

/**
 * Service for executing terminal commands via brain_core's /api/terminal/run endpoint.
 */
export class TerminalService {
	/**
	 * Execute a terminal tool call. Only handles the 'run_terminal' tool.
	 */
	static async executeTool(
		toolName: string,
		params: Record<string, unknown>,
		signal?: AbortSignal
	): Promise<ToolExecutionResult> {
		return {
			content: 'La ejecución autónoma de comandos de terminal está estrictamente deshabilitada.',
			isError: true
		};
	}

	/**
	 * Fetch OS info from the backend for injecting into tool descriptions.
	 */
	static async getOsInfo(): Promise<{ system: string; distro: string; machine: string } | null> {
		const apiHost = window.location.port === '8000' ? '' : 'http://127.0.0.1:8000';
		try {
			const res = await fetch(`${apiHost}/api/terminal/info`);
			if (!res.ok) return null;
			return await res.json();
		} catch {
			return null;
		}
	}
}
