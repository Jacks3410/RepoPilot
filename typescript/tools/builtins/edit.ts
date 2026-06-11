import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

export function editFile(args: { path: string; old_text: string; new_text: string; cwd?: string }): Record<string, any> {
  const filePath = resolve(args.cwd ?? ".", args.path);
  if (!existsSync(filePath)) throw new Error(`File not found: ${args.path}`);

  const content = readFileSync(filePath, "utf-8");
  if (!content.includes(args.old_text)) {
    throw new Error(`Could not find the exact text in ${args.path}. The old text must match exactly.`);
  }

  const occurrences = content.split(args.old_text).length - 1;
  if (occurrences > 1) throw new Error(`Found ${occurrences} occurrences of the text in ${args.path}. The text must be unique.`);

  const newContent = content.replace(args.old_text, args.new_text);
  if (content === newContent) throw new Error(`No changes made to ${args.path}.`);
  writeFileSync(filePath, newContent, "utf-8");

  const oldLines = content.split("\n");
  const newLines = newContent.split("\n");
  let firstChangedLine: number | null = null;
  for (let i = 0; i < Math.min(oldLines.length, newLines.length); i += 1) {
    if (oldLines[i] !== newLines[i]) {
      firstChangedLine = i + 1;
      break;
    }
  }

  return {
    message: `Successfully replaced text in ${args.path}`,
    first_changed_line: firstChangedLine,
  };
}
