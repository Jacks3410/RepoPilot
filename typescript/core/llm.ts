import OpenAI from "openai";

export type Message = Record<string, any>;

function client(): OpenAI {
  return new OpenAI({
    apiKey: process.env.OPENAI_API_KEY,
    baseURL: process.env.OPENAI_BASE_URL,
  });
}

export async function callLlmSimple(prompt: string): Promise<string> {
  const response = await client().chat.completions.create({
    model: process.env.OPENAI_MODEL_ID ?? "kimi-k2.5",
    messages: [{ role: "user", content: prompt }],
  });
  return response.choices[0]?.message.content ?? "";
}

export async function callLlm(
  messages: Message[],
  tools?: Message[],
  systemPrompt?: string,
): Promise<Message> {
  const msgs = systemPrompt ? [{ role: "system", content: systemPrompt }, ...messages] : [...messages];

  const response = await client().chat.completions.create({
    model: process.env.OPENAI_MODEL_ID ?? "kimi-k2.5",
    messages: msgs as any,
    ...(tools?.length ? { tools: tools as any, tool_choice: "auto" as const } : {}),
  });

  const message = response.choices[0]?.message;
  const result: Message = {
    role: "assistant",
    content: message?.content ?? "",
    usage: {
      total_tokens: response.usage?.total_tokens ?? 0,
      prompt_tokens: response.usage?.prompt_tokens ?? 0,
      completion_tokens: response.usage?.completion_tokens ?? 0,
    },
  };

  const reasoningContent = (message as any)?.reasoning_content;
  if (reasoningContent) result.reasoning_content = reasoningContent;
  if (message?.tool_calls) result.tool_calls = message.tool_calls.map((toolCall) => toolCall);

  return result;
}
