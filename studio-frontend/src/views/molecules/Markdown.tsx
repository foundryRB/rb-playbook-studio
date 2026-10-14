import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';

import { cn } from '@/utils';

export interface MarkdownProps {
    children: string;
    className?: string;
    /** Optional element overrides (e.g. universe-aware links and code chips). */
    components?: Components;
}

/** Playbook markdown, styled for the dark theme. */
export const Markdown = ({ children, className, components }: MarkdownProps) => (
    <div
        className={cn(
            'prose prose-sm max-w-none dark:prose-invert',
            'prose-headings:text-foreground prose-p:text-muted-foreground',
            'prose-li:text-muted-foreground prose-strong:text-foreground',
            'prose-code:rounded prose-code:bg-secondary prose-code:px-1 prose-code:py-0.5',
            'prose-code:font-mono prose-code:text-[0.8em] prose-code:text-link',
            'prose-code:before:content-none prose-code:after:content-none',
            'prose-pre:border prose-pre:bg-secondary/60',
            'prose-table:text-xs prose-th:text-foreground prose-td:text-muted-foreground',
            'prose-a:text-link prose-blockquote:border-l-link/50',
            'prose-blockquote:text-muted-foreground',
            className,
        )}
    >
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
            {children}
        </ReactMarkdown>
    </div>
);
