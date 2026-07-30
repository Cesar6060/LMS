import { Card, CardContent } from '@/components/ui/Card';
import { Paperclip, FileText, Image, File, Download } from 'lucide-react';
import type { LessonAttachment } from '@/types';

interface LessonAttachmentsListProps {
  attachments: LessonAttachment[];
  /**
   * Phase 62 — cap the file list and scroll it inside the card. Only wanted on
   * slide pages, where this card is a flex sibling of the stage inside an
   * `h-full flex flex-col` and a long list would otherwise subtract from the
   * stage's height. Doc pages scroll as a whole, so a nested scroll region
   * there would just hide files and trap the wheel.
   */
  capHeight?: boolean;
}

export function LessonAttachmentsList({ attachments, capHeight = false }: LessonAttachmentsListProps) {
  if (!attachments || attachments.length === 0) {
    return null;
  }

  return (
    // `shrink-0` so the card keeps its own height instead of being squeezed;
    // it's inert outside a flex parent, so doc pages are unaffected.
    <Card className="mt-6 shrink-0">
      <CardContent className="py-4">
        <div className="flex items-center gap-2 mb-3">
          <Paperclip className="h-4 w-4 text-muted-foreground" />
          <h3 className="font-medium">Lesson Materials</h3>
        </div>
        {/* When capped, the list scrolls rather than the card — the "Lesson
            Materials" heading stays put above it. */}
        <div className={`space-y-2 ${capHeight ? 'max-h-40 overflow-y-auto' : ''}`}>
          {attachments.map((attachment) => {
            const fileType = attachment.file_type.toLowerCase();
            const isImage = ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(fileType);
            const isDoc = ['pdf', 'doc', 'docx', 'txt', 'md'].includes(fileType);

            return (
              <a
                key={attachment.id}
                href={attachment.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-3 p-3 rounded-lg border bg-muted/30 hover:bg-muted/50 transition-colors"
              >
                {isImage ? (
                  <Image className="h-5 w-5 text-blue-500 flex-shrink-0" />
                ) : isDoc ? (
                  <FileText className="h-5 w-5 text-red-500 flex-shrink-0" />
                ) : (
                  <File className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                )}
                <span className="flex-1 text-sm font-medium truncate">
                  {attachment.filename}
                </span>
                <span className="text-xs text-muted-foreground flex-shrink-0">
                  {attachment.file_size < 1024 * 1024
                    ? `${(attachment.file_size / 1024).toFixed(0)} KB`
                    : `${(attachment.file_size / (1024 * 1024)).toFixed(1)} MB`}
                </span>
                <Download className="h-4 w-4 text-muted-foreground flex-shrink-0" />
              </a>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
