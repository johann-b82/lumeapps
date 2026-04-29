export interface HtmlPlayerProps {
  html: string | null;
}

export function HtmlPlayer({ html }: HtmlPlayerProps) {
  if (!html) return null;
  return (
    <iframe
      srcDoc={html}
      sandbox="allow-scripts"
      className="w-full h-full border-0"
      title="HTML content"
    />
  );
}
