import { JsonSchemaType, ToolCallType } from '$lib/enums';
import type { OpenAIToolDefinition } from '$lib/types';

export const WEB_SEARCH_TOOL_NAME = 'web_search';

export const WEB_SEARCH_TOOL_DEFINITION: OpenAIToolDefinition = {
	type: ToolCallType.FUNCTION,
	function: {
		name: WEB_SEARCH_TOOL_NAME,
		description:
			'Search the web for up-to-date information, news, code examples, software releases, ' +
			'or facts that are not present in your local knowledge base.',
		parameters: {
			type: JsonSchemaType.OBJECT,
			properties: {
				query: {
					type: JsonSchemaType.STRING,
					description: 'The search query to look up (e.g. "latest version of CachyOS Linux")'
				}
			},
			required: ['query']
		}
	}
};
