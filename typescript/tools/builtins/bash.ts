import { exec } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const DEFAULT_MAX_BYTES = 30 * 1024;
const DEFAULT_MAX_LINES = 2000;

export function bash(args: { command: string; timeout?: number; cwd?: string }): Promise<Record<string, any>> {
  const workDir = resolve(args.cwd ?? ".");
  if (!existsSync(workDir)) throw new Error(`Working directory does not exist: ${workDir}`);

  return new Promise((resolvePromise) => {
    exec(args.command, { cwd: workDir, timeout: (args.timeout ?? 0) * 1000 || undefined }, (error, stdout, stderr) => {
      let output = stdout;
      if (stderr) output += output ? `\n${stderr}` : stderr;

      let lines = output.split("\n");
      if (lines.length > DEFAULT_MAX_LINES) {
        lines = lines.slice(-DEFAULT_MAX_LINES);
        output = `[Output truncated to last ${DEFAULT_MAX_LINES} lines]\n${lines.join("\n")}`;
      }

      if (Buffer.byteLength(output, "utf-8") > DEFAULT_MAX_BYTES) {
        output = Buffer.from(output, "utf-8").subarray(-DEFAULT_MAX_BYTES).toString("utf-8");
        output = `[Output truncated to last ${DEFAULT_MAX_BYTES / 1024}KB]\n${output}`;
      }

      resolvePromise({
        stdout: output,
        stderr: stderr || "",
        exit_code: typeof (error as any)?.code === "number" ? (error as any).code : 0,
      });
    });
  });
}
