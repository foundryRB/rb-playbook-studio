import { useEffect } from 'react';

import { Button } from '@/components/ui/button';
import { selectOtherSections, selectViolationsSection, usePlaybook } from '@/viewmodels/playbook';
import { Spinner } from '@/views/atoms/Spinner';
import { corpusLinkComponents } from '@/views/molecules/CorpusLink';
import { Markdown } from '@/views/molecules/Markdown';
import { ValidationBanner } from '@/views/molecules/ValidationBanner';
import { ViolationsPanel } from '@/views/molecules/ViolationsPanel';

/** The AI-PLAYBOOK.md document itself: violations pinned first, gated editing. */
export const PlaybookReader = () => {
    const doc = usePlaybook((state) => state.doc);
    const loading = usePlaybook((state) => state.loading);
    const error = usePlaybook((state) => state.error);
    const editing = usePlaybook((state) => state.editing);
    const draft = usePlaybook((state) => state.draft);
    const saving = usePlaybook((state) => state.saving);
    const saveError = usePlaybook((state) => state.saveError);
    const lastReport = usePlaybook((state) => state.lastReport);
    const load = usePlaybook((state) => state.load);
    const startEdit = usePlaybook((state) => state.startEdit);
    const setDraft = usePlaybook((state) => state.setDraft);
    const cancelEdit = usePlaybook((state) => state.cancelEdit);
    const save = usePlaybook((state) => state.save);

    useEffect(() => {
        void load();
    }, [load]);

    if (loading && !doc) {
        return <Spinner />;
    }
    if (error) {
        return <p className="text-sm text-destructive">{error}</p>;
    }
    if (!doc) {
        return null;
    }

    if (editing) {
        return (
            <div className="mx-auto flex max-w-5xl flex-col gap-3">
                <div className="flex items-center gap-3">
                    <h2 className="text-xl font-bold tracking-tight">{doc.title}</h2>
                    <span className="text-xs text-muted-foreground">
                        whole document; INT-LAYER-003 keeps the skills table honest
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

    const violations = selectViolationsSection(doc);
    const others = selectOtherSections(doc);

    return (
        <div className="mx-auto flex max-w-4xl flex-col gap-4">
            <div className="flex items-center justify-between gap-3">
                <h2 className="text-xl font-bold tracking-tight">{doc.title}</h2>
                {doc.can_edit && (
                    <Button variant="outline" onClick={() => void startEdit()}>
                        Edit document
                    </Button>
                )}
            </div>
            {lastReport && <ValidationBanner report={lastReport} />}

            {violations && <ViolationsPanel body={violations.body} />}

            {others.map((section) => (
                <section key={section.title} className="rounded-lg border bg-card/60 p-4">
                    <h3 className="mb-2 text-sm font-semibold">{section.title}</h3>
                    <Markdown components={corpusLinkComponents}>{section.body}</Markdown>
                </section>
            ))}
        </div>
    );
};
