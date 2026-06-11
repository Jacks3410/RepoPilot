import { readFileSync } from "node:fs";
import YAML from "yaml";

export function load(path: string): [Record<string, any>, string] {
  const content = readFileSync(path, "utf-8");
  if (!content.startsWith("---")) return [{}, content];

  const parts = content.split("---", 3);
  if (parts.length < 3) return [{}, content];

  const metadata = YAML.parse(parts[1]) ?? {};
  const body = parts[2].trim();
  return [metadata, body];
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const testFile = process.argv[2] ?? "tools/skills/pdf/SKILL.md";
  const [metadata, body] = load(testFile);
  console.log(`Loading: ${testFile}`);
  console.log("=".repeat(50));
  console.log("METADATA:");
  for (const [key, value] of Object.entries(metadata)) {
    const display = typeof value === "string" && value.length > 60 ? `${value.slice(0, 60)}...` : value;
    console.log(`  ${key}: ${display}`);
  }
  console.log(`\nCONTENT (first 300 chars):\n${body.slice(0, 300)}...`);
}
