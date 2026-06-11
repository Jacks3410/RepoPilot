import { existsSync, readFileSync, statSync } from "node:fs";
import { resolve } from "node:path";

const DEFAULT_MAX_BYTES = 30 * 1024;

export function readFile(args: { path: string; offset?: number; limit?: number; cwd?: string }): string {
  const filePath = resolve(args.cwd ?? ".", args.path);
  if (!existsSync(filePath)) throw new Error(`File not found: ${args.path}`);
  if (!statSync(filePath).isFile()) throw new Error(`Not a file: ${args.path}`);

  const lines = readFileSync(filePath, "utf-8").split("\n");
  const totalLines = lines.length;
  const startLine = Math.max(0, (args.offset ?? 1) - 1);
  if (startLine >= totalLines) throw new Error(`Offset ${args.offset} is beyond end of file (${totalLines} lines total)`);

  const endLine = args.limit === undefined ? totalLines : Math.min(startLine + args.limit, totalLines);
  let result = lines.slice(startLine, endLine).join("\n");

  if (Buffer.byteLength(result, "utf-8") > DEFAULT_MAX_BYTES) {
    let truncated = Buffer.from(result, "utf-8").subarray(0, DEFAULT_MAX_BYTES).toString("utf-8");
    const lastNewline = truncated.lastIndexOf("\n");
    if (lastNewline > 0) truncated = truncated.slice(0, lastNewline);
    const shownEnd = startLine + truncated.split("\n").length;
    result = `${truncated}\n\n[Showing lines ${startLine + 1}-${shownEnd} of ${totalLines} (${DEFAULT_MAX_BYTES / 1024}KB limit). Use offset=${shownEnd + 1} to continue.]`;
  } else if (args.limit !== undefined && endLine < totalLines) {
    result += `\n\n[${totalLines - endLine} more lines in file. Use offset=${endLine + 1} to continue.]`;
  }

  return result;
}
