import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router';
import { useAuth } from '@/contexts/useAuth';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { courseService, type Announcement } from '@/services/courses';
import { Skeleton } from '@/components/ui/Skeleton';
import {
  Megaphone, Pin, Trash2, Edit, Calendar, User
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/Dialog';
import { Input } from '@/components/ui/Input';
import ReactMarkdown from 'react-markdown';
import { PageContainer } from '@/components/layout/PageContainer';
import { BackLink } from '@/components/layout/BackLink';

export function AnnouncementDetailPage() {
  const { code, announcementId } = useParams<{ code: string; announcementId: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Arrived from CourseDetail (?from=course) → back goes to the course.
  const fromCourse = searchParams.get('from') === 'course';
  const backTo = fromCourse ? `/courses/${code}` : `/courses/${code}/announcements`;
  const backLabel = fromCourse ? 'Course' : 'Announcements';

  const [announcement, setAnnouncement] = useState<Announcement | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // Edit modal state
  const [showEditModal, setShowEditModal] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    content: '',
    is_pinned: false,
  });
  const [isSaving, setIsSaving] = useState(false);

  // Delete confirmation state
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const isAuthor = user?.id === announcement?.author.id;

  const loadAnnouncement = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await courseService.getAnnouncement(Number(announcementId));
      setAnnouncement(data);
      setFormData({
        title: data.title,
        content: data.content,
        is_pinned: data.is_pinned,
      });
    } catch (err) {
      setError('Failed to load announcement');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, [announcementId]);

  useEffect(() => {
    if (announcementId) {
      loadAnnouncement();
    }
  }, [announcementId, loadAnnouncement]);

  const handleSave = async () => {
    if (!formData.title.trim() || !formData.content.trim()) {
      return;
    }

    try {
      setIsSaving(true);
      const updated = await courseService.updateAnnouncement(Number(announcementId), formData);
      setAnnouncement(updated);
      setShowEditModal(false);
    } catch (err) {
      console.error('Failed to save announcement:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    try {
      setIsDeleting(true);
      await courseService.deleteAnnouncement(Number(announcementId));
      navigate(`/courses/${code}/announcements`);
    } catch (err) {
      console.error('Failed to delete announcement:', err);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleTogglePin = async () => {
    if (!announcement) return;

    try {
      const updated = announcement.is_pinned
        ? await courseService.unpinAnnouncement(announcement.id)
        : await courseService.pinAnnouncement(announcement.id);
      setAnnouncement(updated);
    } catch (err) {
      console.error('Failed to toggle pin:', err);
    }
  };

  if (isLoading) {
    return (
      <PageContainer maxWidth="max-w-3xl">
        <Skeleton className="h-4 w-32 mb-6" />
        <Skeleton className="h-8 w-3/4 mb-4" />
        <div className="flex items-center gap-4 mb-6">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-32" />
        </div>
        <Skeleton className="h-64 w-full" />
      </PageContainer>
    );
  }

  if (error || !announcement) {
    return (
      <PageContainer maxWidth="max-w-3xl">
        <Card>
          <CardContent className="py-12 text-center">
            <Megaphone className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">Announcement Not Found</h3>
            <p className="text-muted-foreground mb-4">{error || 'The announcement you are looking for does not exist.'}</p>
            <BackLink to={backTo} label={backLabel} />
          </CardContent>
        </Card>
      </PageContainer>
    );
  }

  return (
    <PageContainer maxWidth="max-w-3xl">
      {/* Back Link */}
      <BackLink to={backTo} label={backLabel} className="mb-6" />

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-2">
            {announcement.is_pinned && (
              <Pin className="h-5 w-5 text-primary" />
            )}
            <h1 className="text-3xl font-bold">{announcement.title}</h1>
          </div>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1">
              <User className="h-4 w-4" />
              {announcement.author.first_name} {announcement.author.last_name}
            </span>
            <span className="flex items-center gap-1">
              <Calendar className="h-4 w-4" />
              {new Date(announcement.created_at).toLocaleDateString('en-US', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </span>
          </div>
        </div>

        {isAuthor && (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleTogglePin}
              title={announcement.is_pinned ? 'Unpin' : 'Pin'}
            >
              <Pin className={`h-4 w-4 mr-2 ${announcement.is_pinned ? 'text-primary' : ''}`} />
              {announcement.is_pinned ? 'Unpin' : 'Pin'}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowEditModal(true)}
            >
              <Edit className="h-4 w-4 mr-2" />
              Edit
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowDeleteDialog(true)}
              className="text-destructive hover:text-destructive"
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Delete
            </Button>
          </div>
        )}
      </div>

      {/* Content */}
      <Card>
        <CardContent className="py-6 prose prose-slate dark:prose-invert max-w-none">
          <ReactMarkdown>{announcement.content}</ReactMarkdown>
        </CardContent>
      </Card>

      {/* Edit Modal */}
      <Dialog open={showEditModal} onOpenChange={setShowEditModal}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Announcement</DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div>
              <label className="block text-sm font-medium mb-1">Title</label>
              <Input
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="Announcement title"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Content</label>
              <textarea
                value={formData.content}
                onChange={(e) => setFormData({ ...formData, content: e.target.value })}
                placeholder="Write your announcement... (Markdown supported)"
                className="w-full min-h-[200px] px-3 py-2 border rounded-md resize-y
                  bg-background text-foreground
                  focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              />
            </div>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.is_pinned}
                onChange={(e) => setFormData({ ...formData, is_pinned: e.target.checked })}
                className="rounded border-input"
              />
              <span className="text-sm">Pin this announcement</span>
            </label>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditModal(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSave}
              disabled={isSaving || !formData.title.trim() || !formData.content.trim()}
            >
              {isSaving ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Announcement</DialogTitle>
          </DialogHeader>
          <p className="text-muted-foreground">
            Are you sure you want to delete this announcement? This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageContainer>
  );
}
