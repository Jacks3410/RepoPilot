import { getBuiltinTools, Tool } from "./builtins/index.ts";

export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, any>;
}

export class ToolResult {
  toolCallId: string;
  content: string;
  isError: boolean;

  constructor(
    toolCallId: string,
    content: string,
    isError = false,
  ) {
    this.toolCallId = toolCallId;
    this.content = content;
    this.isError = isError;
  }

  toMessage(): Record<string, string> {
    return {
      role: "tool",
      tool_call_id: this.toolCallId,
      content: this.content,
    };
  }
}

export class ToolExecutor {
  tools: Tool[];
  toolMap: Map<string, Tool>;

  constructor() {
    this.tools = getBuiltinTools();
    this.toolMap = new Map(this.tools.map((tool) => [tool.name, tool]));
  }

  parseToolCalls(assistantMessage: Record<string, any>): ToolCall[] {
    const openaiCalls = assistantMessage.tool_calls;
    if (!Array.isArray(openaiCalls)) return [];
    return openaiCalls.map((item) => {
      const fn = item.function ?? {};
      let args = fn.arguments ?? {};
      if (typeof args === "string") {
        try {
          args = JSON.parse(args);
        } catch {
          args = {};
        }
      }
      return { id: item.id ?? "", name: fn.name ?? "", arguments: typeof args === "object" ? args : {} };
    });
  }

  async execute(toolCall: ToolCall): Promise<ToolResult> {
    const tool = this.toolMap.get(toolCall.name);
    if (!tool) return new ToolResult(toolCall.id, `Tool '${toolCall.name}' not found`, true);

    try {
      const rawResult = await tool.execute(toolCall.arguments);
      return new ToolResult(toolCall.id, stringifyResult(rawResult));
    } catch (error) {
      return new ToolResult(toolCall.id, `Error: ${error instanceof Error ? error.message : String(error)}`, true);
    }
  }

  async executeAll(toolCalls: ToolCall[]): Promise<ToolResult[]> {
    const results: ToolResult[] = [];
    for (const toolCall of toolCalls) results.push(await this.execute(toolCall));
    return results;
  }
}

function stringifyResult(value: unknown): string {
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}
