import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Skeleton } from '@/components/ui/Skeleton';
import { courseService } from '@/services/courses';
import { discussionService } from '@/services/discussions';
import { isForbidden } from '@/services/api';
import { AccessDenied } from '@/components/AccessDenied';
import type { ThreadDetail, Reply } from '@/types';
import {
  MessageSquare, Pin, Lock, Unlock, ChevronLeft, Trash2, Edit, User, Calendar,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/Dialog';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { PageContainer } from '@/components/layout/PageContainer';

const PROSE = 'prose prose-neutral dark:prose-invert max-w-none';

function authorName(u: Reply['author']): string {
  const full = `${u.first_name} ${u.last_name}`.trim();
  return full || u.email;
}

export function ThreadDetailPage() {
  const { code, threadId } = useParams<{ code: string; threadId: string }>();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [thread, setThread] = useState<ThreadDetail | null>(null);
  const [instructorId, setInstructorId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [forbidden, setForbidden] = useState(false);

  // Reply form
  const [replyContent, setReplyContent] = useState('');
  const [isReplying, setIsReplying] = useState(false);

  // Thread edit
  const [showEditModal, setShowEditModal] = useState(false);
  const [editData, setEditData] = useState({ title: '', content: '' });
  const [isSaving, setIsSaving] = useState(false);

  // Delete thread
  const [showDeleteThread, setShowDeleteThread] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Reply edit / delete
  const [editingReplyId, setEditingReplyId] = useState<number | null>(null);
  const [editingReplyContent, setEditingReplyContent] = useState('');
  const [deleteReplyId, setDeleteReplyId] = useState<number | null>(null);

  const isCourseOwner = user?.id != null && user.id === instructorId;
  const isThreadAuthor = user?.id != null && user.id === thread?.author.id;

  useEffect(() => {
    if (threadId) {
      loadData();
    }
  }, [threadId]);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [threadData, courseData] = await Promise.all([
        discussionService.getThread(Number(threadId)),
        courseService.getCourse(code!),
      ]);
      setThread(threadData);
      setInstructorId(courseData.instructor.id);
    } catch (err) {
      if (isForbidden(err)) {
        setForbidden(true);
      } else {
        setError('Failed to load thread');
        console.error(err);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const refreshThread = async () => {
    const data = await discussionService.getThread(Number(threadId));
    setThread(data);
  };

  const handleReply = async () => {
    if (!replyContent.trim() || !thread) return;
    try {
      setIsReplying(true);
      await discussionService.createReply(thread.id, { content: replyContent });
      setReplyContent('');
      await refreshThread();
    } catch (err) {
      console.error('Failed to post reply:', err);
    } finally {
      setIsReplying(false);
    }
  };

  const openEditThread = () => {
    if (!thread) return;
    setEditData({ title: thread.title, content: thread.content });
    setShowEditModal(true);
  };

  const handleSaveThread = async () => {
    if (!thread || !editData.title.trim() || !editData.content.trim()) return;
    try {
      setIsSaving(true);
      const updated = await discussionService.updateThread(thread.id, editData);
      setThread({ ...updated, replies: thread.replies });
      setShowEditModal(false);
    } catch (err) {
      console.error('Failed to update thread:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteThread = async () => {
    if (!thread) return;
    try {
      setIsDeleting(true);
      await discussionService.deleteThread(thread.id);
      navigate(`/courses/${code}/discussions`);
    } catch (err) {
      console.error('Failed to delete thread:', err);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleTogglePin = async () => {
    if (!thread) return;
    try {
      await discussionService.togglePin(thread.id);
      await refreshThread();
    } catch (err) {
      console.error('Failed to toggle pin:', err);
    }
  };

  const handleToggleLock = async () => {
    if (!thread) return;
    try {
      await discussionService.toggleLock(thread.id);
      await refreshThread();
    } catch (err) {
      console.error('Failed to toggle lock:', err);
    }
  };

  const startEditReply = (reply: Reply) => {
    setEditingReplyId(reply.id);
    setEditingReplyContent(reply.content);
  };

  const handleSaveReply = async () => {
    if (editingReplyId == null || !editingReplyContent.trim()) return;
    try {
      await discussionService.updateReply(editingReplyId, { content: editingReplyContent });
      setEditingReplyId(null);
      setEditingReplyContent('');
      await refreshThread();
    } catch (err) {
      console.error('Failed to update reply:', err);
    }
  };

  const handleDeleteReply = async () => {
    if (deleteReplyId == null) return;
    try {
      await discussionService.deleteReply(deleteReplyId);
      setDeleteReplyId(null);
      await refreshThread();
    } catch (err) {
      console.error('Failed to delete reply:', err);
    }
  };

  if (isLoading) {
    return (
      <PageContainer maxWidth="max-w-3xl">
        <Skeleton className="h-4 w-32 mb-6" />
        <Skeleton className="h-8 w-3/4 mb-4" />
        <Skeleton className="h-64 w-full" />
      </PageContainer>
    );
  }

  if (forbidden) {
    return <AccessDenied />;
  }

  if (error || !thread) {
    return (
      <PageContainer maxWidth="max-w-3xl">
        <Card>
          <CardContent className="py-12 text-center">
            <MessageSquare className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">Thread Not Found</h3>
            <p className="text-muted-foreground mb-4">
              {error || 'The thread you are looking for does not exist.'}
            </p>
            <Link to={`/courses/${code}/discussions`}>
              <Button>Back to Discussions</Button>
            </Link>
          </CardContent>
        </Card>
      </PageContainer>
    );
  }

  const canReply = !thread.is_locked || isCourseOwner;

  return (
    <PageContainer maxWidth="max-w-3xl">
      {/* Back Link */}
      <Link
        to={`/courses/${code}/discussions`}
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground mb-6"
      >
        <ChevronLeft className="h-4 w-4 mr-1" />
        Back to Discussions
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <div className="flex items-center gap-2 mb-2">
            {thread.is_pinned && <Pin className="h-5 w-5 text-primary" />}
            {thread.is_locked && <Lock className="h-5 w-5 text-muted-foreground" />}
            <h1 className="text-3xl font-bold">{thread.title}</h1>
          </div>
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1">
              <User className="h-4 w-4" />
              {authorName(thread.author)}
            </span>
            <span className="flex items-center gap-1">
              <Calendar className="h-4 w-4" />
              {new Date(thread.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {isCourseOwner && (
            <>
              <Button variant="outline" size="sm" onClick={handleTogglePin} title={thread.is_pinned ? 'Unpin' : 'Pin'}>
                <Pin className={`h-4 w-4 ${thread.is_pinned ? 'text-primary' : ''}`} />
              </Button>
              <Button variant="outline" size="sm" onClick={handleToggleLock} title={thread.is_locked ? 'Unlock' : 'Lock'}>
                {thread.is_locked ? <Unlock className="h-4 w-4" /> : <Lock className="h-4 w-4" />}
              </Button>
            </>
          )}
          {isThreadAuthor && (
            <Button variant="outline" size="sm" onClick={openEditThread}>
              <Edit className="h-4 w-4" />
            </Button>
          )}
          {(isThreadAuthor || isCourseOwner) && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowDeleteThread(true)}
              className="text-destructive hover:text-destructive"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      {/* Thread Body */}
      <Card className="mb-8">
        <CardContent className={`py-6 ${PROSE}`}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{thread.content}</ReactMarkdown>
        </CardContent>
      </Card>

      {/* Replies */}
      <h2 className="text-lg font-semibold mb-4">
        {thread.replies.length} {thread.replies.length === 1 ? 'Reply' : 'Replies'}
      </h2>

      <div className="space-y-4 mb-8">
        {thread.replies.map((reply) => {
          const isReplyAuthor = user?.id != null && user.id === reply.author.id;
          return (
            <Card key={reply.id}>
              <CardContent className="py-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <User className="h-3 w-3" />
                    <span className="font-medium text-foreground">{authorName(reply.author)}</span>
                    <span>{new Date(reply.created_at).toLocaleDateString()}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    {isReplyAuthor && (
                      <Button variant="ghost" size="sm" onClick={() => startEditReply(reply)}>
                        <Edit className="h-3 w-3" />
                      </Button>
                    )}
                    {(isReplyAuthor || isCourseOwner) && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setDeleteReplyId(reply.id)}
                        className="text-destructive hover:text-destructive"
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                </div>

                {editingReplyId === reply.id ? (
                  <div className="space-y-2">
                    <textarea
                      value={editingReplyContent}
                      onChange={(e) => setEditingReplyContent(e.target.value)}
                      className="w-full min-h-[100px] px-3 py-2 border rounded-md resize-y
                        bg-background text-foreground
                        focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                    />
                    <div className="flex justify-end gap-2">
                      <Button variant="outline" size="sm" onClick={() => setEditingReplyId(null)}>
                        Cancel
                      </Button>
                      <Button size="sm" onClick={handleSaveReply} disabled={!editingReplyContent.trim()}>
                        Save
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className={PROSE}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{reply.content}</ReactMarkdown>
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}

        {thread.replies.length === 0 && (
          <p className="text-muted-foreground text-sm">No replies yet.</p>
        )}
      </div>

      {/* Reply Form */}
      {canReply ? (
        <Card>
          <CardContent className="py-4">
            <label className="block text-sm font-medium mb-2">Post a Reply</label>
            <textarea
              value={replyContent}
              onChange={(e) => setReplyContent(e.target.value)}
              placeholder="Write your reply... (Markdown supported)"
              className="w-full min-h-[120px] px-3 py-2 border rounded-md resize-y
                bg-background text-foreground
                focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
            />
            <div className="flex justify-end mt-2">
              <Button onClick={handleReply} disabled={isReplying || !replyContent.trim()}>
                {isReplying ? 'Posting...' : 'Post Reply'}
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="py-6 text-center text-muted-foreground flex items-center justify-center gap-2">
            <Lock className="h-4 w-4" />
            This thread is locked. New replies are disabled.
          </CardContent>
        </Card>
      )}

      {/* Edit Thread Modal */}
      <Dialog open={showEditModal} onOpenChange={setShowEditModal}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit Thread</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <label className="block text-sm font-medium mb-1">Title</label>
              <Input
                value={editData.title}
                onChange={(e) => setEditData({ ...editData, title: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Message</label>
              <textarea
                value={editData.content}
                onChange={(e) => setEditData({ ...editData, content: e.target.value })}
                className="w-full min-h-[200px] px-3 py-2 border rounded-md resize-y
                  bg-background text-foreground
                  focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditModal(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSaveThread}
              disabled={isSaving || !editData.title.trim() || !editData.content.trim()}
            >
              {isSaving ? 'Saving...' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Thread Dialog */}
      <Dialog open={showDeleteThread} onOpenChange={setShowDeleteThread}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Thread</DialogTitle>
          </DialogHeader>
          <p className="text-muted-foreground">
            Are you sure you want to delete this thread? All replies will be removed. This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDeleteThread(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteThread} disabled={isDeleting}>
              {isDeleting ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Reply Dialog */}
      <Dialog open={deleteReplyId !== null} onOpenChange={() => setDeleteReplyId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Reply</DialogTitle>
          </DialogHeader>
          <p className="text-muted-foreground">
            Are you sure you want to delete this reply? This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteReplyId(null)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDeleteReply}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageContainer>
  );
}
