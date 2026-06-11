import { existsSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const DEFAULT_LIMIT = 1000;
const DEFAULT_MAX_BYTES = 30 * 1024;

function walkFiles(path: string): string[] {
  const result: string[] = [];
  for (const entry of readdirSync(path)) {
    const fullPath = join(path, entry);
    const stat = statSync(fullPath);
    if (stat.isDirectory()) result.push(...walkFiles(fullPath));
    if (stat.isFile()) result.push(fullPath);
  }
  return result;
}

function globMatch(file: string, pattern: string): boolean {
  if (pattern === "*") return true;
  if (pattern.startsWith("**/")) return file.endsWith(pattern.slice(3));
  if (pattern.startsWith("*.")) return file.endsWith(pattern.slice(1));
  return file.includes(pattern.replaceAll("*", ""));
}

export function find(args: { pattern: string; path?: string; limit?: number; cwd?: string }): string {
  const searchPath = resolve(args.cwd ?? ".", args.path ?? ".");
  if (!existsSync(searchPath)) throw new Error(`Path not found: ${searchPath}`);
  if (!statSync(searchPath).isDirectory()) throw new Error(`Not a directory: ${searchPath}`);

  const limit = args.limit ?? DEFAULT_LIMIT;
  const results = walkFiles(searchPath)
    .filter((file) => globMatch(relative(searchPath, file), args.pattern))
    .slice(0, limit)
    .map((file) => relative(searchPath, file))
    .sort();

  if (results.length === 0) return "No files found matching pattern";

  let output = results.join("\n");
  if (Buffer.byteLength(output, "utf-8") > DEFAULT_MAX_BYTES) {
    output = Buffer.from(output, "utf-8").subarray(0, DEFAULT_MAX_BYTES).toString("utf-8");
    output += `\n\n[${DEFAULT_MAX_BYTES / 1024}KB limit reached]`;
  }
  if (results.length >= limit) output += `\n\n[${limit} results limit reached]`;
  return output;
}
