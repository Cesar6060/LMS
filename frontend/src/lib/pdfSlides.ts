import { GlobalWorkerOptions, getDocument } from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

// pdf.js parses PDFs on a worker thread; Vite's ?url import gives us the
// bundled worker asset without needing a copy step or CDN fetch.
GlobalWorkerOptions.workerSrc = workerUrl;

export const MAX_PDF_BYTES = 50 * 1024 * 1024;
export const MAX_PDF_PAGES = 100;
export const ALT_TEXT_MAX_CHARS = 1000;

/** Target output width for rasterized slides, in CSS pixels. */
const SLIDE_WIDTH_PX = 1920;
const WEBP_QUALITY = 0.9;

export interface RenderedSlide {
  blob: Blob;
  ext: 'webp' | 'png';
  altText: string;
}

export interface SlideDeck {
  numPages: number;
  /** Rasterize one page (1-based) to a 1920px-wide image with alt text. */
  renderPage(pageNumber: number): Promise<RenderedSlide>;
  destroy(): void;
}

/**
 * Thin seam over the DOM canvas so the rasterization logic can be unit
 * tested with pdf.js mocked — jsdom has no 2d canvas context, so tests
 * inject a fake instead of the real `document.createElement('canvas')`.
 */
export interface SlideCanvas {
  canvas: HTMLCanvasElement;
  toBlob(type: string, quality?: number): Promise<Blob | null>;
}

export type CreateSlideCanvas = (width: number, height: number) => SlideCanvas;

const createDomCanvas: CreateSlideCanvas = (width, height) => {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  return {
    canvas,
    toBlob: (type, quality) =>
      new Promise<Blob | null>(resolve => canvas.toBlob(resolve, type, quality)),
  };
};

/** Join a page's text items into a single trimmed, length-capped string. */
function buildAltText(items: ReadonlyArray<object>): string {
  return items
    // getTextContent() mixes TextItem with TextMarkedContent; only the
    // former carries text.
    .map(item => ('str' in item && typeof item.str === 'string' ? item.str : ''))
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, ALT_TEXT_MAX_CHARS);
}

/**
 * Load a PDF file and return a deck handle for rasterizing its pages.
 *
 * Throws an Error with a user-readable message if the file is too large,
 * not a loadable PDF, or has more than MAX_PDF_PAGES pages.
 */
export async function loadDeck(
  file: File,
  createCanvas: CreateSlideCanvas = createDomCanvas,
): Promise<SlideDeck> {
  if (file.size > MAX_PDF_BYTES) {
    throw new Error(
      `PDF is too large (max ${Math.floor(MAX_PDF_BYTES / (1024 * 1024))} MB).`,
    );
  }

  // In pdf.js v6, teardown lives on the loading task, not the document.
  const loadingTask = getDocument({ data: await file.arrayBuffer() });
  let pdf;
  try {
    pdf = await loadingTask.promise;
  } catch {
    throw new Error('Could not read this file as a PDF. Please check the file and try again.');
  }

  if (pdf.numPages > MAX_PDF_PAGES) {
    const numPages = pdf.numPages;
    void loadingTask.destroy();
    throw new Error(
      `PDF has ${numPages} pages (max ${MAX_PDF_PAGES}). Please split the deck and try again.`,
    );
  }

  return {
    numPages: pdf.numPages,

    async renderPage(pageNumber: number): Promise<RenderedSlide> {
      const page = await pdf.getPage(pageNumber);

      const baseViewport = page.getViewport({ scale: 1 });
      const scale = SLIDE_WIDTH_PX / baseViewport.width;
      const viewport = page.getViewport({ scale });

      const target = createCanvas(Math.round(viewport.width), Math.round(viewport.height));
      await page.render({ canvas: target.canvas, viewport }).promise;

      const textContent = await page.getTextContent();
      const altText = buildAltText(textContent.items);

      // Prefer WebP; Safari's toBlob may return null or silently hand back
      // a PNG-typed blob, so verify the type before trusting the extension.
      const webp = await target.toBlob('image/webp', WEBP_QUALITY);
      if (webp && webp.type === 'image/webp') {
        return { blob: webp, ext: 'webp', altText };
      }

      const png = await target.toBlob('image/png');
      if (!png) {
        throw new Error(`Could not encode page ${pageNumber} as an image.`);
      }
      return { blob: png, ext: 'png', altText };
    },

    destroy() {
      void loadingTask.destroy();
    },
  };
}
