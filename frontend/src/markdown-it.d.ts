declare module 'markdown-it' {
  export default class MarkdownIt {
    constructor(options?: any);
    render(content: string): string;
  }
} 