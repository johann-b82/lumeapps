import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSlug from "rehype-slug";
import rehypeHighlight from "rehype-highlight";
import { Check, Copy, Link } from "lucide-react";
import { useRef, useState, type ComponentPropsWithoutRef, type ReactNode } from "react";

interface Props {
  content: string;
}

type HeadingProps = ComponentPropsWithoutRef<"h2"> & { node?: unknown };

function HeadingWithAnchor({ level, id, children, node: _node, ...props }: HeadingProps & { level: number }) {
  const Tag = `h${level}` as "h2" | "h3";
  return (
    <Tag id={id} className="group flex items-center gap-1" {...props}>
      {children}
      {id && (
        <a
          href={`#${id}`}
          aria-label={`Link to section: ${typeof children === "string" ? children : ""}`}
          className="opacity-0 group-hover:opacity-100 transition-opacity text-primary"
        >
          <Link className="h-4 w-4" />
        </a>
      )}
    </Tag>
  );
}

function CodeBlock({ children, ...props }: ComponentPropsWithoutRef<"pre"> & { node?: unknown }) {
  const ref = useRef<HTMLPreElement>(null);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const text = ref.current?.innerText ?? "";
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard blocked (insecure context, denied) — leave the button idle
    }
  };

  // `node` from react-markdown isn't a valid <pre> prop — strip it.
  const { node: _node, ...rest } = props as { node?: unknown };

  return (
    <div className="group relative my-4 overflow-hidden rounded-md bg-muted not-prose">
      <pre
        ref={ref}
        {...rest}
        className="overflow-x-auto bg-transparent px-4 py-3 text-sm leading-relaxed"
      >
        {children as ReactNode}
      </pre>
      <button
        type="button"
        onClick={handleCopy}
        aria-label={copied ? "Copied" : "Copy code"}
        className="absolute right-2 top-2 inline-flex h-7 w-7 items-center justify-center rounded-md border border-border bg-background/80 text-muted-foreground opacity-0 transition-opacity hover:text-foreground group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}

export function MarkdownRenderer({ content }: Props) {
  return (
    <div className="prose dark:prose-invert max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSlug, [rehypeHighlight, { detect: true }]]}
        components={{
          h2: ({ node, ...props }) => <HeadingWithAnchor level={2} {...props} />,
          h3: ({ node, ...props }) => <HeadingWithAnchor level={3} {...props} />,
          pre: CodeBlock,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
