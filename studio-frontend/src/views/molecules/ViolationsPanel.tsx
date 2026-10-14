import { parseViolations } from '@/viewmodels/playbook';
import { Markdown } from '@/views/molecules/Markdown';

export interface ViolationsPanelProps {
    body: string;
}

/** The five cross-cutting rules as scannable one-liners; expand for detail. */
export const ViolationsPanel = ({ body }: ViolationsPanelProps) => {
    const { items, footer } = parseViolations(body);

    return (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-amber-700 dark:text-amber-300">
                Top violations - check every change
            </h3>
            <ol className="mt-2 flex flex-col gap-1">
                {items.map((item) => (
                    <li key={item.number}>
                        <details className="group">
                            <summary className="cursor-pointer select-none rounded px-1.5 py-1 text-sm text-foreground marker:text-amber-600/70 dark:marker:text-amber-400/70 hover:bg-amber-500/10">
                                <span className="mr-1.5 font-mono text-xs text-amber-700 dark:text-amber-300">
                                    {item.number}.
                                </span>
                                <span className="font-medium">{item.title}</span>
                            </summary>
                            <div className="mt-1 border-l-2 border-amber-500/30 pl-3">
                                <Markdown className="prose-p:text-xs prose-li:text-xs">
                                    {item.body.replace(/^\d+\.\s*/, '')}
                                </Markdown>
                            </div>
                        </details>
                    </li>
                ))}
            </ol>
            {footer && (
                <div className="mt-2 border-t border-amber-500/20 pt-2">
                    <Markdown className="prose-p:text-[11px] prose-p:text-muted-foreground">
                        {footer}
                    </Markdown>
                </div>
            )}
        </div>
    );
};
