/**
 * Newsletter als mehrseitiges PDF aus dem gerenderten DOM-Knoten.
 *
 * Rendert den Knoten zu einem PNG (html-to-image) und verteilt das hohe Bild
 * seitenweise auf A4 (jsPDF). Genutzt von der Reader-Seite UND der Entwurfs-
 * Vorschau im Redaktions-Editor.
 */
import { toPng } from "html-to-image";
import { jsPDF } from "jspdf";

export async function exportNewsletterPdf(node: HTMLElement, filename: string): Promise<void> {
  const dataUrl = await toPng(node, { pixelRatio: 2, backgroundColor: "#ffffff", cacheBust: true });
  const img = new Image();
  img.src = dataUrl;
  await img.decode();
  const pdf = new jsPDF({ unit: "pt", format: "a4" });
  const pw = pdf.internal.pageSize.getWidth();
  const ph = pdf.internal.pageSize.getHeight();
  const imgH = img.height * (pw / img.width);
  let heightLeft = imgH;
  let position = 0;
  pdf.addImage(dataUrl, "PNG", 0, position, pw, imgH);
  heightLeft -= ph;
  while (heightLeft > 0) {
    position -= ph;
    pdf.addPage();
    pdf.addImage(dataUrl, "PNG", 0, position, pw, imgH);
    heightLeft -= ph;
  }
  pdf.save(filename);
}
