/**
 * Workflow 示例 - 搜索工作流
 *
 * 工作流: Query → Search → Summarize
 */

import { callLlmSimple } from "../../core/llm.ts";
import { Flow, Node, type FlowResult } from "../../core/node.ts";
import { showMissingOpenAiEnv, TuiApp } from "../../tui/app.ts";
import { search } from "../../tools/builtins/search.ts";

/** 查询节点 - 接收用户输入 */
class QueryNode extends Node {
  exec(payload: unknown): FlowResult {
    return ["search", String(payload)];
  }
}

/** 搜索节点 - 调用搜索工具 */
class SearchNode extends Node {
  async exec(payload: unknown): Promise<FlowResult> {
    const results = await search({ query: String(payload), max_results: 3 });
    return ["summarize", { query: String(payload), results }];
  }
}

/** 总结节点 - 调用 LLM 总结搜索结果 */
class SummarizeNode extends Node {
  async exec(payload: unknown): Promise<FlowResult> {
    const data = payload as { query: string; results: unknown[] };
    const prompt = `请基于以下搜索结果回答问题：${data.query}\n\n${JSON.stringify(data.results, null, 2)}`;
    const summary = await callLlmSimple(prompt);
    return ["default", summary];
  }
}

export function main(): void {
  // 构建工作流
  const query = new QueryNode();
  const searchNode = new SearchNode();
  const summarize = new SummarizeNode();
  query.connect("search", searchNode).connect("summarize", summarize);

  // 创建 TUI 应用
  const app = new TuiApp("🔍 Workflow", [
    "工作流: 输入问题 → 搜索 → 总结",
    "输入 quit/exit/q 或 Ctrl+C 退出",
  ]);

  // 设置提交处理
  app.setSubmitHandler(async (userInput) => {
    app.addMessage("user", userInput);
    const [, result] = await new Flow(query).run(userInput);
    app.addMessage("assistant", String(result ?? ""));
  });

  app.start();
}

// 检查环境变量并启动
if (!process.env.OPENAI_API_KEY || !process.env.OPENAI_BASE_URL) {
  showMissingOpenAiEnv("🔍 Workflow");
} else {
  main();
}
