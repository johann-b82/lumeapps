export type PlayerItemKind = "image" | "video" | "pdf" | "pptx" | "url" | "html";
export type PlayerTransition = "fade" | "cut" | null;

export interface PlayerItem {
  id: string;                       // stable key for React reconciliation (media_id is fine)
  kind: PlayerItemKind;
  uri: string | null;               // for image/video/pdf/url — absolute or app-relative URL
  html: string | null;              // for html
  slide_paths: string[] | null;     // for pptx — array of image URLs, in order
  duration_s: number;               // >= 1
  transition: PlayerTransition;
}
