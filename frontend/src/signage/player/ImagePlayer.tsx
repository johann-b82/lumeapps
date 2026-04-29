export interface ImagePlayerProps {
  uri: string | null;
}

export function ImagePlayer({ uri }: ImagePlayerProps) {
  if (!uri) return null;
  return <img src={uri} alt="" className="w-full h-full object-contain" />;
}
