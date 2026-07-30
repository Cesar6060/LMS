/**
 * Phase 61 — sequential slide-upload pipeline for the PDF import modal.
 *
 * One request per slide (that is what makes keep-what-succeeded and
 * retry-remaining possible), driven page by page so the modal can show
 * "Uploading slide 7 of 24". Pure orchestration: the actual request is
 * injected, so this is unit-testable with the service mocked.
 */

/**
 * Client-side deck limits. They live here, not in pdfSlides.ts, so the editor
 * can show them in the dropzone copy without statically importing pdf.js —
 * that library is ~145 kB gzip and must stay out of the lesson-editor chunk
 * for instructors who never open the import modal.
 */
export const MAX_PDF_BYTES = 50 * 1024 * 1024;
export const MAX_PDF_PAGES = 100;

export interface SlideUploadTask {
  /** 1-based PDF page number (stable across retries). */
  pageNumber: number;
  title: string;
  blob: Blob;
  ext: 'webp' | 'png';
  altText: string;
}

export interface SlideUploadCallbacks {
  /** Fires before each page's request. `index` is 0-based within this run. */
  onPageStart?: (task: SlideUploadTask, index: number, total: number) => void;
  onPageDone?: (task: SlideUploadTask) => void;
  onPageFailed?: (task: SlideUploadTask, error: unknown) => void;
}

export interface SlideUploadResult {
  succeeded: number[];
  failed: number[];
  /** Page numbers never attempted because the run was cancelled. */
  skipped: number[];
  aborted: boolean;
}

/**
 * Upload tasks strictly in order. Cancellation (via `signal`) stops AFTER the
 * in-flight page: the current request is allowed to finish and is recorded
 * accurately — aborting it mid-flight would leave the client unsure whether
 * the server created the section, and a retry would then duplicate the slide.
 */
export async function uploadSlideTasks(
  tasks: SlideUploadTask[],
  upload: (task: SlideUploadTask) => Promise<unknown>,
  opts: { signal?: AbortSignal } & SlideUploadCallbacks = {},
): Promise<SlideUploadResult> {
  const succeeded: number[] = [];
  const failed: number[] = [];
  const skipped: number[] = [];
  let aborted = false;

  for (let i = 0; i < tasks.length; i++) {
    const task = tasks[i];
    if (opts.signal?.aborted) {
      aborted = true;
      skipped.push(task.pageNumber);
      continue;
    }
    opts.onPageStart?.(task, i, tasks.length);
    try {
      await upload(task);
      succeeded.push(task.pageNumber);
      opts.onPageDone?.(task);
    } catch (err) {
      failed.push(task.pageNumber);
      opts.onPageFailed?.(task, err);
    }
  }

  return { succeeded, failed, skipped, aborted };
}
