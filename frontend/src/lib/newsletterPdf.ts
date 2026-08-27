/**
 * Newsletter als mehrseitiges PDF — deckungsgleich zum Buch-Reader.
 *
 * Der übergebene Knoten enthält je Block eine Seite (`[data-pdf-page]`, siehe
 * `NewsletterPdfPages`). Jede solche Seite wird einzeln zu einem JPEG gerendert
 * (html-to-image) und als eigene A4-Seite gesetzt (jsPDF) — so beginnt jeder
 * Block auf einer neuen Seite statt mitten durchgeschnitten zu werden. Ein Block,
 * der höher als A4 ist, läuft auf Folgeseiten über. Fehlen `data-pdf-page`-Knoten,
 * wird der Knoten als Ganzes seitenweise verteilt (Rückfall). Genutzt von der
 * Reader-Seite UND der Entwurfs-Vorschau im Redaktions-Editor.
 *
 * JPEG statt PNG ist hier bewusst: jsPDF legt PNGs praktisch unkomprimiert ab,
 * wodurch ein Newsletter mit ~9 A4-Seiten @2× ein PDF von >200 MB erzeugte —
 * groß genug, um den Tab-Speicher zu sprengen und den Download stumm scheitern
 * zu lassen. Jede Seite hat einen deckenden Hintergrund, daher ist JPEG (q0.92)
 * verlustarm genug und ~85× kleiner.
 */
import { toJpeg } from "html-to-image";
import { jsPDF } from "jspdf";

export async function exportNewsletterPdf(node: HTMLElement, filename: string): Promise<void> {
  const seiten = Array.from(node.querySelectorAll<HTMLElement>("[data-pdf-page]"));
  const knoten = seiten.length ? seiten : [node];

  const pdf = new jsPDF({ unit: "pt", format: "a4" });
  const pw = pdf.internal.pageSize.getWidth();
  const ph = pdf.internal.pageSize.getHeight();

  for (let i = 0; i < knoten.length; i++) {
    const dataUrl = await toJpeg(knoten[i], { pixelRatio: 2, backgroundColor: "#ffffff", quality: 0.92 });
    const img = new Image();
    img.src = dataUrl;
    await img.decode();
    const imgH = img.height * (pw / img.width);

    if (i > 0) pdf.addPage();

    // Passt auf eine Seite (kleine Toleranz gegen Rundung).
    if (imgH <= ph + 1) {
      pdf.addImage(dataUrl, "JPEG", 0, 0, pw, imgH);
      continue;
    }
    // Block höher als A4 → über Folgeseiten verteilen.
    let heightLeft = imgH;
    let position = 0;
    pdf.addImage(dataUrl, "JPEG", 0, position, pw, imgH);
    heightLeft -= ph;
    while (heightLeft > 0) {
      position -= ph;
      pdf.addPage();
      pdf.addImage(dataUrl, "JPEG", 0, position, pw, imgH);
      heightLeft -= ph;
    }
  }

  pdf.save(filename);
}
