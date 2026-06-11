import { callLlm } from "../../core/llm.ts";
import { Flow, Node, shared, type FlowResult } from "../../core/node.ts";
import { showMissingOpenAiEnv, TuiApp } from "../../tui/app.ts";
import { getTools, ToolExecutor } from "../../tools/index.ts";

const SYSTEM_PROMPT =
  "你是一个会调用工具的助手。" +
  "当问题涉及最新信息、模型版本、产品发布时间或事实核验时，优先先调用 search 工具，再基于搜索结果回答。" +
  "若问题是本地文件/代码相关，优先使用 read/grep/find/ls 等本地工具。" +
  "如果一轮回复中既需要向用户展示文字又需要继续调用工具，可以同时返回 content 和 tool_calls。";

class ChatNode extends Node {
  async exec(): Promise<FlowResult> {
    const app = shared.app as TuiApp;
    const messages = shared.messages as Record<string, any>[];
    const assistantMessage = await callLlm(messages, shared.tools as Record<string, any>[], SYSTEM_PROMPT);
    messages.push(assistantMessage);

    if (assistantMessage.content) app.addMessage("assistant", assistantMessage.content);
    if (assistantMessage.tool_calls) return ["tool_call", assistantMessage];
    return ["done", assistantMessage];
  }
}

class ToolCallNode extends Node {
  async exec(payload: unknown): Promise<FlowResult> {
    const app = shared.app as TuiApp;
    const messages = shared.messages as Record<string, any>[];
    const executor = shared.toolExecutor as ToolExecutor;
    const toolCalls = executor.parseToolCalls(payload as Record<string, any>);
    const results = await executor.executeAll(toolCalls);

    for (let i = 0; i < toolCalls.length; i += 1) {
      app.addMessage("tool", `${toolCalls[i].name}(${JSON.stringify(toolCalls[i].arguments)})\n${results[i].content}`);
      messages.push(results[i].toMessage());
    }
    return ["chat", undefined];
  }
}

export function runChat(): void {
  shared.messages = [];
  shared.tools = getTools().map((tool) => tool.toLlmFormat());
  shared.toolExecutor = new ToolExecutor();
  const app = new TuiApp("🤖 Chatbot with Tools", [
    "一个会调用工具的助手，可以搜索网页、读写文件等。",
    "可用工具: read, write, edit, bash, grep, find, ls, search",
    "输入 quit/exit/q 或 Ctrl+C 退出。",
  ]);
  shared.app = app;

  const chat = new ChatNode();
  const toolCall = new ToolCallNode();
  chat.connect("tool_call", toolCall);
  toolCall.connect("chat", chat);

  app.setSubmitHandler(async (userInput) => {
    app.addMessage("user", userInput);
    (shared.messages as Record<string, any>[]).push({ role: "user", content: userInput });
    await new Flow(chat).run();
  });

  app.start();
}

if (!process.env.OPENAI_API_KEY || !process.env.OPENAI_BASE_URL) {
  showMissingOpenAiEnv("🤖 Chatbot with Tools");
} else {
  runChat();
}
