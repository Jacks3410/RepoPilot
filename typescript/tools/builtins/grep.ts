import { existsSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { readdirSync } from "node:fs";

const DEFAULT_LIMIT = 100;
const DEFAULT_MAX_BYTES = 30 * 1024;
const GREP_MAX_LINE_LENGTH = 1000;

function walkFiles(path: string): string[] {
  if (statSync(path).isFile()) return [path];
  const result: string[] = [];
  for (const entry of readdirSync(path)) {
    const fullPath = join(path, entry);
    const stat = statSync(fullPath);
    if (stat.isDirectory()) result.push(...walkFiles(fullPath));
    if (stat.isFile()) result.push(fullPath);
  }
  return result;
}

function matchesGlob(file: string, glob?: string): boolean {
  if (!glob) return true;
  if (glob.startsWith("*.")) return file.endsWith(glob.slice(1));
  return file.includes(glob.replaceAll("*", ""));
}

export function grep(args: {
  pattern: string;
  path?: string;
  glob?: string;
  ignore_case?: boolean;
  literal?: boolean;
  context?: number;
  limit?: number;
  cwd?: string;
}): string {
  const searchPath = resolve(args.cwd ?? ".", args.path ?? ".");
  if (!existsSync(searchPath)) throw new Error(`Path not found: ${searchPath}`);

  const flags = args.ignore_case ? "i" : "";
  const source = args.literal ? args.pattern.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") : args.pattern;
  const regex = new RegExp(source, flags);
  const limit = args.limit ?? DEFAULT_LIMIT;
  const context = args.context ?? 0;
  const matches: string[] = [];

  for (const file of walkFiles(searchPath).filter((item) => matchesGlob(item, args.glob))) {
    if (matches.length >= limit) break;
    let lines: string[];
    try {
      lines = readFileSync(file, "utf-8").split("\n");
    } catch {
      continue;
    }

    for (let i = 0; i < lines.length && matches.length < limit; i += 1) {
      if (!regex.test(lines[i])) continue;
      const relPath = statSync(searchPath).isDirectory() ? relative(searchPath, file) : file.split(/[\\/]/).pop();
      if (context > 0) {
        for (let j = Math.max(0, i - context); j <= Math.min(lines.length - 1, i + context); j += 1) {
          const prefix = j === i ? `${relPath}:${j + 1}:` : `${relPath}-${j + 1}-`;
          matches.push(`${prefix} ${lines[j]}`);
        }
      } else {
        matches.push(`${relPath}:${i + 1}: ${lines[i]}`);
      }
    }
  }

  if (matches.length === 0) return "No matches found";
  let output = matches.map((line) => (line.length > GREP_MAX_LINE_LENGTH ? `${line.slice(0, GREP_MAX_LINE_LENGTH)}...` : line)).join("\n");
  if (Buffer.byteLength(output, "utf-8") > DEFAULT_MAX_BYTES) {
    output = Buffer.from(output, "utf-8").subarray(0, DEFAULT_MAX_BYTES).toString("utf-8");
    output += `\n\n[${DEFAULT_MAX_BYTES / 1024}KB limit reached]`;
  }
  if (matches.length >= limit) output += `\n\n[${limit} matches limit reached]`;
  return output;
}
