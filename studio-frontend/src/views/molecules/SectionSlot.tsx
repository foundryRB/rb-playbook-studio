import type { RefSectionResponse } from '@/models';
import { cn } from '@/utils';

/** Template-slot classification for REF sections, shared by every reader
 *  (the 2D RefReader and the 3D universe panel render the same badges). */

export type SectionSlot = 'content' | 'anti-patterns' | 'derivable' | 'generated';

export const slotOf = (section: RefSectionResponse): SectionSlot => {
    if (section.generated) {
        return 'generated';
    }
    const t = section.title.toLowerCase();
    if (t.includes('anti-pattern')) {
        return 'anti-patterns';
    }
    if (t.startsWith('see also') || t.startsWith('cross-references')) {
        return 'derivable';
    }
    return 'content';
};

export const SLOT_BADGES: Partial<
    Record<SectionSlot, { label: string; className: string; hint: string }>
> = {
    'anti-patterns': {
        label: 'anti-patterns',
        className:
            'bg-rose-500/15 text-rose-700 dark:text-rose-300 ring-1 ring-inset ring-rose-500/30',
        hint: 'The template slot for what NOT to do.',
    },
    derivable: {
        label: 'derivable',
        className:
            'bg-slate-500/15 text-slate-600 dark:text-slate-300 ring-1 ring-inset ring-slate-500/30',
        hint: 'Links here are derivable from the graph; only the annotations are curated.',
    },
    generated: {
        label: 'generated',
        className:
            'bg-slate-500/15 text-slate-600 dark:text-slate-300 ring-1 ring-inset ring-slate-500/30',
        hint: 'Maintained by scripts/sync_backlinks.py; edit skill frontmatter instead.',
    },
};

export const SlotBadge = ({ slot }: { slot: SectionSlot }) => {
    const badge = SLOT_BADGES[slot];
    if (!badge) {
        return null;
    }
    return (
        <span
            title={badge.hint}
            className={cn(
                'rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider',
                badge.className,
            )}
        >
            {badge.label}
        </span>
    );
};
