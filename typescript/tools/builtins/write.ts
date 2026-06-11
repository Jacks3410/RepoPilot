import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

export function writeFile(args: { path: string; content: string; cwd?: string }): string {
  const filePath = resolve(args.cwd ?? ".", args.path);
  mkdirSync(dirname(filePath), { recursive: true });
  writeFileSync(filePath, args.content, "utf-8");
  return `Successfully wrote ${Buffer.byteLength(args.content, "utf-8")} bytes to ${args.path}`;
}
