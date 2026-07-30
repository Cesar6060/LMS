import { describe, expect, it, vi } from 'vitest';
import { uploadSlideTasks, type SlideUploadTask } from './slideImport';

/**
 * The phase-61 sequential upload pipeline. The interesting behaviour is the
 * failure/cancel semantics: keep what succeeded, record what failed so it can
 * be retried, and let an in-flight page finish on abort (aborting mid-request
 * could duplicate the slide on retry).
 */

function makeTask(pageNumber: number): SlideUploadTask {
  return {
    pageNumber,
    title: `Slide ${pageNumber}`,
    blob: new Blob(['x']),
    ext: 'webp',
    altText: `Slide ${pageNumber} of deck`,
  };
}

function makeTasks(count: number, startAt = 1): SlideUploadTask[] {
  return Array.from({ length: count }, (_, i) => makeTask(startAt + i));
}

describe('uploadSlideTasks', () => {
  it('uploads strictly one at a time, in task order', async () => {
    const tasks = makeTasks(4);
    const started: number[] = [];
    let inFlight = 0;
    let maxInFlight = 0;

    const upload = vi.fn(async (task: SlideUploadTask) => {
      started.push(task.pageNumber);
      inFlight++;
      maxInFlight = Math.max(maxInFlight, inFlight);
      // Yield so an (incorrect) concurrent caller would overlap here.
      await new Promise(resolve => setTimeout(resolve, 0));
      inFlight--;
    });

    const result = await uploadSlideTasks(tasks, upload);

    expect(started).toEqual([1, 2, 3, 4]);
    expect(maxInFlight).toBe(1);
    expect(result).toEqual({ succeeded: [1, 2, 3, 4], failed: [], skipped: [], aborted: false });
  });

  it('keeps going after a mid-list failure and records only that page as failed', async () => {
    const tasks = makeTasks(4);
    const upload = vi.fn(async (task: SlideUploadTask) => {
      if (task.pageNumber === 2) throw new Error('413 too large');
    });

    const result = await uploadSlideTasks(tasks, upload);

    expect(upload).toHaveBeenCalledTimes(4);
    expect(result.succeeded).toEqual([1, 3, 4]);
    expect(result.failed).toEqual([2]);
    expect(result.skipped).toEqual([]);
    expect(result.aborted).toBe(false);
  });

  it('supports a retry run over just the failed pages', async () => {
    const tasks = makeTasks(5);
    let firstRun = true;
    const upload = vi.fn(async (task: SlideUploadTask) => {
      if (firstRun && (task.pageNumber === 2 || task.pageNumber === 4)) {
        throw new Error('flaky network');
      }
    });

    const first = await uploadSlideTasks(tasks, upload);
    expect(first.succeeded).toEqual([1, 3, 5]);
    expect(first.failed).toEqual([2, 4]);

    // Retry exactly the failed set — succeeded and failed never overlap, so
    // the union of both runs' successes covers every page exactly once.
    firstRun = false;
    const retryTasks = tasks.filter(t => first.failed.includes(t.pageNumber));
    const second = await uploadSlideTasks(retryTasks, upload);

    expect(second).toEqual({ succeeded: [2, 4], failed: [], skipped: [], aborted: false });
    expect(first.succeeded.filter(p => second.succeeded.includes(p))).toEqual([]);
    expect([...first.succeeded, ...second.succeeded].sort()).toEqual([1, 2, 3, 4, 5]);
  });

  it('lets the in-flight page finish on abort, skips the rest', async () => {
    const tasks = makeTasks(4);
    const controller = new AbortController();

    const upload = vi.fn(async (task: SlideUploadTask) => {
      if (task.pageNumber === 2) {
        // Cancel mid-request: page 2 must still complete and be recorded.
        controller.abort();
        await new Promise(resolve => setTimeout(resolve, 0));
      }
    });

    const result = await uploadSlideTasks(tasks, upload, { signal: controller.signal });

    expect(upload).toHaveBeenCalledTimes(2);
    expect(result.succeeded).toEqual([1, 2]);
    expect(result.failed).toEqual([]);
    expect(result.skipped).toEqual([3, 4]);
    expect(result.aborted).toBe(true);
  });

  it('fires onPageStart with (task, index, total) and onPageDone on success', async () => {
    const tasks = makeTasks(2, 7); // page numbers 7 and 8 — index and page differ
    const onPageStart = vi.fn();
    const onPageDone = vi.fn();
    const onPageFailed = vi.fn();

    await uploadSlideTasks(tasks, async () => undefined, {
      onPageStart,
      onPageDone,
      onPageFailed,
    });

    expect(onPageStart).toHaveBeenCalledTimes(2);
    expect(onPageStart).toHaveBeenNthCalledWith(1, tasks[0], 0, 2);
    expect(onPageStart).toHaveBeenNthCalledWith(2, tasks[1], 1, 2);
    expect(onPageDone).toHaveBeenCalledTimes(2);
    expect(onPageDone).toHaveBeenNthCalledWith(1, tasks[0]);
    expect(onPageDone).toHaveBeenNthCalledWith(2, tasks[1]);
    expect(onPageFailed).not.toHaveBeenCalled();
  });

  it('fires onPageFailed with the task and error on rejection, not onPageDone', async () => {
    const tasks = makeTasks(2);
    const boom = new Error('server said no');
    const onPageDone = vi.fn();
    const onPageFailed = vi.fn();

    await uploadSlideTasks(
      tasks,
      async (task: SlideUploadTask) => {
        if (task.pageNumber === 1) throw boom;
      },
      { onPageDone, onPageFailed },
    );

    expect(onPageFailed).toHaveBeenCalledTimes(1);
    expect(onPageFailed).toHaveBeenCalledWith(tasks[0], boom);
    expect(onPageDone).toHaveBeenCalledTimes(1);
    expect(onPageDone).toHaveBeenCalledWith(tasks[1]);
  });

  it('returns an all-empty result for an empty task list', async () => {
    const upload = vi.fn();

    const result = await uploadSlideTasks([], upload);

    expect(result).toEqual({ succeeded: [], failed: [], skipped: [], aborted: false });
    expect(upload).not.toHaveBeenCalled();
  });
});
