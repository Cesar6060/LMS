import { useState, useEffect } from 'react';
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
import type { LessonSection } from '@/types';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Loader2, Plus, Trash2, ChevronUp, ChevronDown,
  FileText, Video, Save, ClipboardPaste, X
} from 'lucide-react';

interface SectionEditorProps {
  lessonId: number;
  lessonTitle: string;
}

interface EditingSection {
  id?: number;
  title: string;
  content: string;
  video_type: 'none' | 'youtube' | 'vimeo';
  video_id: string;
  order: number;
}

/**
 * Extract YouTube video ID from various URL formats or return the ID if already extracted.
 */
function extractYouTubeVideoId(input: string): string {
  if (!input) return '';
  const trimmed = input.trim();
  const patterns = [
    /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})/,
    /^([a-zA-Z0-9_-]{11})$/,
  ];
  for (const pattern of patterns) {
    const match = trimmed.match(pattern);
    if (match && match[1]) {
      return match[1];
    }
  }
  return trimmed;
}

export function SectionEditor({ lessonId, lessonTitle }: SectionEditorProps) {
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

  useEffect(() => {
    loadSections();
  }, [lessonId]);

  const loadSections = async () => {
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
  };

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

    setIsSaving(true);
    setSaveError('');
    try {
      const data = {
        title: editingSection.title,
        content: editingSection.content,
        video_type: editingSection.video_type,
        video_id: editingSection.video_type === 'youtube'
          ? extractYouTubeVideoId(editingSection.video_id)
          : '',
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
    } catch (err: unknown) {
      console.error('Failed to save section:', err);
      const error = err as { response?: { data?: { error?: string } }; message?: string };
      setSaveError(error.response?.data?.error || error.message || 'Failed to save section');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteSection = async (sectionId: number) => {
    if (!confirm('Are you sure you want to delete this section?')) return;

    try {
      await courseService.deleteLessonSection(lessonId, sectionId);
      await loadSections();
    } catch (err) {
      console.error('Failed to delete section:', err);
    }
  };

  const handleMoveSection = async (index: number, direction: 'up' | 'down') => {
    const newIndex = direction === 'up' ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= sections.length) return;

    const newSections = [...sections];
    [newSections[index], newSections[newIndex]] = [newSections[newIndex], newSections[index]];

    const sectionIds = newSections.map(s => s.id);

    try {
      const reordered = await courseService.reorderLessonSections(lessonId, sectionIds);
      setSections(reordered);
    } catch (err) {
      console.error('Failed to reorder sections:', err);
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
    } catch (err: unknown) {
      console.error('Failed to bulk-create sections:', err);
      const error = err as { response?: { data?: { error?: string; detail?: string } }; message?: string };
      setPasteError(
        error.response?.data?.detail ||
        error.response?.data?.error ||
        error.message ||
        'Failed to add sections'
      );
    } finally {
      setIsBulkSaving(false);
    }
  };

  return (
    <>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Break "{lessonTitle}" into navigable sections (slides).
          </p>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={openPasteModal}>
              <ClipboardPaste className="h-4 w-4 mr-2" />
              Paste to add sections
            </Button>
            <Button size="sm" onClick={openAddSection}>
              <Plus className="h-4 w-4 mr-2" />
              Add Section
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
              <div className="text-center py-12 text-muted-foreground">
                <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p className="mb-4">No sections yet. Add your first section to organize lesson content.</p>
                <div className="flex items-center justify-center gap-2">
                  <Button variant="outline" onClick={openPasteModal}>
                    <ClipboardPaste className="h-4 w-4 mr-2" />
                    Paste to add sections
                  </Button>
                  <Button onClick={openAddSection}>
                    <Plus className="h-4 w-4 mr-2" />
                    Add Section
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
                              Section {index + 1}
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
              {editingSection?.id ? 'Edit Section' : 'Add Section'}
            </DialogTitle>
            <DialogDescription>
              {editingSection?.id
                ? 'Update the section content.'
                : 'Create a new section for this lesson.'}
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
                Section Title (optional)
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
                      ? { ...prev, video_type: e.target.value as 'none' | 'youtube' | 'vimeo' }
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
              </div>
            )}

            <div className="space-y-2">
              <label htmlFor="section-content" className="text-sm font-medium">
                Content (Markdown)
              </label>
              <div className="grid gap-4 lg:grid-cols-2">
                <textarea
                  id="section-content"
                  placeholder="Write section content using Markdown..."
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
            <DialogTitle>Paste to add sections</DialogTitle>
            <DialogDescription>
              Paste one markdown document and split it into sections. Separate
              sections with a line containing only <code>---</code>. Each section
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
                placeholder={'## Section one\n\nSome content...\n\n---\n\n## Section two\n\nMore content...'}
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
                    Nothing to add — the pasted text produced no sections.
                  </p>
                ) : (
                  <>
                    <p className="text-sm font-medium">
                      {previewCards.length} section{previewCards.length === 1 ? '' : 's'} to add
                    </p>
                    {previewCards.map((card, index) => (
                      <Card key={index} className="overflow-hidden">
                        <CardContent className="p-4 space-y-3">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-muted-foreground whitespace-nowrap">
                              Section {index + 1}
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
                              title="Remove this section"
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
