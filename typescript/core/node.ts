export const shared: Record<string, unknown> = {};

export type FlowResult = [string, unknown];

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export abstract class Node {
  successors: Map<string, Node> = new Map();
  maxRetries: number;
  wait: number;

  constructor(maxRetries = 1, wait = 0) {
    this.maxRetries = maxRetries;
    this.wait = wait;
  }

  abstract exec(payload: unknown): Promise<FlowResult> | FlowResult;

  async runNode(payload: unknown): Promise<FlowResult> {
    for (let curRetry = 0; curRetry < this.maxRetries; curRetry += 1) {
      try {
        return await this.exec(payload);
      } catch (error) {
        if (curRetry === this.maxRetries - 1) throw error;
        if (this.wait > 0) await sleep(this.wait * 1000);
      }
    }
    throw new Error("Unexpected error in Node.runNode");
  }

  connect(action: string, node: Node): Node {
    this.successors.set(action || "default", node);
    return node;
  }
}

export class Flow {
  start?: Node;

  constructor(start?: Node) {
    this.start = start;
  }

  async run(payload: unknown = undefined): Promise<FlowResult> {
    let current = this.start;
    let lastAction = "default";

    while (current) {
      [lastAction, payload] = await current.runNode(payload);
      current = current.successors.get(lastAction);
    }

    return [lastAction, payload];
  }
}
