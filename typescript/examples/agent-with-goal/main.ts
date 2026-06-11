import { callLlm } from "../../core/llm.ts";
import { Flow, Node, shared, type FlowResult } from "../../core/node.ts";
import { showMissingOpenAiEnv, TuiApp } from "../../tui/app.ts";
import { getTools, Tool, ToolExecutor } from "../../tools/index.ts";

const SYSTEM_PROMPT =
  "你是一个会调用工具的助手。" +
  "当问题涉及最新信息、模型版本、产品发布时间或事实核验时，优先先调用 search 工具，再基于搜索结果回答。" +
  "若问题是本地文件/代码相关，优先使用 read/grep/find/ls 等本地工具。" +
  "如果一轮回复中既需要向用户展示文字又需要继续调用工具，可以同时返回 content 和 tool_calls。";

class GoalState {
  text: string | null = null;
  active = false;
}

function goalMessage(goal: GoalState): Record<string, string> {
  return {
    role: "user",
    content:
      "Complete this goal fully:\n\n" +
      `${goal.text}\n\n` +
      "Treat the goal text above as the whole task. Do not infer extra file, code, " +
      "or project work unless the goal explicitly asks for it. Do not stop at only " +
      "a plan, partial progress, or suggested next steps. Use tools only when the " +
      "goal explicitly requires them. If this is a simple chat goal, reply directly. " +
      "When the goal is fully complete and verified, call goal_complete.",
  };
}

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

function makeGoalCompleteTool(goal: GoalState): Tool {
  return new Tool("goal_complete", "Mark the active goal as complete.", {
    type: "object",
    properties: {},
  }, () => {
    if (!goal.active) return "No active goal";
    goal.text = null;
    goal.active = false;
    return "Goal complete";
  });
}

async function runGoal(flow: Flow, goal: GoalState): Promise<void> {
  while (goal.active) {
    (shared.messages as Record<string, any>[]).push(goalMessage(goal));
    await flow.run();
  }
}

export function runChat(): void {
  const goal = new GoalState();
  const executor = new ToolExecutor();
  const goalTool = makeGoalCompleteTool(goal);
  executor.tools.push(goalTool);
  executor.toolMap.set(goalTool.name, goalTool);

  shared.messages = [];
  shared.goal = goal;
  shared.tools = [...getTools().map((tool) => tool.toLlmFormat()), goalTool.toLlmFormat()];
  shared.toolExecutor = executor;
  const app = new TuiApp("🤖 Agent with Goal", [
    "一个会调用工具且支持目标驱动的助手。",
    "可用工具: read, write, edit, bash, grep, find, ls, search",
    "Goal 命令: /goal <goal>, /goal status, /goal clear",
    "输入 quit/exit/q 或 Ctrl+C 退出。",
  ]);
  shared.app = app;

  const chat = new ChatNode();
  const toolCall = new ToolCallNode();
  chat.connect("tool_call", toolCall);
  toolCall.connect("chat", chat);
  const flow = new Flow(chat);

  app.setSubmitHandler(async (userInput, ui) => {
    ui.addMessage("user", userInput);
    if (userInput.startsWith("/goal")) {
      const command = userInput.replace(/^\/goal/, "").trim();
      if (!command || command === "status") {
        ui.addMessage("system", goal.text ? `🎯 Goal: ${goal.text}\nActive: ${goal.active}` : "🎯 No active goal. Use /goal <goal> to start one.");
        return;
      }
      if (command === "clear") {
        goal.text = null;
        goal.active = false;
        ui.addMessage("system", "🎯 Goal cleared.");
        return;
      }
      goal.text = command;
      goal.active = true;
      ui.addMessage("system", `🎯 Goal started: ${goal.text}`);
      await runGoal(flow, goal);
      return;
    }

    (shared.messages as Record<string, any>[]).push({ role: "user", content: userInput });
    await flow.run();
  });

  app.start();
}

if (!process.env.OPENAI_API_KEY || !process.env.OPENAI_BASE_URL) {
  showMissingOpenAiEnv("🤖 Agent with Goal");
} else {
  runChat();
}
