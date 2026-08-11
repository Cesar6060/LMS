import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AttachmentUploader } from './AttachmentUploader';

const mockGetLessonAttachments = vi.hoisted(() => vi.fn());
const mockUploadLessonAttachments = vi.hoisted(() => vi.fn());
const mockIsDemoBlocked = vi.hoisted(() => vi.fn());

vi.mock('@/services/courses', () => ({
  courseService: {
    getLessonAttachments: mockGetLessonAttachments,
    uploadLessonAttachments: mockUploadLessonAttachments,
    deleteLessonAttachment: vi.fn(),
  },
}));

vi.mock('@/services/api', () => ({
  DEMO_BLOCKED_MESSAGE: 'Not available in the demo.',
  isDemoBlocked: (err: unknown) => mockIsDemoBlocked(err),
}));

async function uploadOneFile() {
  render(<AttachmentUploader lessonId={1} lessonTitle="Naming Conventions" />);
  await screen.findByText('No attachments yet.');

  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, {
    target: { files: [new File(['print(1)'], 'starter.py', { type: 'text/x-python' })] },
  });
}

describe('AttachmentUploader — upload rejections', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    mockGetLessonAttachments.mockReset().mockResolvedValue([]);
    mockUploadLessonAttachments.mockReset();
    mockIsDemoBlocked.mockReset().mockReturnValue(false);
  });

  it('names the demo account as the reason on a 403 demo_blocked', async () => {
    mockIsDemoBlocked.mockReturnValue(true);
    mockUploadLessonAttachments.mockRejectedValue({
      response: { status: 403, data: { detail: 'Demo accounts cannot upload.', code: 'demo_blocked' } },
    });

    await uploadOneFile();

    expect(await screen.findByText('Not available in the demo.')).toBeInTheDocument();
  });

  it('asks the instructor to wait on a 429', async () => {
    mockUploadLessonAttachments.mockRejectedValue({ response: { status: 429 } });

    await uploadOneFile();

    expect(
      await screen.findByText('Too many uploads — please wait a while and try again.')
    ).toBeInTheDocument();
  });

  // The attachment endpoint reports per-file rejections as `error`. An earlier
  // version of this test mocked `detail`, which the API never sends here, so it
  // passed while every real rejection showed the generic message.
  it('passes through a per-file rejection from the backend', async () => {
    mockUploadLessonAttachments.mockRejectedValue({
      response: { status: 400, data: { error: '"starter.py" does not match its file type.' } },
    });

    await uploadOneFile();

    expect(
      await screen.findByText('"starter.py" does not match its file type.')
    ).toBeInTheDocument();
  });

  it('still reads detail, which permission denials use', async () => {
    mockUploadLessonAttachments.mockRejectedValue({
      response: { status: 403, data: { detail: 'Only instructors can upload attachments.' } },
    });

    await uploadOneFile();

    expect(
      await screen.findByText('Only instructors can upload attachments.')
    ).toBeInTheDocument();
  });

  it('stays generic when the failure has no shape it recognizes', async () => {
    mockUploadLessonAttachments.mockRejectedValue(new Error('Network Error'));

    await uploadOneFile();

    expect(await screen.findByText('Failed to upload files')).toBeInTheDocument();
  });
});
