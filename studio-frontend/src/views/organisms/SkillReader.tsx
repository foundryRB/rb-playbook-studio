import { useEffect } from 'react';

import { Button } from '@/components/ui/button';
import { cn } from '@/utils';
import { useGraph } from '@/viewmodels/graph';
import { useNav } from '@/viewmodels/nav';
import { useSkillDetail } from '@/viewmodels/skilldetail';
import { useSync } from '@/viewmodels/sync';
import { Spinner } from '@/views/atoms/Spinner';
import { ConnectAgent } from '@/views/molecules/ConnectAgent';
import { corpusLinkComponents } from '@/views/molecules/CorpusLink';
import { Markdown } from '@/views/molecules/Markdown';
import { ValidationBanner } from '@/views/molecules/ValidationBanner';

const shortName = (id: string): string => id.replace(/^REF-/, '');

export const SkillReader = () => {
    const selectedSkill = useSkillDetail((state) => state.selectedSkill);
    const skill = useSkillDetail((state) => state.skill);
    const loading = useSkillDetail((state) => state.loading);
    const error = useSkillDetail((state) => state.error);
    const activeFile = useSkillDetail((state) => state.activeFile);
    const fileContent = useSkillDetail((state) => state.fileContent);
    const fileLoading = useSkillDetail((state) => state.fileLoading);
    const editing = useSkillDetail((state) => state.editing);
    const draft = useSkillDetail((state) => state.draft);
    const saving = useSkillDetail((state) => state.saving);
    const saveError = useSkillDetail((state) => state.saveError);
    const installing = useSkillDetail((state) => state.installing);
    const lastReport = useSkillDetail((state) => state.lastReport);
    const load = useSkillDetail((state) => state.load);
    const openFile = useSkillDetail((state) => state.openFile);
    const startEdit = useSkillDetail((state) => state.startEdit);
    const setDraft = useSkillDetail((state) => state.setDraft);
    const cancelEdit = useSkillDetail((state) => state.cancelEdit);
    const save = useSkillDetail((state) => state.save);
    const install = useSkillDetail((state) => state.install);
    const selectRef = useGraph((state) => state.select);
    const setView = useNav((state) => state.setView);
    // A managed deployment has no local skills runtime: agents install on
    // their own machines, so the runtime panel becomes a connect affordance.
    const deployed = useSync((state) => state.enabled);
    const initSync = useSync((state) => state.init);

    useEffect(() => {
        void initSync();
    }, [initSync]);

    useEffect(() => {
        if (selectedSkill !== null) {
            void load(selectedSkill);
        }
    }, [selectedSkill, load]);

    if (selectedSkill === null) {
        return <p className="text-sm text-muted-foreground">Pick a skill from the sidebar.</p>;
    }
    if (loading && !skill) {
        return <Spinner />;
    }
    if (error) {
        return <p className="text-sm text-destructive">{error}</p>;
    }
    if (!skill) {
        return null;
    }

    const isSkillMd = activeFile === 'SKILL.md';

    return (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_280px]">
            <div className="flex min-w-0 flex-col gap-4">
                <div>
                    <div className="flex items-center gap-3">
                        <h2 className="font-mono text-xl font-bold tracking-tight">{skill.name}</h2>
                        {!deployed && (
                            <span
                                className={cn(
                                    'rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ring-1 ring-inset',
                                    !skill.installed &&
                                        'bg-slate-500/15 text-slate-600 dark:text-slate-300 ring-slate-500/30',
                                    skill.installed &&
                                        skill.in_sync &&
                                        'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 ring-emerald-500/30',
                                    skill.installed &&
                                        !skill.in_sync &&
                                        'bg-amber-500/15 text-amber-700 dark:text-amber-300 ring-amber-500/30',
                                )}
                            >
                                {!skill.installed
                                    ? 'not installed'
                                    : skill.in_sync
                                      ? 'installed'
                                      : 'out of sync'}
                            </span>
                        )}
                    </div>
                    <p className="mt-1.5 text-sm italic text-muted-foreground">
                        {skill.description}
                    </p>
                    {skill.refs.length > 0 && (
                        <div className="mt-2 flex flex-wrap items-baseline gap-1.5">
                            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/70">
                                instantiates
                            </span>
                            {skill.refs.map((refId, index) => (
                                <button
                                    key={refId}
                                    onClick={() => {
                                        selectRef(refId);
                                        setView('ref');
                                    }}
                                    title={
                                        index === 0
                                            ? `${refId}: this skill's home sun (it lives with this REF)`
                                            : refId
                                    }
                                    className={
                                        index === 0
                                            ? 'rounded-full border border-link bg-primary/15 px-2 py-0.5 text-[11px] font-semibold text-link hover:bg-primary/25'
                                            : 'rounded-full border border-border bg-secondary/60 px-2 py-0.5 text-[11px] text-foreground hover:border-link/60 hover:text-link'
                                    }
                                >
                                    {index === 0 ? `⌂ ${shortName(refId)}` : shortName(refId)}
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {lastReport && <ValidationBanner report={lastReport} />}

                <div className="rounded-lg border bg-card/60">
                    <div className="flex items-center justify-between border-b border-border/70 px-4 py-2">
                        <p className="font-mono text-xs text-muted-foreground">
                            skills/{skill.name}/{activeFile}
                        </p>
                        {skill.can_edit && !editing && (
                            <Button
                                variant="outline"
                                className="h-6 px-2.5 text-xs"
                                onClick={startEdit}
                            >
                                Edit
                            </Button>
                        )}
                    </div>
                    <div className="p-4">
                        {editing ? (
                            <>
                                <textarea
                                    className="h-[55vh] w-full rounded-md border border-input bg-background/80 p-3 font-mono text-xs leading-relaxed text-foreground outline-none focus:ring-1 focus:ring-ring"
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
                            </>
                        ) : fileLoading ? (
                            <Spinner />
                        ) : isSkillMd ? (
                            <Markdown components={corpusLinkComponents}>{skill.body}</Markdown>
                        ) : (
                            <pre className="max-h-[60vh] overflow-auto whitespace-pre font-mono text-xs leading-relaxed text-muted-foreground">
                                {fileContent ?? ''}
                            </pre>
                        )}
                    </div>
                </div>
            </div>

            <aside className="hidden xl:block">
                <div className="sticky top-16 flex flex-col gap-3">
                    <div className="rounded-lg border bg-card/60 p-3">
                        <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                            Files
                        </p>
                        <ul className="flex flex-col gap-0.5">
                            {skill.files.map((file) => (
                                <li key={file}>
                                    <button
                                        onClick={() => void openFile(file)}
                                        className={cn(
                                            'w-full truncate rounded px-1.5 py-1 text-left font-mono text-xs',
                                            activeFile === file
                                                ? 'bg-secondary font-semibold text-foreground'
                                                : 'text-muted-foreground hover:bg-secondary/60 hover:text-foreground',
                                        )}
                                    >
                                        {file}
                                    </button>
                                </li>
                            ))}
                        </ul>
                    </div>
                    <div className="rounded-lg border bg-card/60 p-3">
                        <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                            {deployed ? 'Install via your agent' : 'Runtime'}
                        </p>
                        {deployed ? (
                            <ConnectAgent skillName={skill.name} />
                        ) : (
                            <>
                                <p className="text-xs text-muted-foreground">
                                    {!skill.installed
                                        ? 'Not in the runtime skills directory yet.'
                                        : skill.in_sync
                                          ? 'Runtime copy matches this master.'
                                          : 'Master has changed since the last install.'}
                                </p>
                                <Button
                                    className="mt-2 w-full"
                                    disabled={installing || (skill.installed && skill.in_sync)}
                                    onClick={() => void install()}
                                >
                                    {installing
                                        ? 'Installing...'
                                        : !skill.installed
                                          ? 'Install to runtime'
                                          : skill.in_sync
                                            ? 'Installed'
                                            : 'Reinstall (sync)'}
                                </Button>
                            </>
                        )}
                    </div>
                </div>
            </aside>
        </div>
    );
};
