import { bash } from "./bash.ts";
import { editFile } from "./edit.ts";
import { find } from "./find.ts";
import { grep } from "./grep.ts";
import { ls } from "./ls.ts";
import { readFile } from "./read.ts";
import { search } from "./search.ts";
import { Tool } from "./tool-def.ts";
import { writeFile } from "./write.ts";

export { bash, editFile, find, grep, ls, readFile, search, Tool, writeFile };

export function getBuiltinTools(): Tool[] {
  return [
    new Tool("read", "Read file contents. Use offset/limit for large files.", {
      type: "object",
      properties: {
        path: { type: "string", description: "File path" },
        offset: { type: "integer", description: "Start line (1-indexed)" },
        limit: { type: "integer", description: "Max lines to read" },
      },
      required: ["path"],
    }, readFile),
    new Tool("write", "Write content to a file. Creates parent directories automatically.", {
      type: "object",
      properties: {
        path: { type: "string", description: "File path" },
        content: { type: "string", description: "Content to write" },
      },
      required: ["path", "content"],
    }, writeFile),
    new Tool("edit", "Edit file by replacing exact text. old_text must match exactly.", {
      type: "object",
      properties: {
        path: { type: "string", description: "File path" },
        old_text: { type: "string", description: "Exact text to find" },
        new_text: { type: "string", description: "Replacement text" },
      },
      required: ["path", "old_text", "new_text"],
    }, editFile),
    new Tool("bash", "Execute bash command. Output truncated to 2000 lines or 30KB.", {
      type: "object",
      properties: {
        command: { type: "string", description: "Command to execute" },
        timeout: { type: "integer", description: "Timeout in seconds" },
      },
      required: ["command"],
    }, bash),
    new Tool("grep", "Search file contents for a pattern. Returns matching lines.", {
      type: "object",
      properties: {
        pattern: { type: "string", description: "Search pattern (regex)" },
        path: { type: "string", description: "Directory or file to search" },
        glob: { type: "string", description: "File pattern e.g. '*.py'" },
      },
      required: ["pattern"],
    }, grep),
    new Tool("find", "Find files by glob pattern. Returns matching file paths.", {
      type: "object",
      properties: {
        pattern: { type: "string", description: "Glob pattern e.g. '*.py'" },
        path: { type: "string", description: "Directory to search" },
      },
      required: ["pattern"],
    }, find),
    new Tool("ls", "List directory contents. Returns entries with '/' suffix for directories.", {
      type: "object",
      properties: {
        path: { type: "string", description: "Directory path" },
      },
    }, ls),
    new Tool("search", "Search the web for up-to-date information and return relevant results.", {
      type: "object",
      properties: {
        query: { type: "string", description: "Search query" },
        max_results: { type: "integer", description: "Maximum number of results" },
      },
      required: ["query"],
    }, search),
  ];
}
