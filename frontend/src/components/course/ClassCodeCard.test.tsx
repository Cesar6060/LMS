import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ClassCodeCard } from './ClassCodeCard';

const mockGetJoinCode = vi.hoisted(() => vi.fn());
const mockRotateJoinCode = vi.hoisted(() => vi.fn());
const mockDisableJoinCode = vi.hoisted(() => vi.fn());
const mockIsForbidden = vi.hoisted(() => vi.fn());

vi.mock('@/services/courses', () => ({
  courseService: {
    getJoinCode: mockGetJoinCode,
    rotateJoinCode: mockRotateJoinCode,
    disableJoinCode: mockDisableJoinCode,
  },
}));

vi.mock('@/services/api', () => ({
  isForbidden: (err: unknown) => mockIsForbidden(err),
}));

describe('ClassCodeCard', () => {
  beforeEach(() => {
    mockGetJoinCode.mockReset();
    mockRotateJoinCode.mockReset();
    mockDisableJoinCode.mockReset();
    mockIsForbidden.mockReset();
    mockIsForbidden.mockReturnValue(false);
  });

  it('shows the code and its full lifecycle controls', async () => {
    mockGetJoinCode.mockResolvedValue('ABCD2345');

    render(<ClassCodeCard courseCode="VGD101" />);

    // Twice on purpose: the big selectable code, and again inside the
    // read-this-to-your-class script.
    expect(await screen.findAllByText('ABCD2345')).toHaveLength(2);
    expect(screen.getByRole('button', { name: /rotate code/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /turn off/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /copy code/i })).toBeInTheDocument();
  });

  it('offers generation when the course has no code yet', async () => {
    mockGetJoinCode.mockResolvedValue(null);

    render(<ClassCodeCard courseCode="VGD101" />);

    expect(
      await screen.findByRole('button', { name: /generate a class code/i })
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /rotate code/i })).not.toBeInTheDocument();
  });

  it('is deterministic for a given course', async () => {
    // Guards the card itself. That BOTH pages actually mount it is asserted
    // where it can fail — in StudentRosterPage.test.tsx and
    // ManageCoursePage.test.tsx — since rendering it twice here could never
    // detect a page dropping it.
    mockGetJoinCode.mockResolvedValue('ABCD2345');

    const fromRoster = render(<ClassCodeCard courseCode="VGD101" />);
    const rosterHtml = await waitFor(() => {
      expect(fromRoster.getAllByText('ABCD2345')).toHaveLength(2);
      return fromRoster.container.innerHTML;
    });
    fromRoster.unmount();

    const fromManage = render(<ClassCodeCard courseCode="VGD101" />);
    await screen.findAllByText('ABCD2345');

    expect(fromManage.container.innerHTML).toBe(rosterHtml);
  });

  it('hides itself entirely on a 403', async () => {
    // The demo course refuses the join-code endpoint outright. Offering an
    // action that can never work is worse than offering nothing.
    mockIsForbidden.mockReturnValue(true);
    mockGetJoinCode.mockRejectedValue({ response: { status: 403 } });

    const { container } = render(<ClassCodeCard courseCode="DEMO101" />);

    await waitFor(() => expect(container).toBeEmptyDOMElement());
    expect(screen.queryByText(/class code/i)).not.toBeInTheDocument();
  });

  it('keeps the card and explains itself on a non-403 failure', async () => {
    mockGetJoinCode.mockRejectedValue({ response: { status: 500 } });

    render(<ClassCodeCard courseCode="VGD101" />);

    expect(await screen.findByText(/could not load the class code/i)).toBeInTheDocument();
  });
});
