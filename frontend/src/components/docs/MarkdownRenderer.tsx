import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSlug from "rehype-slug";
import rehypeHighlight from "rehype-highlight";
import { Link } from "lucide-react";
import type { ComponentPropsWithoutRef } from "react";

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

export function MarkdownRenderer({ content }: Props) {
  return (
    <div className="prose dark:prose-invert max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSlug, [rehypeHighlight, { detect: true }]]}
        components={{
          h2: ({ node, ...props }) => <HeadingWithAnchor level={2} {...props} />,
          h3: ({ node, ...props }) => <HeadingWithAnchor level={3} {...props} />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
