import { useEffect, useState } from "react";

export interface PptxPlayerProps {
  slidePaths: string[] | null;
  durationS: number; // total item duration
}

export function PptxPlayer({ slidePaths, durationS }: PptxPlayerProps) {
  const [index, setIndex] = useState(0);
  const paths = slidePaths ?? [];

  useEffect(() => {
    setIndex(0);
    if (paths.length <= 1) return;
    const perSlide = Math.max(1000, (durationS * 1000) / paths.length);
    const id = setInterval(() => setIndex((i) => (i + 1) % paths.length), perSlide);
    return () => clearInterval(id);
  }, [paths, durationS]);

  if (paths.length === 0) return null;
  return <img src={paths[index]} alt="" className="w-full h-full object-contain" />;
}
