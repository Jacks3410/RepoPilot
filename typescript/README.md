# Learn OpenClaw TypeScript

这是当前 Python 教学项目的一比一 TypeScript 版本。目录结构保留 `core / tools / examples` 的学习顺序，所有交互示例统一使用 `pi-tui` 做终端输入输出。

## 安装

```bash
cd typescript
npm install
```

当前 TUI 依赖 pi-mono 的 TUI 包：

```text
@earendil-works/pi-tui
```

## 环境变量

```bash
export OPENAI_API_KEY=your-api-key
export OPENAI_BASE_URL=your-base-url
export OPENAI_MODEL_ID=kimi-k2.5
```

Windows PowerShell:

```powershell
$env:OPENAI_API_KEY="your-api-key"
$env:OPENAI_BASE_URL="your-base-url"
$env:OPENAI_MODEL_ID="kimi-k2.5"
```

## 运行

以下脚本都会打开 TUI 界面，输入内容后按 Enter 发送，输入 `quit` / `exit` / `q` 或按 Ctrl+C 退出。

```bash
npm run chatbot
npm run workflow
npm run chatbot:tools
npm run chatbot:memory
npm run agent:goal
npm run tui
```

## 一比一对应关系

```text
Python                         TypeScript
core/node.py                   typescript/core/node.ts
core/llm.py                    typescript/core/llm.ts
core/memory.py                 typescript/core/memory.ts
tools/builtins/*.py            typescript/tools/builtins/*.ts
tools/executor.py              typescript/tools/executor.ts
tools/skill_loader.py          typescript/tools/skill-loader.ts
tools/mcp/*.py                 typescript/tools/mcp/*.ts
examples/chatbot/main.py       typescript/examples/chatbot/main.ts
examples/workflow/main.py      typescript/examples/workflow/main.ts
examples/chatbot_with_tools    typescript/examples/chatbot-with-tools
examples/chatbot_with_memory   typescript/examples/chatbot-with-memory
examples/agent_with_goal       typescript/examples/agent-with-goal
```

TypeScript 不支持 Python 的 `node - "action" >> next_node` 运算符写法，所以这里使用 `node.connect("action", nextNode)` 表达同一个路由关系。

## pi-tui

`typescript/tui/app.ts` 封装了 `@earendil-works/pi-tui` 的 `TUI / ProcessTerminal / Editor / Markdown / Text` 组件。`typescript/examples/*/main.ts` 和 `typescript/tui/main.ts` 都复用这个封装，避免每个示例重复写输入框、消息渲染和退出逻辑。

## 注意

- TypeScript 版本放在独立目录，不会修改 Python 教学代码。
- `search` 工具保留同名接口，TypeScript 版使用 DuckDuckGo Instant Answer HTTP API，避免额外 Python 依赖。
- MCP 示例依赖 `@modelcontextprotocol/sdk`，与 Python 版 `FastMCP` 处在同一教学层级。
