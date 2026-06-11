import { callLlm } from "../../core/llm.ts";
import { Memory } from "../../core/memory.ts";
import { Flow, Node, shared, type FlowResult } from "../../core/node.ts";
import { showMissingOpenAiEnv, TuiApp } from "../../tui/app.ts";
import { getTools, ToolExecutor } from "../../tools/index.ts";

const SYSTEM_PROMPT =
  "你是一个会调用工具的助手。" +
  "当问题涉及最新信息、模型版本、产品发布时间或事实核验时，优先先调用 search 工具，再基于搜索结果回答。" +
  "若问题是本地文件/代码相关，优先使用 read/grep/find/ls 等本地工具。";

class ChatNode extends Node {
  async exec(): Promise<FlowResult> {
    const memory = shared.memory as Memory;
    const messages = memory.buildContext(SYSTEM_PROMPT);
    const assistantMessage = await callLlm(messages, shared.tools as Record<string, any>[]);
    await memory.addMessage(assistantMessage);

    if (assistantMessage.tool_calls) return ["tool_call", assistantMessage];
    return ["output", assistantMessage];
  }
}

class ToolCallNode extends Node {
  async exec(payload: unknown): Promise<FlowResult> {
    const app = shared.app as TuiApp;
    const memory = shared.memory as Memory;
    const executor = shared.toolExecutor as ToolExecutor;
    const toolCalls = executor.parseToolCalls(payload as Record<string, any>);
    const results = await executor.executeAll(toolCalls);

    for (let i = 0; i < toolCalls.length; i += 1) {
      app.addMessage("tool", `${toolCalls[i].name}(${JSON.stringify(toolCalls[i].arguments)})\n${results[i].content}`);
      await memory.addMessage(results[i].toMessage());
    }
    return ["chat", undefined];
  }
}

class OutputNode extends Node {
  exec(payload: unknown): FlowResult {
    const app = shared.app as TuiApp;
    const response = payload as Record<string, any>;
    app.addMessage("assistant", response.content ?? "");
    return ["default", undefined];
  }
}

export function runChat(): void {
  shared.memory = new Memory();
  shared.tools = getTools().map((tool) => tool.toLlmFormat());
  shared.toolExecutor = new ToolExecutor();
  const app = new TuiApp("🤖 Chatbot with Memory", [
    "一个会调用工具且具有记忆功能的助手。",
    "可用工具: read, write, edit, bash, grep, find, ls, search",
    "记忆管理: 短期上下文 + 长期记忆 (自动压缩)",
    "输入 quit/exit/q 或 Ctrl+C 退出。",
  ]);
  shared.app = app;

  const chat = new ChatNode();
  const toolCall = new ToolCallNode();
  const outputNode = new OutputNode();
  chat.connect("tool_call", toolCall);
  toolCall.connect("chat", chat);
  chat.connect("output", outputNode);

  app.setSubmitHandler(async (userInput) => {
    app.addMessage("user", userInput);
    await (shared.memory as Memory).addMessage({ role: "user", content: userInput });
    await new Flow(chat).run();
  });

  app.start();
}

if (!process.env.OPENAI_API_KEY || !process.env.OPENAI_BASE_URL) {
  showMissingOpenAiEnv("🤖 Chatbot with Memory");
} else {
  runChat();
}
