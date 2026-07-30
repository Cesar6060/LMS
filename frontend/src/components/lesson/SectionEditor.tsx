import { useState, useEffect, useCallback, useRef } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardContent } from '@/components/ui/Card';
import { ProgressBar } from '@/components/ui/ProgressBar';
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
import type { RenderedSlide } from '@/lib/pdfSlides';
import { uploadSlideTasks, MAX_PDF_BYTES, MAX_PDF_PAGES } from '@/lib/slideImport';
import type { SlideUploadTask } from '@/lib/slideImport';
import { extractYouTubeVideoId } from '@/lib/video';
import { YouTubeVideoPreview } from '@/components/lesson/YouTubeVideoPreview';
import { useToast } from '@/contexts/useToast';
import type { LessonSection } from '@/types';
import { LessonMarkdown } from '@/components/lesson/LessonMarkdown';
import { useDebounce } from '@/hooks/useDebounce';
import { cn } from '@/lib/utils';
import {
  Loader2, Plus, Trash2, ChevronUp, ChevronDown,
  FileText, Video, Save, ClipboardPaste, X, Presentation,
  Upload, ListPlus, CheckCircle2, AlertCircle
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
  layout: 'doc' | 'slide';
  /** Phase 61 — read-only here; set only by the slide-import endpoint. */
  image_url: string | null;
  image_alt: string;
  order: number;
}

/** Phase 61 — one rendered PDF page inside the import modal. */
interface ImportPage {
  /** 1-based PDF page number (stable identity across deselect/retry). */
  pageNumber: number;
  /** Object URL for the preview grid (revoked when the modal closes). */
  previewUrl: string;
  slide: RenderedSlide;
  selected: boolean;
  status: 'pending' | 'uploading' | 'done' | 'failed';
  /** Assigned when the first upload run starts; stable across retries. */
  title?: string;
}

type ImportPhase = 'pick' | 'rendering' | 'preview' | 'uploading';

/** Milliseconds a preview waits after the last keystroke before re-rendering. */
const PREVIEW_DEBOUNCE_MS = 200;

interface DebouncedPreviewProps {
  content: string;
  /** Extra prose classes, e.g. `prose-lg` for the slide mini stage. */
  className?: string;
  /** Shown while the debounced content is empty. */
  emptyText: string;
}

/**
 * Phase 62 — a preview that re-renders markdown (and highlight.js) only after
 * typing pauses, while its textarea stays fully controlled off the live state so
 * keystrokes remain instant. It exists as a component rather than a hook call in
 * the editor body because the paste modal needs one per card, and hooks cannot
 * be called inside `previewCards.map()`.
 *
 * Key it by the thing being edited where a stable id exists: the debounced state
 * lives inside, so swapping the content prop on a surviving instance shows the
 * previous content for one debounce interval. The paste cards have no id and are
 * keyed by index, so removing a card mid-typing does flash the removed card's
 * markdown in that slot for ~200ms before it self-corrects.
 */
function DebouncedMarkdownPreview({ content, className, emptyText }: DebouncedPreviewProps) {
  const debouncedContent = useDebounce(content, PREVIEW_DEBOUNCE_MS);

  if (!debouncedContent) {
    return <p className="text-muted-foreground text-sm">{emptyText}</p>;
  }

  return <LessonMarkdown content={debouncedContent} className={className} />;
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

  // Insert-below (phase 61): index of the row the new page goes under, or
  // null for a plain append via "Add Page".
  const [insertAfterIndex, setInsertAfterIndex] = useState<number | null>(null);

  // Slide-import modal state (phase 61)
  const toast = useToast();
  const [showImportModal, setShowImportModal] = useState(false);
  const [importPhase, setImportPhase] = useState<ImportPhase>('pick');
  const [importError, setImportError] = useState('');
  const [importPages, setImportPages] = useState<ImportPage[]>([]);
  const [renderedCount, setRenderedCount] = useState(0);
  const [renderTotal, setRenderTotal] = useState(0);
  const [uploadCurrent, setUploadCurrent] = useState(0);
  const [uploadTotal, setUploadTotal] = useState(0);
  const importAbortRef = useRef<AbortController | null>(null);
  const renderCancelledRef = useRef(false);
  const importFileInputRef = useRef<HTMLInputElement>(null);

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
      layout: 'doc',
      image_url: null,
      image_alt: '',
      order: nextOrder,
    });
    setInsertAfterIndex(null);
    setSaveError('');
    setShowEditModal(true);
  };

  // Phase 61: add a page directly under a row. The new page inherits the
  // anchor row's layout, so a page added between slides is a slide-stage
  // page and a page added below a doc is a doc.
  const openInsertBelow = (index: number) => {
    const anchor = sections[index];
    const nextOrder = sections.length > 0 ? Math.max(...sections.map(s => s.order)) + 1 : 0;
    setEditingSection({
      title: '',
      content: '',
      video_type: 'none',
      video_id: '',
      layout: anchor.layout,
      image_url: null,
      image_alt: '',
      order: nextOrder,
    });
    setInsertAfterIndex(index);
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
      layout: section.layout,
      image_url: section.image_url,
      image_alt: section.image_alt,
      order: section.order,
    });
    setInsertAfterIndex(null);
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
        layout: editingSection.layout,
        image_alt: editingSection.image_alt,
        order: editingSection.order,
      };

      if (editingSection.id) {
        await courseService.updateLessonSection(lessonId, editingSection.id, data);
      } else {
        const created = await courseService.createLessonSection(lessonId, data);
        // Insert-below (phase 61): the create appended the page; slot it
        // after its anchor row with a full-permutation reorder.
        if (insertAfterIndex !== null && insertAfterIndex < sections.length) {
          const ids = sections.map(s => s.id);
          ids.splice(insertAfterIndex + 1, 0, created.id);
          await courseService.reorderLessonSections(lessonId, ids);
        }
      }

      await loadSections();
      setShowEditModal(false);
      setEditingSection(null);
      setInsertAfterIndex(null);
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

  // Phase 60: flip a page between Document and Slide straight from its row.
  const handleLayoutChange = async (section: LessonSection, layout: 'doc' | 'slide') => {
    if (section.layout === layout) return;

    report('saving');
    try {
      const updated = await courseService.updateLessonSection(lessonId, section.id, {
        title: section.title,
        content: section.content,
        video_type: section.video_type,
        video_id: section.video_id,
        layout,
        image_alt: section.image_alt,
        order: section.order,
      });
      setSections(prev => prev.map(s => (s.id === updated.id ? updated : s)));
      report('saved');
    } catch (err) {
      console.error('Failed to change page layout:', err);
      report('error', 'Failed to change page layout');
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

  // ---- Slide import (phase 61) -------------------------------------------

  const resetImportState = useCallback(() => {
    importAbortRef.current?.abort();
    importAbortRef.current = null;
    // Signals an in-flight render loop to stop and clean up after itself;
    // closing the modal mid-render must not keep rasterizing into state that
    // no longer has a home.
    renderCancelledRef.current = true;
    setImportPages(prev => {
      prev.forEach(p => URL.revokeObjectURL(p.previewUrl));
      return [];
    });
    setImportPhase('pick');
    setImportError('');
    setRenderedCount(0);
    setRenderTotal(0);
    setUploadCurrent(0);
    setUploadTotal(0);
  }, []);

  // Revoke any preview URLs still alive if the editor unmounts with the
  // modal open.
  useEffect(() => resetImportState, [resetImportState]);

  const openImportModal = () => {
    resetImportState();
    setShowImportModal(true);
  };

  const closeImportModal = useCallback((didImportAny: boolean) => {
    setShowImportModal(false);
    resetImportState();
    if (didImportAny) {
      loadSections();
    }
  }, [resetImportState, loadSections]);

  const handlePdfPicked = async (file: File | null | undefined) => {
    if (!file) return;
    setImportError('');

    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setImportError('Please choose a PDF file (export your deck to PDF first).');
      return;
    }
    if (file.size > MAX_PDF_BYTES) {
      setImportError(`"${file.name}" exceeds the ${MAX_PDF_BYTES / (1024 * 1024)} MB limit.`);
      return;
    }

    setImportPhase('rendering');
    renderCancelledRef.current = false;
    const pages: ImportPage[] = [];
    try {
      // pdf.js is loaded on demand — see the comment in pdfSlides.ts.
      const { loadDeck } = await import('@/lib/pdfSlides');
      const deck = await loadDeck(file);
      try {
        setRenderTotal(deck.numPages);
        setRenderedCount(0);
        for (let n = 1; n <= deck.numPages; n++) {
          if (renderCancelledRef.current) break;
          const slide = await deck.renderPage(n);
          pages.push({
            pageNumber: n,
            previewUrl: URL.createObjectURL(slide.blob),
            slide,
            selected: true,
            status: 'pending',
          });
          setRenderedCount(n);
        }
        if (renderCancelledRef.current) {
          pages.forEach(p => URL.revokeObjectURL(p.previewUrl));
          return;
        }
        setImportPages(pages);
        setImportPhase('preview');
      } finally {
        deck.destroy();
      }
    } catch (err: unknown) {
      // Pages rendered before the failure never reach state, so revoke their
      // object URLs here or nothing ever will.
      pages.forEach(p => URL.revokeObjectURL(p.previewUrl));
      const message = err instanceof Error ? err.message : 'Could not read this PDF.';
      setImportError(message);
      setImportPhase('pick');
    } finally {
      if (importFileInputRef.current) {
        importFileInputRef.current.value = '';
      }
    }
  };

  const togglePageSelected = (pageNumber: number) => {
    setImportPages(prev =>
      prev.map(p => (p.pageNumber === pageNumber ? { ...p, selected: !p.selected } : p))
    );
  };

  /** Upload every selected page still pending or failed, one at a time. */
  const runImport = async () => {
    // Titles are assigned once, on the first run — "Slide 1..N" over the
    // selected pages — and stay stable across retries.
    let titleCounter = 0;
    const withTitles = importPages.map(p => {
      if (!p.selected) return p;
      titleCounter += 1;
      return { ...p, title: p.title ?? `Slide ${titleCounter}` };
    });

    const toUpload = withTitles.filter(
      p => p.selected && (p.status === 'pending' || p.status === 'failed')
    );
    if (toUpload.length === 0) return;

    const tasks: SlideUploadTask[] = toUpload.map(p => ({
      pageNumber: p.pageNumber,
      title: p.title ?? `Slide ${p.pageNumber}`,
      blob: p.slide.blob,
      ext: p.slide.ext,
      altText: p.slide.altText,
    }));

    const abort = new AbortController();
    importAbortRef.current = abort;
    setImportPages(withTitles);
    setImportPhase('uploading');
    setImportError('');
    setUploadTotal(tasks.length);
    setUploadCurrent(0);
    report('saving');

    const setPageStatus = (pageNumber: number, status: ImportPage['status']) => {
      setImportPages(prev =>
        prev.map(p => (p.pageNumber === pageNumber ? { ...p, status } : p))
      );
    };

    // Deterministic failures (oversize, demo_blocked, throttled) will repeat
    // on every retry, so show the server's reason rather than only "retry".
    let firstFailure = '';
    const failureMessage = (err: unknown) => {
      const e = err as {
        response?: { data?: { error?: string; detail?: string } };
        message?: string;
      };
      return e.response?.data?.error || e.response?.data?.detail || e.message || '';
    };

    const result = await uploadSlideTasks(
      tasks,
      task =>
        courseService.importSlideSection(lessonId, {
          image: task.blob,
          filename: `${task.title.replace(/[^\w-]+/g, '-') || 'slide'}.${task.ext}`,
          title: task.title,
          imageAlt: task.altText,
        }),
      {
        signal: abort.signal,
        onPageStart: (task, index) => {
          setUploadCurrent(index + 1);
          setPageStatus(task.pageNumber, 'uploading');
        },
        onPageDone: task => setPageStatus(task.pageNumber, 'done'),
        onPageFailed: (task, err) => {
          firstFailure ||= failureMessage(err);
          setPageStatus(task.pageNumber, 'failed');
        },
      }
    );

    importAbortRef.current = null;
    const doneCount = importPages.filter(p => p.status === 'done').length + result.succeeded.length;

    if (result.failed.length === 0 && !result.aborted) {
      report('saved');
      toast.show({
        message: `Imported ${doneCount} slide${doneCount === 1 ? '' : 's'}`,
        variant: 'success',
      });
      closeImportModal(doneCount > 0);
    } else {
      setImportPhase('preview');
      if (result.aborted) {
        report('saved');
        setImportError(
          `Import cancelled — ${doneCount} slide${doneCount === 1 ? '' : 's'} imported so far. ` +
          'Use "Retry remaining" to finish, or close to keep what was imported.'
        );
      } else {
        report('error', 'Some slides failed to upload');
        setImportError(
          `${result.failed.length} slide${result.failed.length === 1 ? '' : 's'} failed to upload` +
          (firstFailure ? ` (${firstFailure})` : '') +
          '. What succeeded has been kept — use "Retry remaining" to finish.'
        );
      }
      // The lesson already grew behind the modal; keep the editor in sync.
      loadSections();
    }
  };

  const importedCount = importPages.filter(p => p.status === 'done').length;
  const failedCount = importPages.filter(p => p.status === 'failed').length;
  const remainingCount = importPages.filter(
    p => p.selected && (p.status === 'pending' || p.status === 'failed')
  ).length;

  return (
    <>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-base text-muted-foreground">
            Pages are the content of "{lessonTitle}". Each page holds text and an
            optional video; students step through them in order.
          </p>
          <div className="flex items-center gap-2">
            <Button size="sm" variant="outline" onClick={openImportModal}>
              <Upload className="h-4 w-4 mr-2" />
              Import slides (PDF)
            </Button>
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

                        {/* Slide thumbnail (phase 61: imported image slides) */}
                        {section.image_url && (
                          <img
                            src={section.image_url}
                            alt={section.image_alt}
                            className="h-14 w-24 shrink-0 rounded-md border object-cover"
                          />
                        )}

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
                              : section.image_url
                                ? '(Imported slide image)'
                                : '(No content)'}
                          </p>
                        </div>

                        {/* Layout toggle (phase 60): how the player renders
                            this page — scrolling document or slide stage */}
                        <div
                          className="flex items-center rounded-md border overflow-hidden shrink-0"
                          role="group"
                          aria-label={`Page ${index + 1} layout`}
                        >
                          <Button
                            variant={section.layout === 'doc' ? 'default' : 'ghost'}
                            size="sm"
                            className="rounded-none gap-1.5"
                            onClick={() => handleLayoutChange(section, 'doc')}
                            aria-pressed={section.layout === 'doc'}
                            title="Render as a scrolling document"
                          >
                            <FileText className="h-4 w-4" />
                            Doc
                          </Button>
                          <Button
                            variant={section.layout === 'slide' ? 'default' : 'ghost'}
                            size="sm"
                            className="rounded-none gap-1.5"
                            onClick={() => handleLayoutChange(section, 'slide')}
                            aria-pressed={section.layout === 'slide'}
                            title="Render as a slide"
                          >
                            <Presentation className="h-4 w-4" />
                            Slide
                          </Button>
                        </div>

                        {/* Actions */}
                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openInsertBelow(index)}
                            title="Insert page below"
                            aria-label={`Insert page below page ${index + 1}`}
                          >
                            <ListPlus className="h-4 w-4" />
                          </Button>
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
              <span className="text-sm font-medium">Page Layout</span>
              <div
                className="flex items-center rounded-md border overflow-hidden w-fit"
                role="group"
                aria-label="Page layout"
              >
                <Button
                  type="button"
                  variant={editingSection?.layout === 'doc' ? 'default' : 'ghost'}
                  size="sm"
                  className="rounded-none gap-1.5"
                  onClick={() =>
                    setEditingSection(prev => (prev ? { ...prev, layout: 'doc' } : null))
                  }
                  aria-pressed={editingSection?.layout === 'doc'}
                >
                  <FileText className="h-4 w-4" />
                  Document
                </Button>
                <Button
                  type="button"
                  variant={editingSection?.layout === 'slide' ? 'default' : 'ghost'}
                  size="sm"
                  className="rounded-none gap-1.5"
                  onClick={() =>
                    setEditingSection(prev => (prev ? { ...prev, layout: 'slide' } : null))
                  }
                  aria-pressed={editingSection?.layout === 'slide'}
                >
                  <Presentation className="h-4 w-4" />
                  Slide
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Documents scroll like today's pages; slides render on a big
                centered stage with larger type.
              </p>
            </div>

            {editingSection?.image_url && (
              <div className="space-y-2">
                <span className="text-sm font-medium">Slide Image</span>
                <img
                  src={editingSection.image_url}
                  alt={editingSection.image_alt}
                  className="w-full max-h-64 rounded-md border object-contain bg-muted/40"
                />
                <label htmlFor="section-image-alt" className="text-sm font-medium block pt-1">
                  Image alt text
                </label>
                <textarea
                  id="section-image-alt"
                  placeholder="Describe this slide for screen readers and search..."
                  value={editingSection.image_alt}
                  onChange={(e) =>
                    setEditingSection(prev =>
                      prev ? { ...prev, image_alt: e.target.value } : null
                    )
                  }
                  rows={3}
                  className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 resize-y"
                />
                <p className="text-xs text-muted-foreground">
                  Pre-filled from the PDF's text layer. Image slides aren't
                  otherwise selectable or searchable, so this is what screen
                  readers announce.
                </p>
              </div>
            )}

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
                  {editingSection?.layout === 'slide' ? (
                    /* Preview as slide (phase 60): mini stage with the same
                       styling students see in the player */
                    <CardContent className="p-3 h-full bg-muted/40">
                      <div className="rounded-lg border bg-card shadow-md px-6 py-5 min-h-full">
                        {editingSection.title && (
                          <h3 className="text-2xl font-bold tracking-tight mb-4">
                            {editingSection.title}
                          </h3>
                        )}
                        <DebouncedMarkdownPreview
                          key={editingSection.id}
                          content={editingSection.content}
                          className="prose-lg"
                          emptyText="Preview appears here as you type."
                        />
                      </div>
                    </CardContent>
                  ) : (
                    <CardContent className="py-4">
                      <DebouncedMarkdownPreview
                        key={editingSection?.id}
                        content={editingSection?.content || ''}
                        emptyText="Preview appears here as you type."
                      />
                    </CardContent>
                  )}
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
                              <CardContent className="py-3">
                                <DebouncedMarkdownPreview
                                  content={card.content}
                                  className="prose-sm"
                                  emptyText="(No content)"
                                />
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

      {/* Slide Import Modal (phase 61) */}
      <Dialog
        open={showImportModal}
        onOpenChange={(open) => {
          if (!open) {
            // Block closing mid-upload (Cancel first); otherwise keep what
            // was imported and refresh the list if anything landed.
            if (importPhase === 'uploading') return;
            closeImportModal(importedCount > 0);
          }
        }}
      >
        <DialogContent className="max-w-4xl max-h-[85vh] overflow-hidden flex flex-col">
          <DialogHeader>
            <DialogTitle>Import slides (PDF)</DialogTitle>
            <DialogDescription>
              Export your deck (PowerPoint, Google Slides, Canva) to PDF and
              upload it here. Each page becomes a slide page at the end of
              this lesson.
            </DialogDescription>
          </DialogHeader>

          {importError && (
            <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-md px-4 py-3 text-sm">
              {importError}
            </div>
          )}

          <div className="flex-1 overflow-y-auto py-4 space-y-4">
            {importPhase === 'pick' && (
              <div
                className="border-2 border-dashed rounded-lg p-10 text-center transition-colors cursor-pointer hover:border-primary/50"
                onClick={() => importFileInputRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  handlePdfPicked(e.dataTransfer.files?.[0]);
                }}
              >
                <input
                  ref={importFileInputRef}
                  type="file"
                  className="hidden"
                  accept=".pdf,application/pdf"
                  onChange={(e) => handlePdfPicked(e.target.files?.[0])}
                />
                <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
                <p className="text-sm font-medium">
                  Drop a PDF here, or click to choose one
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Max {MAX_PDF_BYTES / (1024 * 1024)} MB, {MAX_PDF_PAGES} pages.
                  Slides are rendered in your browser — nothing is uploaded
                  until you confirm.
                </p>
              </div>
            )}

            {importPhase === 'rendering' && (
              <div className="py-10 text-center space-y-4">
                <Loader2 className="h-8 w-8 mx-auto animate-spin text-primary" />
                <p className="text-sm font-medium">
                  Rendering page {Math.min(renderedCount + 1, renderTotal)} of {renderTotal}…
                </p>
                <ProgressBar
                  value={renderTotal > 0 ? (renderedCount / renderTotal) * 100 : 0}
                  className="max-w-md mx-auto"
                />
              </div>
            )}

            {(importPhase === 'preview' || importPhase === 'uploading') && (
              <>
                {importPhase === 'uploading' && (
                  <div className="space-y-2">
                    <p className="text-sm font-medium">
                      Uploading slide {uploadCurrent} of {uploadTotal}…
                    </p>
                    <ProgressBar
                      value={uploadTotal > 0 ? (uploadCurrent / uploadTotal) * 100 : 0}
                    />
                  </div>
                )}

                {importPhase === 'preview' && (
                  <p className="text-sm text-muted-foreground">
                    {importedCount > 0
                      ? `${importedCount} imported, ${remainingCount} remaining. `
                      : `${importPages.filter(p => p.selected).length} of ${importPages.length} pages selected. `}
                    Click a page to {importedCount > 0 ? 'de' : ''}select it
                    {importedCount === 0 ? ' or leave it out of the import' : ''}.
                  </p>
                )}

                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                  {importPages.map((page) => (
                    <button
                      key={page.pageNumber}
                      type="button"
                      disabled={importPhase === 'uploading' || page.status === 'done'}
                      onClick={() => togglePageSelected(page.pageNumber)}
                      className={cn(
                        'relative rounded-md border-2 overflow-hidden text-left transition-opacity',
                        page.selected ? 'border-primary' : 'border-transparent opacity-40',
                        page.status === 'failed' && 'border-destructive',
                      )}
                      title={
                        page.status === 'done'
                          ? `Slide imported`
                          : page.selected
                            ? 'Click to skip this page'
                            : 'Click to include this page'
                      }
                    >
                      <img
                        src={page.previewUrl}
                        alt={`Page ${page.pageNumber}`}
                        className="w-full aspect-video object-contain bg-muted/40"
                      />
                      <span className="absolute bottom-1 left-1.5 text-xs font-medium bg-background/80 rounded px-1.5 py-0.5">
                        {page.pageNumber}
                      </span>
                      {page.status === 'done' && (
                        <CheckCircle2 className="absolute top-1.5 right-1.5 h-5 w-5 text-green-500 bg-background/80 rounded-full" />
                      )}
                      {page.status === 'failed' && (
                        <AlertCircle className="absolute top-1.5 right-1.5 h-5 w-5 text-destructive bg-background/80 rounded-full" />
                      )}
                      {page.status === 'uploading' && (
                        <Loader2 className="absolute top-1.5 right-1.5 h-5 w-5 animate-spin text-primary bg-background/80 rounded-full" />
                      )}
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>

          <DialogFooter className="border-t pt-4">
            {importPhase === 'uploading' ? (
              <Button
                variant="outline"
                onClick={() => importAbortRef.current?.abort()}
              >
                Cancel import
              </Button>
            ) : (
              <Button
                variant="outline"
                onClick={() => closeImportModal(importedCount > 0)}
              >
                Close
              </Button>
            )}
            {importPhase === 'preview' && (
              <Button onClick={runImport} disabled={remainingCount === 0}>
                <Upload className="h-4 w-4 mr-2" />
                {failedCount > 0 || importedCount > 0
                  ? `Retry remaining (${remainingCount})`
                  : `Import ${remainingCount} slide${remainingCount === 1 ? '' : 's'}`}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
