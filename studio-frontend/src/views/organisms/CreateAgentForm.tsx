import { Button } from '@/components/ui/button';
import { DOMAIN_ORDER, DOOR_KINDS, useGraph } from '@/viewmodels/graph';
import { useAgentDetail } from '@/viewmodels/agentdetail';
import { useCreateAgent } from '@/viewmodels/createagent';
import { useNav } from '@/viewmodels/nav';
import { GalaxyField, OwnersField } from '@/views/molecules/CreateFields';
import { ValidationBanner } from '@/views/molecules/ValidationBanner';
import { cn } from '@/utils';

const FIELD_CLASSES =
    'w-full rounded-md border border-input bg-background/70 px-3 py-1.5 text-sm outline-none placeholder:text-muted-foreground/50 focus:ring-1 focus:ring-ring';

const shortName = (id: string): string => id.replace(/^REF-/, '');

export const CreateAgentForm = () => {
    const name = useCreateAgent((state) => state.name);
    const title = useCreateAgent((state) => state.title);
    const description = useCreateAgent((state) => state.description);
    const refs = useCreateAgent((state) => state.refs);
    const skills = useCreateAgent((state) => state.skills);
    const doors = useCreateAgent((state) => state.doors);
    const galaxy = useCreateAgent((state) => state.galaxy);
    const owners = useCreateAgent((state) => state.owners);
    const setOwners = useCreateAgent((state) => state.setOwners);
    const writes = useCreateAgent((state) => state.writes);
    const freshEyes = useCreateAgent((state) => state.freshEyes);
    const submitting = useCreateAgent((state) => state.submitting);
    const error = useCreateAgent((state) => state.error);
    const report = useCreateAgent((state) => state.report);
    const setName = useCreateAgent((state) => state.setName);
    const setTitle = useCreateAgent((state) => state.setTitle);
    const setDescription = useCreateAgent((state) => state.setDescription);
    const toggleRef = useCreateAgent((state) => state.toggleRef);
    const toggleSkill = useCreateAgent((state) => state.toggleSkill);
    const toggleDoor = useCreateAgent((state) => state.toggleDoor);
    const setGalaxy = useCreateAgent((state) => state.setGalaxy);
    const setWrites = useCreateAgent((state) => state.setWrites);
    const setFreshEyes = useCreateAgent((state) => state.setFreshEyes);
    const reset = useCreateAgent((state) => state.reset);
    const submit = useCreateAgent((state) => state.submit);

    const graph = useGraph((state) => state.graph);
    const graphLoad = useGraph((state) => state.load);
    const selectAgent = useAgentDetail((state) => state.select);
    const setView = useNav((state) => state.setView);

    const allRefs = graph?.nodes.filter((n) => n.kind === 'ref') ?? [];
    const allSkills = graph?.nodes.filter((n) => n.kind === 'skill') ?? [];
    const allDoors = graph?.nodes.filter((n) => DOOR_KINDS.has(n.kind)) ?? [];
    const onSubmit = async () => {
        const created = await submit();
        if (created) {
            reset();
            await graphLoad();
            selectAgent(created.name);
            setView('agent');
        }
    };

    const pickChip = (active: boolean): string =>
        cn(
            'rounded-full border px-2 py-0.5 text-[11px]',
            active
                ? 'border-link/70 bg-primary/15 text-link'
                : 'border-border text-muted-foreground hover:text-foreground',
        );

    return (
        <div className="mx-auto flex max-w-2xl flex-col gap-4">
            <div>
                <h2 className="text-lg font-bold tracking-tight">New Agent</h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                    Runs the playbook's own bootstrap-agent scaffolder: the agent file and
                    regenerated REF back-links, in one gated transaction. Replace the body with one
                    paragraph of character afterwards; the no-procedure gate refuses step lists.
                </p>
            </div>

            <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
                Name (kebab-case)
                <input
                    className={`${FIELD_CLASSES} font-mono`}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="release-warden"
                />
            </label>

            <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
                Title (the job title)
                <input
                    className={FIELD_CLASSES}
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Release Warden"
                />
            </label>

            <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
                Description (one line: when to hand work to it; a harness routes on this)
                <input
                    className={FIELD_CLASSES}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Guards a release until its gate is signed; hand it a release to hold."
                />
            </label>

            <GalaxyField
                label="Galaxy (the home sun must live here)"
                value={galaxy}
                onChange={setGalaxy}
            />

            <OwnersField value={owners} onChange={setOwners} />

            <div className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
                REFs this agent orbits (home sun first, frontmatter `refs:`)
                <div className="flex flex-col gap-2 rounded-md border border-input p-3">
                    {DOMAIN_ORDER.map((domain) => {
                        const group = allRefs.filter((r) => r.domain === domain);
                        if (group.length === 0) {
                            return null;
                        }
                        return (
                            <div key={domain} className="flex flex-wrap items-baseline gap-1">
                                <span className="mr-1 text-[10px] uppercase tracking-widest text-muted-foreground/60">
                                    {domain}
                                </span>
                                {group.map((ref) => (
                                    <button
                                        key={ref.id}
                                        onClick={() => toggleRef(ref.id)}
                                        className={pickChip(refs.includes(ref.id))}
                                    >
                                        {refs[0] === ref.id
                                            ? `⌂ ${shortName(ref.id)}`
                                            : shortName(ref.id)}
                                    </button>
                                ))}
                            </div>
                        );
                    })}
                </div>
            </div>

            <div className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
                Skills it is licensed to run (frontmatter `skills:`, at least one)
                <div className="flex flex-wrap gap-1 rounded-md border border-input p-3">
                    {allSkills.map((skill) => (
                        <button
                            key={skill.id}
                            onClick={() => toggleSkill(skill.id)}
                            className={pickChip(skills.includes(skill.id))}
                        >
                            {skill.id}
                        </button>
                    ))}
                </div>
            </div>

            {allDoors.length > 0 && (
                <div className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
                    Doors it needs bound (frontmatter `doors:`)
                    <div className="flex flex-wrap gap-1 rounded-md border border-input p-3">
                        {allDoors.map((door) => (
                            <button
                                key={door.id}
                                onClick={() => toggleDoor(door.id)}
                                className={pickChip(doors.includes(door.id))}
                            >
                                {door.id}
                            </button>
                        ))}
                    </div>
                </div>
            )}

            <div className="flex flex-wrap gap-4 text-xs font-medium text-muted-foreground">
                <label className="flex items-center gap-1.5">
                    <input
                        type="checkbox"
                        checked={writes}
                        onChange={(e) => setWrites(e.target.checked)}
                    />
                    writes (may change the artifacts it works on)
                </label>
                <label className="flex items-center gap-1.5">
                    <input
                        type="checkbox"
                        checked={freshEyes}
                        onChange={(e) => setFreshEyes(e.target.checked)}
                    />
                    fresh eyes (reviews what it had no hand in; scaffolds read-only, no appearance)
                </label>
            </div>

            {error && <p className="text-xs text-destructive">{error}</p>}
            {report && !report.ok && <ValidationBanner report={report} />}

            <div className="flex gap-2">
                <Button disabled={submitting} onClick={() => void onSubmit()}>
                    {submitting ? 'Validating...' : 'Create (runs gates)'}
                </Button>
                <Button variant="outline" disabled={submitting} onClick={() => setView('map')}>
                    Cancel
                </Button>
            </div>
        </div>
    );
};
