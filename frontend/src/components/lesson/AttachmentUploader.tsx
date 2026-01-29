import { useState, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/Button';
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
import type { LessonAttachment } from '@/types';
import { Upload, Trash2, Loader2, FileText, Image, File, Paperclip } from 'lucide-react';
import { cn } from '@/lib/utils';

interface AttachmentUploaderProps {
  lessonId: number;
  lessonTitle: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(fileType: string) {
  const ext = fileType.toLowerCase();
  if (['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) {
    return <Image className="h-5 w-5 text-blue-500" />;
  }
  if (['pdf', 'doc', 'docx', 'txt', 'md'].includes(ext)) {
    return <FileText className="h-5 w-5 text-red-500" />;
  }
  return <File className="h-5 w-5 text-muted-foreground" />;
}

export function AttachmentUploader({
  lessonId,
  lessonTitle,
  open,
  onOpenChange,
}: AttachmentUploaderProps) {
  const [attachments, setAttachments] = useState<LessonAttachment[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open && lessonId) {
      loadAttachments();
    }
  }, [open, lessonId]);

  const loadAttachments = async () => {
    setIsLoading(true);
    setError('');
    try {
      const data = await courseService.getLessonAttachments(lessonId);
      setAttachments(data);
    } catch (err) {
      console.error('Failed to load attachments:', err);
      setError('Failed to load attachments');
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    // Validate file count
    const remainingSlots = 10 - attachments.length;
    if (files.length > remainingSlots) {
      setError(`Maximum 10 attachments per lesson. You can add ${remainingSlots} more.`);
      return;
    }

    // Validate file sizes (10MB max)
    const maxSize = 10 * 1024 * 1024;
    for (const file of Array.from(files)) {
      if (file.size > maxSize) {
        setError(`File "${file.name}" exceeds 10MB limit`);
        return;
      }
    }

    setIsUploading(true);
    setError('');
    try {
      const newAttachments = await courseService.uploadLessonAttachments(
        lessonId,
        Array.from(files)
      );
      setAttachments(prev => [...prev, ...newAttachments]);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err) {
      console.error('Failed to upload:', err);
      setError('Failed to upload files');
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (attachmentId: number) => {
    if (!confirm('Are you sure you want to delete this attachment?')) return;

    try {
      await courseService.deleteLessonAttachment(lessonId, attachmentId);
      setAttachments(prev => prev.filter(a => a.id !== attachmentId));
    } catch (err) {
      console.error('Failed to delete:', err);
      setError('Failed to delete attachment');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Paperclip className="h-5 w-5" />
            Lesson Attachments
          </DialogTitle>
          <DialogDescription>
            Upload files for "{lessonTitle}". Students can download these materials.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="bg-destructive/10 border border-destructive/20 text-destructive rounded-md px-4 py-3 text-sm">
            {error}
          </div>
        )}

        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          {/* Upload Zone */}
          <div
            className={cn(
              "border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer hover:border-primary/50",
              isUploading && "pointer-events-none opacity-50"
            )}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.md,.csv,.png,.jpg,.jpeg,.gif,.webp,.svg,.zip,.rar,.7z,.mp3,.wav,.mp4,.webm,.mov,.py,.js,.html,.css,.json"
              onChange={(e) => handleUpload(e.target.files)}
            />
            {isUploading ? (
              <Loader2 className="h-8 w-8 mx-auto mb-2 animate-spin text-muted-foreground" />
            ) : (
              <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
            )}
            <p className="text-sm font-medium">
              {isUploading ? 'Uploading...' : 'Click to upload files'}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              PDF, images, documents, code files (max 10MB each)
            </p>
            <p className="text-xs text-muted-foreground">
              {attachments.length}/10 attachments
            </p>
          </div>

          {/* Attachments List */}
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : attachments.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-muted-foreground">
                <Paperclip className="h-8 w-8 mx-auto mb-3 opacity-50" />
                <p>No attachments yet.</p>
                <p className="text-sm mt-1">Upload files to share with students.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {attachments.map((attachment) => (
                <Card key={attachment.id}>
                  <CardContent className="py-3 px-4">
                    <div className="flex items-center gap-3">
                      {getFileIcon(attachment.file_type)}
                      <div className="flex-1 min-w-0">
                        <a
                          href={attachment.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm font-medium text-primary hover:underline truncate block"
                        >
                          {attachment.filename}
                        </a>
                        <p className="text-xs text-muted-foreground">
                          {formatFileSize(attachment.file_size)}
                        </p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(attachment.id)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Done
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
