import GithubSlugger from "github-slugger";

export interface TocEntry {
  level: 2 | 3;
  text: string;
  id: string;
}

const headingRe = /^(#{2,3})\s+(.+)$/gm;

export function extractToc(markdown: string): TocEntry[] {
  const slugger = new GithubSlugger();
  const entries: TocEntry[] = [];
  let match: RegExpExecArray | null;
  while ((match = headingRe.exec(markdown)) !== null) {
    const level = match[1].length as 2 | 3;
    const text = match[2].trim();
    entries.push({ level, text, id: slugger.slug(text) });
  }
  return entries;
}
