import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getDocument } from 'pdfjs-dist';
import {
  ALT_TEXT_MAX_CHARS,
  MAX_PDF_BYTES,
  MAX_PDF_PAGES,
  loadDeck,
  type CreateSlideCanvas,
} from './pdfSlides';

/**
 * The PDF→slide rasterizer (phase 61). pdf.js and the canvas seam are both
 * mocked: jsdom has no 2d canvas context, and the interesting behaviour is
 * the orchestration — size/page guards, the 1920px scale math, alt-text
 * normalization and the WebP→PNG Safari fallback.
 */
vi.mock('pdfjs-dist', () => ({
  GlobalWorkerOptions: { workerSrc: '' },
  getDocument: vi.fn(),
}));
vi.mock('pdfjs-dist/build/pdf.worker.min.mjs?url', () => ({
  default: 'mock-worker-url',
}));

const mockGetDocument = vi.mocked(getDocument);

interface FakePageOptions {
  width?: number;
  height?: number;
  textItems?: Array<{ str?: string }>;
}

function makeFakePage({ width = 960, height = 540, textItems = [] }: FakePageOptions = {}) {
  return {
    getViewport: vi.fn(({ scale }: { scale: number }) => ({
      width: width * scale,
      height: height * scale,
      scale,
    })),
    render: vi.fn(() => ({ promise: Promise.resolve() })),
    getTextContent: vi.fn(() => Promise.resolve({ items: textItems })),
  };
}

function makeFakePdf(numPages: number, page = makeFakePage()) {
  return {
    numPages,
    getPage: vi.fn(() => Promise.resolve(page)),
  };
}

/** pdf.js v6 puts destroy() on the loading task, not the document proxy. */
function stubGetDocument(pdf: ReturnType<typeof makeFakePdf>) {
  const task = { promise: Promise.resolve(pdf), destroy: vi.fn(() => Promise.resolve()) };
  mockGetDocument.mockReturnValue(task as unknown as ReturnType<typeof getDocument>);
  return task;
}

function makeFile(size = 1024): File {
  return {
    size,
    arrayBuffer: () => Promise.resolve(new Uint8Array([1, 2, 3]).buffer),
  } as unknown as File;
}

/** Canvas seam stub: `encodings` maps mime type → what toBlob resolves with. */
function makeCanvasSeam(encodings: Record<string, Blob | null>) {
  const created: Array<{ width: number; height: number }> = [];
  const toBlob = vi.fn((type: string) => Promise.resolve(encodings[type] ?? null));
  const create: CreateSlideCanvas = (width, height) => {
    created.push({ width, height });
    return { canvas: {} as HTMLCanvasElement, toBlob };
  };
  return { create, created, toBlob };
}

const webpBlob = new Blob(['webp-bytes'], { type: 'image/webp' });
const pngBlob = new Blob(['png-bytes'], { type: 'image/png' });

beforeEach(() => {
  vi.clearAllMocks();
});

describe('loadDeck', () => {
  it('rejects an oversize file without parsing it', async () => {
    const file = makeFile(MAX_PDF_BYTES + 1);
    await expect(loadDeck(file)).rejects.toThrow(/too large/i);
    expect(mockGetDocument).not.toHaveBeenCalled();
  });

  it('accepts a file exactly at the size limit', async () => {
    stubGetDocument(makeFakePdf(3));
    const deck = await loadDeck(makeFile(MAX_PDF_BYTES));
    expect(deck.numPages).toBe(3);
  });

  it('rejects a deck with more than MAX_PDF_PAGES pages and destroys it', async () => {
    const task = stubGetDocument(makeFakePdf(MAX_PDF_PAGES + 1));
    await expect(loadDeck(makeFile())).rejects.toThrow(/101 pages/);
    expect(task.destroy).toHaveBeenCalledOnce();
  });

  it('wraps pdf.js parse failures in a user-readable error', async () => {
    mockGetDocument.mockReturnValue(
      { promise: Promise.reject(new Error('bad XRef')) } as unknown as ReturnType<
        typeof getDocument
      >,
    );
    await expect(loadDeck(makeFile())).rejects.toThrow(/could not read this file as a pdf/i);
  });

  it('exposes numPages and proxies destroy() to pdf.js', async () => {
    const task = stubGetDocument(makeFakePdf(7));
    const deck = await loadDeck(makeFile());
    expect(deck.numPages).toBe(7);
    expect(task.destroy).not.toHaveBeenCalled();
    deck.destroy();
    expect(task.destroy).toHaveBeenCalledOnce();
  });
});

describe('renderPage', () => {
  it('renders at a scale that yields a 1920px-wide canvas and returns webp', async () => {
    const page = makeFakePage({ width: 960, height: 540 });
    const pdf = makeFakePdf(1, page);
    stubGetDocument(pdf);
    const seam = makeCanvasSeam({ 'image/webp': webpBlob });

    const deck = await loadDeck(makeFile(), seam.create);
    const slide = await deck.renderPage(1);

    expect(pdf.getPage).toHaveBeenCalledWith(1);
    // 960pt-wide page → scale 2 → 1920 x 1080 output canvas.
    expect(page.getViewport).toHaveBeenCalledWith({ scale: 1 });
    expect(page.getViewport).toHaveBeenCalledWith({ scale: 2 });
    expect(seam.created).toEqual([{ width: 1920, height: 1080 }]);
    expect(seam.toBlob).toHaveBeenCalledWith('image/webp', 0.9);
    expect(slide.blob).toBe(webpBlob);
    expect(slide.ext).toBe('webp');
  });

  it('falls back to png when webp encoding yields null (Safari)', async () => {
    stubGetDocument(makeFakePdf(1));
    const seam = makeCanvasSeam({ 'image/webp': null, 'image/png': pngBlob });

    const deck = await loadDeck(makeFile(), seam.create);
    const slide = await deck.renderPage(1);

    expect(slide.blob).toBe(pngBlob);
    expect(slide.ext).toBe('png');
  });

  it('falls back to png when the "webp" blob is not actually webp (Safari)', async () => {
    stubGetDocument(makeFakePdf(1));
    // Safari can hand back a PNG-typed blob from a webp request.
    const seam = makeCanvasSeam({ 'image/webp': pngBlob, 'image/png': pngBlob });

    const deck = await loadDeck(makeFile(), seam.create);
    const slide = await deck.renderPage(1);

    expect(slide.blob).toBe(pngBlob);
    expect(slide.ext).toBe('png');
  });

  it('throws a user-readable error when both encodings fail', async () => {
    stubGetDocument(makeFakePdf(1));
    const seam = makeCanvasSeam({ 'image/webp': null, 'image/png': null });

    const deck = await loadDeck(makeFile(), seam.create);
    await expect(deck.renderPage(1)).rejects.toThrow(/could not encode page 1/i);
  });

  it('joins text items with spaces, collapses whitespace and trims', async () => {
    const page = makeFakePage({
      textItems: [
        { str: '  Intro to ' },
        { str: 'Game\nLoops' },
        { str: '' },
        { str: '\t and   timing ' },
      ],
    });
    stubGetDocument(makeFakePdf(1, page));
    const seam = makeCanvasSeam({ 'image/webp': webpBlob });

    const deck = await loadDeck(makeFile(), seam.create);
    const slide = await deck.renderPage(1);

    expect(slide.altText).toBe('Intro to Game Loops and timing');
  });

  it('caps alt text at ALT_TEXT_MAX_CHARS', async () => {
    const page = makeFakePage({
      textItems: [{ str: 'a'.repeat(600) }, { str: 'b'.repeat(600) }],
    });
    stubGetDocument(makeFakePdf(1, page));
    const seam = makeCanvasSeam({ 'image/webp': webpBlob });

    const deck = await loadDeck(makeFile(), seam.create);
    const slide = await deck.renderPage(1);

    expect(slide.altText).toHaveLength(ALT_TEXT_MAX_CHARS);
    expect(slide.altText.startsWith('a'.repeat(600))).toBe(true);
  });
});
