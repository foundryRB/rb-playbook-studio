import { useEffect } from 'react';

import { Button } from '@/components/ui/button';
import { cn } from '@/utils';
import { useAgentDetail } from '@/viewmodels/agentdetail';
import { useDoorDetail } from '@/viewmodels/doordetail';
import { useGraph } from '@/viewmodels/graph';
import { useNav } from '@/viewmodels/nav';
import { useSkillDetail } from '@/viewmodels/skilldetail';
import { Spinner } from '@/views/atoms/Spinner';
import { corpusLinkComponents } from '@/views/molecules/CorpusLink';
import { Markdown } from '@/views/molecules/Markdown';
import { ValidationBanner } from '@/views/molecules/ValidationBanner';

const shortName = (id: string): string => id.replace(/^REF-/, '');

export const AgentReader = () => {
    const selectedAgent = useAgentDetail((state) => state.selectedAgent);
    const agent = useAgentDetail((state) => state.agent);
    const loading = useAgentDetail((state) => state.loading);
    const error = useAgentDetail((state) => state.error);
    const editing = useAgentDetail((state) => state.editing);
    const draft = useAgentDetail((state) => state.draft);
    const saving = useAgentDetail((state) => state.saving);
    const saveError = useAgentDetail((state) => state.saveError);
    const lastReport = useAgentDetail((state) => state.lastReport);
    const load = useAgentDetail((state) => state.load);
    const startEdit = useAgentDetail((state) => state.startEdit);
    const setDraft = useAgentDetail((state) => state.setDraft);
    const cancelEdit = useAgentDetail((state) => state.cancelEdit);
    const save = useAgentDetail((state) => state.save);
    const selectRef = useGraph((state) => state.select);
    const selectSkill = useSkillDetail((state) => state.select);
    const selectDoor = useDoorDetail((state) => state.select);
    const setView = useNav((state) => state.setView);

    useEffect(() => {
        if (selectedAgent !== null) {
            void load(selectedAgent);
        }
    }, [selectedAgent, load]);

    if (selectedAgent === null) {
        return <p className="text-sm text-muted-foreground">Pick an agent from the sidebar.</p>;
    }
    if (loading && !agent) {
        return <Spinner />;
    }
    if (error) {
        return <p className="text-sm text-destructive">{error}</p>;
    }
    if (!agent) {
        return null;
    }

    return (
        <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_280px]">
            <div className="flex min-w-0 flex-col gap-4">
                <div>
                    <div className="flex items-center gap-3">
                        <h2 className="font-mono text-xl font-bold tracking-tight">{agent.name}</h2>
                        <span className="rounded-full bg-lime-500/15 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-lime-700 ring-1 ring-inset ring-lime-500/30 dark:text-lime-300">
                            agent
                        </span>
                        {agent.posture.fresh_eyes && (
                            <span className="rounded-full bg-sky-500/15 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-sky-700 ring-1 ring-inset ring-sky-500/30 dark:text-sky-300">
                                fresh eyes
                            </span>
                        )}
                    </div>
                    <p className="mt-1.5 text-sm italic text-muted-foreground">{agent.summary}</p>
                    {agent.refs.length > 0 && (
                        <div className="mt-2 flex flex-wrap items-baseline gap-1.5">
                            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/70">
                                orbits
                            </span>
                            {agent.refs.map((refId, index) => (
                                <button
                                    key={refId}
                                    onClick={() => {
                                        selectRef(refId);
                                        setView('ref');
                                    }}
                                    title={
                                        index === 0
                                            ? `${refId}: this agent's home sun (it lives with this REF)`
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
                    <div className="mt-2 flex flex-wrap items-baseline gap-1.5">
                        <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/70">
                            licensed to run
                        </span>
                        {agent.skills.map((skillId) => (
                            <button
                                key={skillId}
                                onClick={() => {
                                    selectSkill(skillId);
                                    setView('skill');
                                }}
                                title={`${skillId}: a skill this agent is licensed to run (a licence, not a lock)`}
                                className="rounded-full border border-border bg-secondary/60 px-2 py-0.5 text-[11px] text-foreground hover:border-link/60 hover:text-link"
                            >
                                {skillId}
                            </button>
                        ))}
                    </div>
                    {agent.doors.length > 0 && (
                        <div className="mt-2 flex flex-wrap items-baseline gap-1.5">
                            <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/70">
                                needs doors
                            </span>
                            {agent.doors.map((doorId) => (
                                <button
                                    key={doorId}
                                    onClick={() => {
                                        selectDoor(doorId);
                                        setView('door');
                                    }}
                                    title={`${doorId}: a door the environment must bind for this agent`}
                                    className="rounded-full border border-border bg-secondary/60 px-2 py-0.5 text-[11px] text-foreground hover:border-link/60 hover:text-link"
                                >
                                    {doorId}
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {lastReport && <ValidationBanner report={lastReport} />}

                <div className="rounded-lg border bg-card/60">
                    <div className="flex items-center justify-between border-b border-border/70 px-4 py-2">
                        <p className="font-mono text-xs text-muted-foreground">
                            galaxies/{agent.galaxy}/agents/{agent.name}.md
                        </p>
                        {agent.can_edit && !editing && (
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
                        ) : (
                            <Markdown components={corpusLinkComponents}>{agent.body}</Markdown>
                        )}
                    </div>
                </div>
            </div>

            <aside className="hidden xl:block">
                <div className="sticky top-16 flex flex-col gap-3">
                    <div className="rounded-lg border bg-card/60 p-3">
                        <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                            Posture
                        </p>
                        <ul className="flex flex-col gap-1 text-xs text-muted-foreground">
                            <li>
                                permission:{' '}
                                <span className="font-mono text-foreground">
                                    {agent.posture.permission}
                                </span>
                            </li>
                            <li>{agent.posture.writes ? 'writes artifacts' : 'read-only'}</li>
                            <li>
                                {agent.posture.fresh_eyes
                                    ? 'fresh eyes: reviews what it had no hand in'
                                    : 'works on what it produces'}
                            </li>
                        </ul>
                    </div>
                    {agent.appearance && (
                        <div className="rounded-lg border bg-card/60 p-3">
                            <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                                Appearance
                            </p>
                            <ul
                                className={cn(
                                    'grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-muted-foreground',
                                )}
                            >
                                <li>hair: {agent.appearance.hair}</li>
                                <li>headwear: {agent.appearance.headwear}</li>
                                <li>eyes: {agent.appearance.eyes}</li>
                                <li>face: {agent.appearance.face}</li>
                            </ul>
                        </div>
                    )}
                    <p className="px-1 text-[11px] leading-relaxed text-muted-foreground/70">
                        An agent carries who does the work: character, licence, doors, posture. Its
                        skills carry the procedure; the environment binds model and credential.
                    </p>
                </div>
            </aside>
        </div>
    );
};
