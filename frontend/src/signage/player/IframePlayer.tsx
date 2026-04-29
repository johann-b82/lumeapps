export interface IframePlayerProps {
  uri: string | null;
}

export function IframePlayer({ uri }: IframePlayerProps) {
  if (!uri) return null;
  return (
    <iframe
      src={uri}
      sandbox="allow-scripts allow-same-origin"
      className="w-full h-full border-0"
      title="External content"
    />
  );
}
