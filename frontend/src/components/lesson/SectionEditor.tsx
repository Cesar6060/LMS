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
import type { LessonSection } from '@/types';
import {
  Loader2, Plus, Trash2, ChevronUp, ChevronDown,
  FileText, Video, Save
} from 'lucide-react';

interface SectionEditorProps {
  lessonId: number;
  lessonTitle: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
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

export function SectionEditor({
  lessonId,
  lessonTitle,
  open,
  onOpenChange,
}: SectionEditorProps) {
  const [sections, setSections] = useState<LessonSection[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // Edit modal state
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingSection, setEditingSection] = useState<EditingSection | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  useEffect(() => {
    if (open) {
      loadSections();
    }
  }, [open, lessonId]);

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

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Manage Sections</DialogTitle>
            <DialogDescription>
              {lessonTitle} - Organize content into navigable sections
            </DialogDescription>
          </DialogHeader>

          {error && (
            <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-md px-4 py-3 text-sm">
              {error}
            </div>
          )}

          <div className="flex-1 overflow-y-auto py-4">
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
              </div>
            ) : sections.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p className="mb-4">No sections yet. Add your first section to organize lesson content.</p>
                <Button onClick={openAddSection}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Section
                </Button>
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

          <DialogFooter className="border-t pt-4">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Close
            </Button>
            <Button onClick={openAddSection}>
              <Plus className="h-4 w-4 mr-2" />
              Add Section
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
                className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              />
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
    </>
  );
}
