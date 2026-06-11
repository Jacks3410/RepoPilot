import { callLlm } from "../../core/llm.ts";
import { Flow, Node, shared, type FlowResult } from "../../core/node.ts";
import { showMissingOpenAiEnv, TuiApp } from "../../tui/app.ts";

const SYSTEM_PROMPT = "你是一个友好的对话助手，请回答用户的问题。";

class ChatNode extends Node {
  async exec(): Promise<FlowResult> {
    const messages = shared.messages as Record<string, any>[];
    const assistantMessage = await callLlm(messages, undefined, SYSTEM_PROMPT);
    messages.push(assistantMessage);
    return ["output", assistantMessage];
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
  shared.messages = [];
  const app = new TuiApp("🤖 Simple Chatbot", [
    "一个简单的对话助手，可以回答您的问题。",
    "输入 quit/exit/q 或 Ctrl+C 退出。",
  ]);
  shared.app = app;

  const chat = new ChatNode();
  const outputNode = new OutputNode();
  chat.connect("output", outputNode);

  app.setSubmitHandler(async (userInput) => {
    app.addMessage("user", userInput);
    (shared.messages as Record<string, any>[]).push({ role: "user", content: userInput });
    await new Flow(chat).run();
  });

  app.start();
}

if (!process.env.OPENAI_API_KEY || !process.env.OPENAI_BASE_URL) {
  showMissingOpenAiEnv("🤖 Simple Chatbot");
} else {
  runChat();
}
