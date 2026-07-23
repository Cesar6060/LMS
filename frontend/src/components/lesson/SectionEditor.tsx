import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardContent } from '@/components/ui/Card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/Dialog';
import { courseService } from '@/services/courses';
import { splitSections } from '@/lib/splitSections';
import { extractYouTubeVideoId } from '@/lib/video';
import { YouTubeVideoPreview } from '@/components/lesson/YouTubeVideoPreview';
import type { LessonSection } from '@/types';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Loader2, Plus, Trash2, ChevronUp, ChevronDown,
  FileText, Video, Save, ClipboardPaste, X
} from 'lucide-react';

export type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

interface SectionEditorProps {
  lessonId: number;
  lessonTitle: string;
  /** Report save activity up to the page-level status indicator. */
  onSaveStatus?: (status: SaveStatus, message?: string) => void;
}

interface EditingSection {
  id?: number;
  title: string;
  content: string;
  video_type: 'none' | 'youtube';
  video_id: string;
  order: number;
}

export function SectionEditor({ lessonId, lessonTitle, onSaveStatus }: SectionEditorProps) {
  const report = useCallback(
    (status: SaveStatus, message?: string) => onSaveStatus?.(status, message),
    [onSaveStatus]
  );
  const [sections, setSections] = useState<LessonSection[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // Edit modal state
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingSection, setEditingSection] = useState<EditingSection | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  // Paste-to-split modal state
  const [showPasteModal, setShowPasteModal] = useState(false);
  const [pasteText, setPasteText] = useState('');
  const [previewCards, setPreviewCards] = useState<Array<{ title: string; content: string }>>([]);
  const [hasPreviewed, setHasPreviewed] = useState(false);
  const [isBulkSaving, setIsBulkSaving] = useState(false);
  const [pasteError, setPasteError] = useState('');

  const loadSections = useCallback(async () => {
    try {
      setIsLoading(true);
      setError('');
      const data = await courseService.getLessonSections(lessonId);
      setSections(data);
    } catch (err) {
      console.error('Failed to load sections:', err);
      setError('Failed to load sections');
    } finally {
      setIsLoading(false);
    }
  }, [lessonId]);

  useEffect(() => {
    loadSections();
  }, [loadSections]);

  const openAddSection = () => {
    const nextOrder = sections.length > 0 ? Math.max(...sections.map(s => s.order)) + 1 : 0;
    setEditingSection({
      title: '',
      content: '',
      video_type: 'none',
      video_id: '',
      order: nextOrder,
    });
    setSaveError('');
    setShowEditModal(true);
  };

  const openEditSection = (section: LessonSection) => {
    setEditingSection({
      id: section.id,
      title: section.title,
      content: section.content,
      video_type: section.video_type,
      video_id: section.video_id,
      order: section.order,
    });
    setSaveError('');
    setShowEditModal(true);
  };

  const handleSaveSection = async () => {
    if (!editingSection) return;

    let videoId = '';
    if (editingSection.video_type === 'youtube') {
      const extracted = extractYouTubeVideoId(editingSection.video_id);
      if (!extracted) {
        setSaveError(
          'Could not extract a YouTube video ID from the video field. ' +
          'Fix the link or set Video Type to "No Video" before saving.'
        );
        return;
      }
      videoId = extracted;
    }

    setIsSaving(true);
    setSaveError('');
    report('saving');
    try {
      const data = {
        title: editingSection.title,
        content: editingSection.content,
        video_type: editingSection.video_type,
        video_id: videoId,
        order: editingSection.order,
      };

      if (editingSection.id) {
        await courseService.updateLessonSection(lessonId, editingSection.id, data);
      } else {
        await courseService.createLessonSection(lessonId, data);
      }

      await loadSections();
      setShowEditModal(false);
      setEditingSection(null);
      report('saved');
    } catch (err: unknown) {
      console.error('Failed to save section:', err);
      const error = err as { response?: { data?: { error?: string } }; message?: string };
      const message = error.response?.data?.error || error.message || 'Failed to save section';
      setSaveError(message);
      report('error', message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteSection = async (sectionId: number) => {
    if (!confirm('Are you sure you want to delete this section?')) return;

    report('saving');
    try {
      await courseService.deleteLessonSection(lessonId, sectionId);
      await loadSections();
      report('saved');
    } catch (err) {
      console.error('Failed to delete section:', err);
      report('error', 'Failed to delete section');
    }
  };

  const handleMoveSection = async (index: number, direction: 'up' | 'down') => {
    const newIndex = direction === 'up' ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= sections.length) return;

    const newSections = [...sections];
    [newSections[index], newSections[newIndex]] = [newSections[newIndex], newSections[index]];

    const sectionIds = newSections.map(s => s.id);

    report('saving');
    try {
      const reordered = await courseService.reorderLessonSections(lessonId, sectionIds);
      setSections(reordered);
      report('saved');
    } catch (err) {
      console.error('Failed to reorder sections:', err);
      report('error', 'Failed to reorder sections');
    }
  };

  const openPasteModal = () => {
    setPasteText('');
    setPreviewCards([]);
    setHasPreviewed(false);
    setPasteError('');
    setShowPasteModal(true);
  };

  const handlePreviewSplit = () => {
    setPasteError('');
    setPreviewCards(splitSections(pasteText));
    setHasPreviewed(true);
  };

  const updatePreviewCard = (index: number, field: 'title' | 'content', value: string) => {
    setPreviewCards(prev =>
      prev.map((card, i) => (i === index ? { ...card, [field]: value } : card))
    );
  };

  const removePreviewCard = (index: number) => {
    setPreviewCards(prev => prev.filter((_, i) => i !== index));
  };

  const handleBulkSave = async () => {
    if (previewCards.length === 0) return;

    setIsBulkSaving(true);
    setPasteError('');
    report('saving');
    try {
      await courseService.bulkCreateLessonSections(
        lessonId,
        previewCards.map(card => ({
          title: card.title,
          content: card.content,
          video_type: 'none' as const,
          video_id: '',
        }))
      );
      await loadSections();
      setShowPasteModal(false);
      report('saved');
    } catch (err: unknown) {
      console.error('Failed to bulk-create sections:', err);
      const error = err as { response?: { data?: { error?: string; detail?: string } }; message?: string };
      const message =
        error.response?.data?.detail ||
        error.response?.data?.error ||
        error.message ||
        'Failed to add pages';
      setPasteError(message);
      report('error', message);
    } finally {
      setIsBulkSaving(false);
    }
  };

  return (
    <>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-base text-muted-foreground">
            Pages are the content of "{lessonTitle}". Each page holds text and an
            optional video; students step through them in order.
          </p>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={openPasteModal}>
              <ClipboardPaste className="h-4 w-4 mr-2" />
              Paste to add pages
            </Button>
            <Button size="sm" onClick={openAddSection}>
              <Plus className="h-4 w-4 mr-2" />
              Add Page
            </Button>
          </div>
        </div>

        {error && (
          <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-md px-4 py-3 text-sm">
            {error}
          </div>
        )}

        <div>
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : sections.length === 0 ? (
              <div className="text-center py-16 border-2 border-dashed rounded-lg">
                <FileText className="h-14 w-14 mx-auto mb-4 opacity-40" />
                <h3 className="text-lg font-semibold mb-1">This lesson has no content yet</h3>
                <p className="mb-6 text-muted-foreground">
                  Add your first page to start building the lesson.
                </p>
                <div className="flex items-center justify-center gap-3">
                  <Button variant="outline" size="lg" onClick={openPasteModal}>
                    <ClipboardPaste className="h-4 w-4 mr-2" />
                    Paste to add pages
                  </Button>
                  <Button size="lg" onClick={openAddSection}>
                    <Plus className="h-4 w-4 mr-2" />
                    Add your first page
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {sections.map((section, index) => (
                  <Card key={section.id} className="overflow-hidden">
                    <CardContent className="p-4">
                      <div className="flex items-center gap-3">
                        {/* Reorder buttons */}
                        <div className="flex flex-col items-center gap-0.5">
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0"
                            onClick={() => handleMoveSection(index, 'up')}
                            disabled={index === 0}
                            title="Move up"
                          >
                            <ChevronUp className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0"
                            onClick={() => handleMoveSection(index, 'down')}
                            disabled={index === sections.length - 1}
                            title="Move down"
                          >
                            <ChevronDown className="h-4 w-4" />
                          </Button>
                        </div>

                        {/* Section info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-sm font-medium text-muted-foreground">
                              Page {index + 1}
                            </span>
                            {section.video_type !== 'none' && (
                              <Video className="h-4 w-4 text-muted-foreground" />
                            )}
                          </div>
                          <h4 className="font-medium truncate">
                            {section.title || '(No title)'}
                          </h4>
                          <p className="text-sm text-muted-foreground truncate">
                            {section.content
                              ? `${section.content.slice(0, 100)}...`
                              : '(No content)'}
                          </p>
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditSection(section)}
                          >
                            Edit
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive hover:text-destructive"
                            onClick={() => handleDeleteSection(section.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
        </div>
      </div>

      {/* Edit Section Modal */}
      <Dialog open={showEditModal} onOpenChange={setShowEditModal}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>
              {editingSection?.id ? 'Edit Page' : 'Add Page'}
            </DialogTitle>
            <DialogDescription>
              {editingSection?.id
                ? 'Update the page content.'
                : 'Create a new page for this lesson.'}
            </DialogDescription>
          </DialogHeader>

          {saveError && (
            <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-md px-4 py-3 text-sm">
              {saveError}
            </div>
          )}

          <div className="flex-1 overflow-y-auto py-4 space-y-4">
            <div className="space-y-2">
              <label htmlFor="section-title" className="text-sm font-medium">
                Page Title (optional)
              </label>
              <Input
                id="section-title"
                type="text"
                placeholder="e.g., Introduction, Getting Started..."
                value={editingSection?.title || ''}
                onChange={(e) =>
                  setEditingSection(prev =>
                    prev ? { ...prev, title: e.target.value } : null
                  )
                }
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="section-video-type" className="text-sm font-medium">
                Video Type
              </label>
              <select
                id="section-video-type"
                value={editingSection?.video_type || 'none'}
                onChange={(e) =>
                  setEditingSection(prev =>
                    prev
                      ? { ...prev, video_type: e.target.value as 'none' | 'youtube' }
                      : null
                  )
                }
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                <option value="none">No Video</option>
                <option value="youtube">YouTube</option>
              </select>
            </div>

            {editingSection?.video_type === 'youtube' && (
              <div className="space-y-2">
                <label htmlFor="section-video-id" className="text-sm font-medium">
                  YouTube URL or Video ID
                </label>
                <Input
                  id="section-video-id"
                  type="text"
                  placeholder="Paste YouTube URL or video ID"
                  value={editingSection?.video_id || ''}
                  onChange={(e) =>
                    setEditingSection(prev =>
                      prev ? { ...prev, video_id: e.target.value } : null
                    )
                  }
                />
                <YouTubeVideoPreview input={editingSection?.video_id || ''} />
              </div>
            )}

            <div className="space-y-2">
              <label htmlFor="section-content" className="text-sm font-medium">
                Content (Markdown)
              </label>
              <div className="grid gap-4 lg:grid-cols-2">
                <textarea
                  id="section-content"
                  placeholder="Write page content using Markdown..."
                  value={editingSection?.content || ''}
                  onChange={(e) =>
                    setEditingSection(prev =>
                      prev ? { ...prev, content: e.target.value } : null
                    )
                  }
                  rows={12}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-y"
                />
                <Card className="overflow-y-auto max-h-[320px]">
                  <CardContent className="prose prose-neutral dark:prose-invert max-w-none py-4">
                    {editingSection?.content ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {editingSection.content}
                      </ReactMarkdown>
                    ) : (
                      <p className="text-muted-foreground not-prose text-sm">
                        Preview appears here as you type.
                      </p>
                    )}
                  </CardContent>
                </Card>
              </div>
              <p className="text-xs text-muted-foreground">
                Supports GitHub Flavored Markdown (headers, lists, code blocks, links, etc.)
              </p>
            </div>
          </div>

          <DialogFooter className="border-t pt-4">
            <Button
              variant="outline"
              onClick={() => setShowEditModal(false)}
              disabled={isSaving}
            >
              Cancel
            </Button>
            <Button onClick={handleSaveSection} disabled={isSaving}>
              {isSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              <Save className="h-4 w-4 mr-2" />
              Save Section
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Paste-to-split Modal */}
      <Dialog open={showPasteModal} onOpenChange={setShowPasteModal}>
        <DialogContent className="max-w-4xl max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Paste to add pages</DialogTitle>
            <DialogDescription>
              Paste one markdown document and split it into pages. Separate
              pages with a line containing only <code>---</code>. Each page
              is auto-titled from its first heading.
            </DialogDescription>
          </DialogHeader>

          {pasteError && (
            <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-md px-4 py-3 text-sm">
              {pasteError}
            </div>
          )}

          <div className="flex-1 overflow-y-auto py-4 space-y-4">
            <div className="space-y-2">
              <label htmlFor="paste-text" className="text-sm font-medium">
                Pasted Markdown
              </label>
              <textarea
                id="paste-text"
                placeholder={'## Page one\n\nSome content...\n\n---\n\n## Page two\n\nMore content...'}
                value={pasteText}
                onChange={(e) => setPasteText(e.target.value)}
                rows={10}
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-y"
              />
              <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground">
                  A <code>---</code> inside a code fence does not split.
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePreviewSplit}
                  disabled={pasteText.trim() === ''}
                >
                  Preview split
                </Button>
              </div>
            </div>

            {hasPreviewed && (
              <div className="space-y-3">
                {previewCards.length === 0 ? (
                  <p className="text-sm text-muted-foreground text-center py-6">
                    Nothing to add — the pasted text produced no pages.
                  </p>
                ) : (
                  <>
                    <p className="text-sm font-medium">
                      {previewCards.length} page{previewCards.length === 1 ? '' : 's'} to add
                    </p>
                    {previewCards.map((card, index) => (
                      <Card key={index} className="overflow-hidden">
                        <CardContent className="p-4 space-y-3">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">
                              Page {index + 1}
                            </span>
                            <Input
                              type="text"
                              placeholder="Title (optional)"
                              value={card.title}
                              onChange={(e) => updatePreviewCard(index, 'title', e.target.value)}
                            />
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-8 w-8 p-0 text-destructive hover:text-destructive shrink-0"
                              onClick={() => removePreviewCard(index)}
                              title="Remove this page"
                            >
                              <X className="h-4 w-4" />
                            </Button>
                          </div>
                          <div className="grid gap-3 lg:grid-cols-2">
                            <textarea
                              value={card.content}
                              onChange={(e) => updatePreviewCard(index, 'content', e.target.value)}
                              rows={6}
                              className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-y"
                            />
                            <Card className="overflow-y-auto max-h-[200px]">
                              <CardContent className="prose prose-neutral dark:prose-invert max-w-none py-3 text-sm">
                                {card.content ? (
                                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                    {card.content}
                                  </ReactMarkdown>
                                ) : (
                                  <p className="text-muted-foreground not-prose text-sm">
                                    (No content)
                                  </p>
                                )}
                              </CardContent>
                            </Card>
                          </div>
                        </CardContent>
                      </Card>
                    ))}
                  </>
                )}
              </div>
            )}
          </div>

          <DialogFooter className="border-t pt-4">
            <Button
              variant="outline"
              onClick={() => setShowPasteModal(false)}
              disabled={isBulkSaving}
            >
              Cancel
            </Button>
            <Button
              onClick={handleBulkSave}
              disabled={isBulkSaving || previewCards.length === 0}
            >
              {isBulkSaving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              <Plus className="h-4 w-4 mr-2" />
              Add {previewCards.length} section{previewCards.length === 1 ? '' : 's'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
