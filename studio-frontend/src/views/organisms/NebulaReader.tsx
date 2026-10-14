import { useState } from 'react';
import type { Components } from 'react-markdown';

import { Card, CardContent } from '@/components/ui/card';
import type { NebulaNoteResponse } from '@/models';
import { normalizeToken } from '@/viewmodels/graph/panel.model';
import { useNebulae } from '@/viewmodels/nebulae';
import { Spinner } from '@/views/atoms/Spinner';
import { Markdown } from '@/views/molecules/Markdown';

/** One stardust note's frontmatter, rendered as muted facts. */
const NoteFacts = ({ note }: { note: NebulaNoteResponse }) => (
    <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
        <span className="rounded border border-border px-1.5 py-0.5 font-mono">{note.type}</span>
        <span className="rounded border border-border px-1.5 py-0.5">
            confidence {note.confidence}
        </span>
        {note.vote && (
            <span className="rounded border border-border px-1.5 py-0.5">vote {note.vote}</span>
        )}
        <span className="rounded border border-border px-1.5 py-0.5">{note.status}</span>
        {note.seats.map((seat) => (
            <span key={seat} className="rounded border border-border/60 px-1.5 py-0.5 italic">
                {seat}
            </span>
        ))}
    </div>
);

/** A nebula's stardust: the territory under study, its roster of typed notes
 *  (each readable in place), and the fronting NEBULA.md. Unearned content
 *  reads second-class throughout: dashed borders, muted ink, an explicit
 *  banner (REF-Forge: the quarantine). */
export const NebulaReader = () => {
    const detail = useNebulae((state) => state.detail);
    const loading = useNebulae((state) => state.detailLoading);
    const error = useNebulae((state) => state.detailError);
    const [openNote, setOpenNote] = useState<string | null>(null);

    if (loading) {
        return <Spinner />;
    }
    if (error) {
        return <p className="text-sm text-destructive">{error}</p>;
    }
    if (!detail) {
        return <p className="text-sm text-muted-foreground">Pick a nebula on the map.</p>;
    }
    const note = detail.notes.find((n) => n.name === openNote) ?? null;
    const noteNames = new Set(detail.notes.map((n) => n.name));

    // Markdown links stay inside the reader: a roster link like
    // [playtomic](playtomic.md) opens that note here (a real relative anchor
    // would navigate the SPA away); http(s) opens a tab; the rest is inert.
    const components: Components = {
        a: ({ href, children }) => {
            const target = normalizeToken(href ?? '');
            if (noteNames.has(target)) {
                return (
                    <button
                        onClick={() => setOpenNote(target)}
                        title={`Open the ${target} note`}
                        className="font-medium text-muted-foreground underline decoration-border underline-offset-2 hover:text-foreground"
                    >
                        {children}
                    </button>
                );
            }
            if (href && /^https?:\/\//.test(href)) {
                return (
                    <a href={href} target="_blank" rel="noreferrer">
                        {children}
                    </a>
                );
            }
            return <span>{children}</span>;
        },
    };

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-xl font-bold text-muted-foreground">{detail.territory}</h1>
                <span className="rounded-full bg-slate-500/15 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500 ring-1 ring-inset ring-slate-500/30 dark:text-slate-400">
                    nebula &middot; unearned
                </span>
            </div>
            {detail.subject && (
                <p className="text-sm italic text-muted-foreground">{detail.subject}</p>
            )}
            <p className="rounded-md border border-dashed border-border bg-secondary/20 px-3 py-2 text-xs text-muted-foreground">
                Stardust is quarantined research: nothing here informs work outside the Forge until
                the smelt promotes it into a galaxy.
            </p>

            <Card className="border-dashed">
                <CardContent className="space-y-2 p-5">
                    <h2 className="text-sm font-semibold text-muted-foreground">
                        Stardust ({detail.notes.length})
                    </h2>
                    <div className="flex flex-wrap gap-1.5">
                        {detail.notes.map((n) => (
                            <button
                                key={n.name}
                                onClick={() => setOpenNote(openNote === n.name ? null : n.name)}
                                title={`${n.type} · ${n.status}`}
                                className={
                                    openNote === n.name
                                        ? 'rounded-md border border-dashed border-slate-400/70 bg-secondary/60 px-2 py-0.5 font-mono text-[11px] text-foreground'
                                        : 'rounded-md border border-dashed border-border px-2 py-0.5 font-mono text-[11px] text-muted-foreground hover:text-foreground'
                                }
                            >
                                {n.name}
                            </button>
                        ))}
                    </div>
                </CardContent>
            </Card>

            {note && (
                <Card className="border-dashed">
                    <CardContent className="space-y-3 p-5">
                        <NoteFacts note={note} />
                        <Markdown components={components}>{note.body}</Markdown>
                        {note.sources.length > 0 && (
                            <div className="space-y-0.5 text-xs text-muted-foreground">
                                <span className="font-semibold uppercase tracking-wider">
                                    sources
                                </span>
                                {note.sources.map((source) => (
                                    <a
                                        key={source}
                                        href={source}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="block truncate underline decoration-border underline-offset-2 hover:text-foreground"
                                    >
                                        {source}
                                    </a>
                                ))}
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            <Card className="border-dashed opacity-90">
                <CardContent className="p-5">
                    <Markdown components={components}>{detail.raw}</Markdown>
                </CardContent>
            </Card>
        </div>
    );
};
