import { fireEvent, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NotificationBell } from './NotificationBell';
import type { Notification } from '@/types';

const mockNavigate = vi.hoisted(() => vi.fn());
const mockGetNotifications = vi.hoisted(() => vi.fn());
const mockGetUnreadCount = vi.hoisted(() => vi.fn());
const mockMarkAsRead = vi.hoisted(() => vi.fn());

vi.mock('react-router', () => ({
  useNavigate: () => mockNavigate,
}));

vi.mock('@/services/notifications', () => ({
  notificationService: {
    getNotifications: mockGetNotifications,
    getUnreadCount: mockGetUnreadCount,
    markAsRead: mockMarkAsRead,
    markAllAsRead: vi.fn(),
  },
}));

// Radix's dropdown opens on pointer events jsdom does not deliver reliably.
// These stand-ins render the panel inline, expose the open transition as a
// plain button, and turn item selection into a plain click, so the test
// exercises handleSelect rather than Radix.
vi.mock('@/components/ui/DropdownMenu', () => ({
  DropdownMenu: ({
    children,
    onOpenChange,
  }: {
    children: ReactNode;
    onOpenChange: (open: boolean) => void;
  }) => (
    <div>
      <button type="button" onClick={() => onOpenChange(true)}>
        open panel
      </button>
      {children}
    </div>
  ),
  DropdownMenuTrigger: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  DropdownMenuContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  DropdownMenuItem: ({
    children,
    onSelect,
  }: {
    children: ReactNode;
    onSelect: (event: Event) => void;
  }) => (
    <div role="menuitem" onClick={() => onSelect(new Event('select', { cancelable: true }))}>
      {children}
    </div>
  ),
}));

function makeNotification(relatedUrl: string): Notification {
  return {
    id: 1,
    recipient: 1,
    type: 'announcement',
    title: 'New announcement',
    message: 'Read this',
    is_read: true,
    created_at: '2026-01-01T00:00:00Z',
    related_url: relatedUrl,
  };
}

async function selectNotification(relatedUrl: string) {
  mockGetNotifications.mockResolvedValue([makeNotification(relatedUrl)]);

  render(<NotificationBell />);
  fireEvent.click(screen.getByRole('button', { name: 'open panel' }));

  fireEvent.click(await screen.findByRole('menuitem'));
}

describe('NotificationBell — following related_url', () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    mockGetNotifications.mockReset().mockResolvedValue([]);
    mockGetUnreadCount.mockReset().mockResolvedValue(0);
    mockMarkAsRead.mockReset().mockResolvedValue(undefined);
  });

  it('navigates to an in-app path', async () => {
    await selectNotification('/courses/ROB101/lessons/12');

    expect(mockNavigate).toHaveBeenCalledWith('/courses/ROB101/lessons/12');
  });

  it('does not follow an absolute URL', async () => {
    await selectNotification('https://example.com/phish');

    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('does not follow a protocol-relative URL', async () => {
    await selectNotification('//example.com/phish');

    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
