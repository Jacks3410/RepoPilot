import { existsSync, mkdirSync, readFileSync, writeFileSync, appendFileSync } from "node:fs";
import { join } from "node:path";

import { callLlm, type Message } from "./llm.ts";

export const MEMORY_DIR = "./examples/chatbot-with-memory/chat_memory";
export const SESSION_FILE = join(MEMORY_DIR, "session.jsonl");
export const LONG_TERM_FILE = join(MEMORY_DIR, "MEMORY.md");
export const MAX_CONTEXT_LENGTH = 128_000;
export const COMPRESS_THRESHOLD = 0.9;
export const KEEP_MESSAGES_ON_COMPRESS = 4;
export const LONG_TERM_MEMORY_HEADER = "# 长期记忆：包括用户偏好、重要事件、运行环境等等\n\n";
export const MESSAGE_KEYS = new Set(["role", "content", "tool_calls", "tool_call_id", "reasoning_content"]);

export class Memory {
  messages: Message[] = [];

  constructor() {
    mkdirSync(MEMORY_DIR, { recursive: true });
    if (!existsSync(LONG_TERM_FILE)) writeFileSync(LONG_TERM_FILE, LONG_TERM_MEMORY_HEADER);

    if (existsSync(SESSION_FILE)) {
      for (const line of readFileSync(SESSION_FILE, "utf-8").split(/\r?\n/)) {
        if (!line.trim()) continue;
        try {
          this.messages.push(JSON.parse(line));
        } catch {}
      }
    }

    let needRewrite = false;
    for (let index = this.messages.length - 1; index >= 0; index -= 1) {
      const message = this.messages[index];
      if (message.role !== "assistant" || !message.tool_calls) continue;

      const tail = this.messages.slice(index + 1);
      if (tail.length > 0 && !tail.every((item) => item.role === "tool")) break;

      const start = index > 0 && this.messages[index - 1]?.role === "user" ? index - 1 : index;
      this.messages.splice(start);
      needRewrite = true;
      break;
    }

    if (needRewrite) this.writeAll();
  }

  async addMessage(message: Message): Promise<void> {
    const totalTokens = message.usage?.total_tokens ?? 0;
    const shouldCompress = totalTokens > 0 && !message.tool_calls;
    const cleanMessage = Object.fromEntries(Object.entries(message).filter(([key]) => MESSAGE_KEYS.has(key)));

    this.messages.push(cleanMessage);
    appendFileSync(SESSION_FILE, `${JSON.stringify(cleanMessage)}\n`, "utf-8");

    if (shouldCompress) await this.compress(totalTokens);
  }

  buildContext(systemPrompt = ""): Message[] {
    if (!systemPrompt) return [...this.messages];

    let longTermMemory = readFileSync(LONG_TERM_FILE, "utf-8").trim();
    if (longTermMemory === LONG_TERM_MEMORY_HEADER.trim()) longTermMemory = "";

    const systemMessage = { role: "system", content: systemPrompt };
    if (longTermMemory) systemMessage.content += `\n\n长期记忆：\n${longTermMemory}`;

    if (this.messages[0]?.role === "system") {
      systemMessage.content += `\n\n${this.messages[0].content}`;
      return [systemMessage, ...this.messages.slice(1)];
    }

    return [systemMessage, ...this.messages];
  }

  async compress(totalTokens: number): Promise<void> {
    if (totalTokens <= MAX_CONTEXT_LENGTH * COMPRESS_THRESHOLD) return;
    if (this.messages.length <= KEEP_MESSAGES_ON_COMPRESS) return;

    let splitIndex = Math.max(0, this.messages.length - KEEP_MESSAGES_ON_COMPRESS);
    while (splitIndex > 0 && this.messages[splitIndex]?.role === "tool") splitIndex -= 1;

    if (
      splitIndex > 0 &&
      this.messages[splitIndex]?.role === "assistant" &&
      this.messages[splitIndex]?.tool_calls &&
      this.messages[splitIndex - 1]?.role === "user"
    ) {
      splitIndex -= 1;
    }

    const oldMessages = this.messages.slice(0, splitIndex);
    const recentMessages = this.messages.slice(splitIndex);
    if (oldMessages.length === 0) return;

    let longTermMemory = readFileSync(LONG_TERM_FILE, "utf-8").trim();
    if (longTermMemory === LONG_TERM_MEMORY_HEADER.trim()) longTermMemory = "无";

    const response = await callLlm([
      ...oldMessages,
      {
        role: "user",
        content:
          `已有长期记忆：\n${longTermMemory}\n\n请压缩以上对话历史，并判断是否有值得长期记住的信息（用户偏好、关键事实、运行环境等等。注意排除已有的长期记忆）。\n` +
          "只返回 JSON，不要使用 Markdown 代码块。JSON 包含 summary(摘要总结) 和 memory_update(值得长期记忆的信息) 两个字符串字段。",
      },
    ]);

    let summary = response.content ?? "";
    let memoryUpdate = "";
    try {
      const result = JSON.parse(response.content ?? "");
      summary = result.summary ?? "";
      memoryUpdate = result.memory_update ?? "";
    } catch {}

    this.messages = [{ role: "system", content: `对话历史摘要：\n${summary}` }, ...recentMessages];
    this.writeAll();

    if (memoryUpdate) appendFileSync(LONG_TERM_FILE, `\n${memoryUpdate}`, "utf-8");
  }

  private writeAll(): void {
    writeFileSync(SESSION_FILE, this.messages.map((message) => JSON.stringify(message)).join("\n") + "\n", "utf-8");
  }
}
