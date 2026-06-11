import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

import { search as searchImpl } from "../builtins/search.ts";

const server = new McpServer({
  name: "agent-tools",
  version: "0.1.0",
});

server.tool(
  "search",
  "使用 DuckDuckGo 搜索网页",
  {
    query: z.string(),
    max_results: z.number().optional(),
  },
  async ({ query, max_results }) => {
    const result = await searchImpl({ query, max_results });
    return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
  },
);

server.tool(
  "add",
  "Add two numbers",
  {
    a: z.number(),
    b: z.number(),
  },
  async ({ a, b }) => ({ content: [{ type: "text", text: String(a + b) }] }),
);

server.tool(
  "multiply",
  "Multiply two numbers",
  {
    a: z.number(),
    b: z.number(),
  },
  async ({ a, b }) => ({ content: [{ type: "text", text: String(a * b) }] }),
);

const transport = new StdioServerTransport();
await server.connect(transport);
