export type ToolFn = (args: any) => any | Promise<any>;

export class Tool {
  name: string;
  description: string;
  parameters: Record<string, any>;
  fn: ToolFn;

  constructor(
    name: string,
    description: string,
    parameters: Record<string, any>,
    fn: ToolFn,
  ) {
    this.name = name;
    this.description = description;
    this.parameters = parameters;
    this.fn = fn;
  }

  toLlmFormat(): Record<string, any> {
    return {
      type: "function",
      function: {
        name: this.name,
        description: this.description,
        parameters: this.parameters,
      },
    };
  }

  execute(args: Record<string, any>): any | Promise<any> {
    return this.fn(args);
  }
}
