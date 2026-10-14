import { useEffect } from 'react';

import type { RefSectionResponse } from '@/models';
import { Button } from '@/components/ui/button';
import { cn } from '@/utils';
import { useGraph } from '@/viewmodels/graph';
import { useNav } from '@/viewmodels/nav';
import { selectRoutingRowsFor, usePlaybook } from '@/viewmodels/playbook';
import { useRefDetail } from '@/viewmodels/refdetail';
import { DomainBadge } from '@/views/atoms/DomainBadge';
import { Spinner } from '@/views/atoms/Spinner';
import { EgoGraph } from '@/views/organisms/EgoGraph';
import { corpusLinkComponents } from '@/views/molecules/CorpusLink';
import { Markdown } from '@/views/molecules/Markdown';
import { SLOT_BADGES, slotOf } from '@/views/molecules/SectionSlot';
import { ValidationBanner } from '@/views/molecules/ValidationBanner';

export const RefReader = () => {
    const selectedRef = useGraph((state) => state.selectedRef);
    const ref = useRefDetail((state) => state.ref);
    const loading = useRefDetail((state) => state.loading);
    const error = useRefDetail((state) => state.error);
    const editingSection = useRefDetail((state) => state.editingSection);
    const editingDoc = useRefDetail((state) => state.editingDoc);
    const draft = useRefDetail((state) => state.draft);
    const saving = useRefDetail((state) => state.saving);
    const saveError = useRefDetail((state) => state.saveError);
    const lastReport = useRefDetail((state) => state.lastReport);
    const load = useRefDetail((state) => state.load);
    const startEdit = useRefDetail((state) => state.startEdit);
    const startDocEdit = useRefDetail((state) => state.startDocEdit);
    const setDraft = useRefDetail((state) => state.setDraft);
    const cancelEdit = useRefDetail((state) => state.cancelEdit);
    const save = useRefDetail((state) => state.save);

    const playbookDoc = usePlaybook((state) => state.doc);
    const playbookLoad = usePlaybook((state) => state.load);
    const setView = useNav((state) => state.setView);

    useEffect(() => {
        if (selectedRef !== null) {
            void load(selectedRef);
        }
        void playbookLoad();
    }, [selectedRef, load, playbookLoad]);

    if (selectedRef === null) {
        return <p className="text-sm text-muted-foreground">Pick a REF from the sidebar.</p>;
    }
    if (loading) {
        return <Spinner />;
    }
    if (error) {
        return <p className="text-sm text-destructive">{error}</p>;
    }
    if (!ref) {
        return null;
    }

    if (editingDoc) {
        return (
            <div className="mx-auto flex max-w-5xl flex-col gap-3">
                <div className="flex items-center gap-3">
                    <h2 className="font-mono text-xl font-bold tracking-tight">{ref.name}</h2>
                    <span className="text-xs text-muted-foreground">
                        whole document - restructure freely; the gates enforce the template
                    </span>
                </div>
                {lastReport && !lastReport.ok && <ValidationBanner report={lastReport} />}
                <textarea
                    className="h-[65vh] w-full rounded-md border border-input bg-background/80 p-4 font-mono text-xs leading-relaxed text-foreground outline-none focus:ring-1 focus:ring-ring"
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    spellCheck={false}
                />
                {saveError && <p className="text-xs text-destructive">{saveError}</p>}
                <div className="flex gap-2">
                    <Button disabled={saving} onClick={() => void save()}>
                        {saving ? 'Validating...' : 'Save (runs gates)'}
                    </Button>
                    <Button variant="outline" disabled={saving} onClick={cancelEdit}>
                        Cancel
                    </Button>
                </div>
            </div>
        );
    }

    const onEdit = (section: RefSectionResponse) => {
        startEdit(section.number, section.body);
        document.getElementById(`section-${section.number}`)?.scrollIntoView({ block: 'start' });
    };

    return (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
            <div className="flex min-w-0 flex-col gap-4">
                <div>
                    <div className="flex items-center gap-3">
                        <h2 className="font-mono text-xl font-bold tracking-tight">{ref.name}</h2>
                        <DomainBadge domain={ref.domain} />
                    </div>
                    <p className="mt-1.5 text-sm italic text-muted-foreground">{ref.summary}</p>
                </div>

                {lastReport && <ValidationBanner report={lastReport} />}

                {ref.sections.map((section) => {
                    const slot = slotOf(section);
                    const badge = SLOT_BADGES[slot];
                    if (editingSection === section.number) {
                        return (
                            <section
                                key={section.number}
                                id={`section-${section.number}`}
                                className="rounded-lg border border-link/50 bg-secondary/30 p-4"
                            >
                                <h3 className="text-sm font-semibold">
                                    <span className="mr-1.5 text-link">§{section.number}</span>
                                    {section.title}
                                </h3>
                                <textarea
                                    className="mt-3 h-72 w-full rounded-md border border-input bg-background/80 p-3 font-mono text-xs leading-relaxed text-foreground outline-none focus:ring-1 focus:ring-ring"
                                    value={draft}
                                    onChange={(event) => setDraft(event.target.value)}
                                    spellCheck={false}
                                />
                                {saveError && (
                                    <p className="mt-1 text-xs text-destructive">{saveError}</p>
                                )}
                                <div className="mt-3 flex gap-2">
                                    <Button disabled={saving} onClick={() => void save()}>
                                        {saving ? 'Validating...' : 'Save (runs gates)'}
                                    </Button>
                                    <Button
                                        variant="outline"
                                        disabled={saving}
                                        onClick={cancelEdit}
                                    >
                                        Cancel
                                    </Button>
                                </div>
                            </section>
                        );
                    }
                    return (
                        <section
                            key={section.number}
                            id={`section-${section.number}`}
                            className={cn(
                                'group scroll-mt-16 rounded-lg border p-4',
                                slot === 'anti-patterns' && 'border-rose-500/30 bg-rose-500/5',
                                slot === 'content' && 'bg-card/60',
                                (slot === 'derivable' || slot === 'generated') &&
                                    'bg-card/30 opacity-80',
                            )}
                        >
                            <div className="flex items-center justify-between gap-2">
                                <h3 className="text-sm font-semibold">
                                    <span className="mr-1.5 text-link">§{section.number}</span>
                                    {section.title}
                                </h3>
                                <div className="flex items-center gap-2">
                                    {badge && (
                                        <span
                                            title={badge.hint}
                                            className={cn(
                                                'rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider',
                                                badge.className,
                                            )}
                                        >
                                            {badge.label}
                                        </span>
                                    )}
                                    {ref.can_edit && slot !== 'generated' && (
                                        <Button
                                            variant="outline"
                                            className="h-6 px-2.5 text-xs opacity-0 transition-opacity group-hover:opacity-100"
                                            onClick={() => onEdit(section)}
                                        >
                                            Edit
                                        </Button>
                                    )}
                                </div>
                            </div>
                            <div className="mt-2">
                                <Markdown components={corpusLinkComponents}>
                                    {section.body}
                                </Markdown>
                            </div>
                        </section>
                    );
                })}
            </div>

            <aside className="hidden xl:block">
                <div className="sticky top-16 flex flex-col gap-3">
                    <div className="rounded-lg border bg-card/60 p-3">
                        <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                            Connections
                        </p>
                        <EgoGraph refName={ref.name} />
                    </div>
                    <div className="rounded-lg border bg-card/60 p-3">
                        <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                            Routing
                        </p>
                        {(() => {
                            const rows = selectRoutingRowsFor(playbookDoc, ref.name);
                            if (rows.length === 0) {
                                return (
                                    <div>
                                        <p className="text-xs text-amber-700 dark:text-amber-300">
                                            Not in the playbook routing table: no task will load
                                            this REF.
                                        </p>
                                        <button
                                            onClick={() => setView('playbook')}
                                            className="mt-1.5 text-xs text-link hover:underline"
                                        >
                                            Add a Task Routing row
                                        </button>
                                    </div>
                                );
                            }
                            return (
                                <ul className="flex flex-col gap-1">
                                    {rows.map((task) => (
                                        <li
                                            key={task}
                                            className="text-xs leading-snug text-muted-foreground"
                                        >
                                            {task}
                                        </li>
                                    ))}
                                </ul>
                            );
                        })()}
                    </div>
                    <div className="rounded-lg border bg-card/60 p-3">
                        <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                            Sections
                        </p>
                        <ul className="flex flex-col gap-0.5">
                            {ref.sections.map((section) => (
                                <li key={section.number}>
                                    <button
                                        onClick={() =>
                                            document
                                                .getElementById(`section-${section.number}`)
                                                ?.scrollIntoView({
                                                    block: 'start',
                                                    behavior: 'smooth',
                                                })
                                        }
                                        className="flex w-full items-baseline gap-1.5 rounded px-1.5 py-0.5 text-left text-xs text-muted-foreground hover:bg-secondary/60 hover:text-foreground"
                                    >
                                        <span className="font-mono text-[10px] text-link">
                                            §{section.number}
                                        </span>
                                        <span className="truncate">{section.title}</span>
                                    </button>
                                </li>
                            ))}
                        </ul>
                    </div>
                    {ref.can_edit && (
                        <>
                            <Button variant="outline" onClick={startDocEdit}>
                                Edit whole document
                            </Button>
                            <p className="text-[11px] leading-relaxed text-muted-foreground/70">
                                Add or remove sections by editing the whole document; the intent
                                gates enforce numbering, frontmatter, and generated sections, and
                                roll back any edit that breaks them.
                            </p>
                        </>
                    )}
                </div>
            </aside>
        </div>
    );
};
