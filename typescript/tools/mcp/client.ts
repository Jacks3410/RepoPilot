import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

export class MCPClient {
  client?: Client;
  transport?: StdioClientTransport;
  tools: Record<string, any>[] = [];

  async connectStdio(command: string, args: string[] = []): Promise<void> {
    this.client = new Client({
      name: "learn-openclaw-client",
      version: "0.1.0",
    });
    this.transport = new StdioClientTransport({ command, args });
    await this.client.connect(this.transport);
    const toolsResult = await this.client.listTools();
    this.tools = toolsResult.tools as Record<string, any>[];
  }

  async listTools(): Promise<Record<string, any>[]> {
    if (!this.client) throw new Error("Not connected to server");
    const toolsResult = await this.client.listTools();
    return toolsResult.tools as Record<string, any>[];
  }

  async callTool(name: string, arguments_: Record<string, any>): Promise<unknown> {
    if (!this.client) throw new Error("Not connected to server");
    return this.client.callTool({ name, arguments: arguments_ });
  }

  async close(): Promise<void> {
    await this.transport?.close();
    this.client = undefined;
    this.transport = undefined;
  }
}

async function main(): Promise<void> {
  const client = new MCPClient();
  await client.connectStdio("node", ["--loader", "tsx/esm", "typescript/tools/mcp/server.ts"]);
  const tools = await client.listTools();
  console.log("Available tools:", tools.map((tool) => tool.name));
  const result = await client.callTool("add", { a: 3, b: 4 });
  console.log("3 + 4 =", result);
  await client.close();
}

if (import.meta.url === `file://${process.argv[1]}`) {
  await main();
}
