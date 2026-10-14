import type { IntentClaimResponse } from '@/models';
import { cn } from '@/utils';

export interface ClaimRowProps {
    claim: IntentClaimResponse;
}

const CRITICALITY_CLASSES: Record<string, string> = {
    critical: 'bg-rose-500/15 text-rose-700 dark:text-rose-300 ring-1 ring-inset ring-rose-500/30',
    high: 'bg-amber-500/15 text-amber-700 dark:text-amber-300 ring-1 ring-inset ring-amber-500/30',
    medium: 'bg-sky-500/15 text-sky-700 dark:text-sky-300 ring-1 ring-inset ring-sky-500/30',
    low: 'bg-slate-500/15 text-slate-600 dark:text-slate-300 ring-1 ring-inset ring-slate-500/30',
};

export const ClaimRow = ({ claim }: ClaimRowProps) => (
    <li className="rounded-lg border bg-secondary/40 p-3">
        <div className="flex items-center gap-2">
            <code className="font-mono text-xs font-semibold text-link">{claim.claim_id}</code>
            <span
                className={cn(
                    'rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider',
                    CRITICALITY_CLASSES[claim.criticality] ?? CRITICALITY_CLASSES.low,
                )}
            >
                {claim.criticality}
            </span>
        </div>
        <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{claim.statement}</p>
    </li>
);
