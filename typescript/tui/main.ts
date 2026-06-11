import { callLlm } from "../core/llm.ts";
import { getTools, ToolExecutor } from "../tools/index.ts";
import { showMissingOpenAiEnv, TuiApp } from "./app.ts";

const SYSTEM_PROMPT =
  "你是一个会调用工具的助手。" +
  "当问题涉及最新信息、模型版本、产品发布时间或事实核验时，优先先调用 search 工具，再基于搜索结果回答。" +
  "若问题是本地文件/代码相关，优先使用 read/grep/find/ls 等本地工具。";

async function runAgent(messages: Record<string, any>[], onMessage: (role: string, content: string) => void): Promise<void> {
  const executor = new ToolExecutor();
  const tools = getTools().map((tool) => tool.toLlmFormat());

  while (true) {
    const assistantMessage = await callLlm(messages, tools, SYSTEM_PROMPT);
    messages.push(assistantMessage);
    if (assistantMessage.content) onMessage("assistant", assistantMessage.content);

    if (!assistantMessage.tool_calls) return;

    const toolCalls = executor.parseToolCalls(assistantMessage);
    const results = await executor.executeAll(toolCalls);
    for (let i = 0; i < toolCalls.length; i += 1) {
      onMessage("tool", `${toolCalls[i].name}(${JSON.stringify(toolCalls[i].arguments)})\n${results[i].content}`);
      messages.push(results[i].toMessage());
    }
  }
}

export function startTui(): void {
  const messages: Record<string, any>[] = [];
  const app = new TuiApp("Learn OpenClaw TypeScript TUI", ["Enter 发送；输入 quit/exit/q 或 Ctrl+C 退出。"]);

  app.setSubmitHandler(async (text, ui) => {
    messages.push({ role: "user", content: text });
    ui.addMessage("user", text);
    await runAgent(messages, (role, content) => ui.addMessage(role, content));
  });

  app.start();
}

if (!process.env.OPENAI_API_KEY || !process.env.OPENAI_BASE_URL) {
  showMissingOpenAiEnv("Learn OpenClaw TypeScript TUI");
} else {
  startTui();
}
