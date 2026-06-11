import { existsSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const DEFAULT_LIMIT = 500;
const DEFAULT_MAX_BYTES = 30 * 1024;

export function ls(args: { path?: string; limit?: number; cwd?: string } = {}): string {
  const dirPath = resolve(args.cwd ?? ".", args.path ?? ".");
  if (!existsSync(dirPath)) throw new Error(`Path not found: ${dirPath}`);
  if (!statSync(dirPath).isDirectory()) throw new Error(`Not a directory: ${dirPath}`);

  const effectiveLimit = args.limit ?? DEFAULT_LIMIT;
  const entries = readdirSync(dirPath).sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
  const shown = entries.slice(0, effectiveLimit).map((entry) => entry + (statSync(join(dirPath, entry)).isDirectory() ? "/" : ""));

  if (shown.length === 0) return "(empty directory)";

  let output = shown.join("\n");
  if (Buffer.byteLength(output, "utf-8") > DEFAULT_MAX_BYTES) {
    output = Buffer.from(output, "utf-8").subarray(0, DEFAULT_MAX_BYTES).toString("utf-8");
    output += `\n\n[${DEFAULT_MAX_BYTES / 1024}KB limit reached]`;
  }
  if (entries.length > effectiveLimit) output += `\n\n[${effectiveLimit} entries limit reached. Use limit=${effectiveLimit * 2} for more]`;
  return output;
}
