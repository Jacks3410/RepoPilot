import {
  Editor,
  Key,
  Markdown,
  ProcessTerminal,
  Spacer,
  Text,
  TUI,
  matchesKey,
  type EditorTheme,
  type MarkdownTheme,
  type SelectListTheme,
} from "@earendil-works/pi-tui";

const plain = (text: string) => text;

const selectListTheme: SelectListTheme = {
  selectedPrefix: plain,
  selectedText: plain,
  description: plain,
  scrollInfo: plain,
  noMatch: plain,
};

const editorTheme: EditorTheme = {
  borderColor: plain,
  selectList: selectListTheme,
};

const markdownTheme: MarkdownTheme = {
  heading: plain,
  link: plain,
  linkUrl: plain,
  code: plain,
  codeBlock: plain,
  codeBlockBorder: plain,
  quote: plain,
  quoteBorder: plain,
  hr: plain,
  listBullet: plain,
  bold: plain,
  italic: plain,
  strikethrough: plain,
  underline: plain,
};

export type SubmitHandler = (text: string, app: TuiApp) => Promise<void> | void;

export class TuiApp {
  tui: TUI;
  editor: Editor;
  status: Text;
  onSubmit?: SubmitHandler;

  constructor(title: string, hints: string[] = []) {
    this.tui = new TUI(new ProcessTerminal());
    this.editor = new Editor(this.tui, editorTheme);
    this.status = new Text("");

    this.tui.addChild(new Text(title));
    for (const hint of hints) this.tui.addChild(new Text(hint));
    this.tui.addChild(this.status);
    this.tui.addChild(new Spacer(1));
    this.tui.addChild(this.editor);
    this.tui.setFocus(this.editor);

    this.editor.onSubmit = (text: string) => {
      const value = text.trim();
      if (!value) return;
      if (["quit", "exit", "q"].includes(value.toLowerCase())) {
        this.stop();
        return;
      }
      this.editor.setText("");
      void this.runSubmit(value);
    };

    this.tui.addInputListener((data: string) => {
      if (matchesKey(data, Key.ctrl("c"))) this.stop();
      return undefined;
    });
  }

  start(): void {
    this.tui.start();
  }

  stop(): void {
    this.tui.stop();
    process.exit(0);
  }

  setSubmitHandler(handler: SubmitHandler): void {
    this.onSubmit = handler;
  }

  addMessage(role: string, content: string): void {
    const icon = role === "user" ? "👤" : role === "tool" ? "🔧" : role === "system" ? "⚙️" : "🤖";
    const prefix = role === "user" ? "User" : role === "tool" ? "Tool" : role === "system" ? "System" : "Assistant";

    this.tui.removeChild(this.editor);
    this.tui.addChild(new Markdown(`${icon} **${prefix}:**\n\n${content}`, 1, 0, markdownTheme));
    this.tui.addChild(new Spacer(1));
    this.tui.addChild(this.editor);
    this.tui.setFocus(this.editor);
    this.tui.requestRender();
  }

  setStatus(text: string): void {
    this.status.setText(text);
    this.tui.requestRender();
  }

  private async runSubmit(text: string): Promise<void> {
    if (!this.onSubmit) return;
    this.editor.disableSubmit = true;
    this.setStatus("Working...");
    try {
      await this.onSubmit(text, this);
    } catch (error) {
      this.addMessage("system", `Error: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      this.setStatus("");
      this.editor.disableSubmit = false;
      this.tui.setFocus(this.editor);
      this.tui.requestRender();
    }
  }
}

export function showMissingOpenAiEnv(title: string): void {
  const app = new TuiApp(title, ["Ctrl+C 退出。"]);
  app.addMessage("system", "⚠️ 提示：请先设置环境变量 OPENAI_API_KEY 和 OPENAI_BASE_URL\n\n" +
    "示例:\n" +
    "```bash\n" +
    "export OPENAI_API_KEY=your-api-key\n" +
    "export OPENAI_BASE_URL=https://api.openai.com/v1\n" +
    "```");
  app.start();
}
