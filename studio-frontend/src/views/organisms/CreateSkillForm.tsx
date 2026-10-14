import { Button } from '@/components/ui/button';
import { DOMAIN_ORDER, useGraph } from '@/viewmodels/graph';
import { useCreateSkill } from '@/viewmodels/createskill';
import { useNav } from '@/viewmodels/nav';
import { useSkillDetail } from '@/viewmodels/skilldetail';
import { GalaxyField, OwnersField } from '@/views/molecules/CreateFields';
import { ValidationBanner } from '@/views/molecules/ValidationBanner';
import { cn } from '@/utils';

const FIELD_CLASSES =
    'w-full rounded-md border border-input bg-background/70 px-3 py-1.5 text-sm outline-none placeholder:text-muted-foreground/50 focus:ring-1 focus:ring-ring';

const shortName = (id: string): string => id.replace(/^REF-/, '');

export const CreateSkillForm = () => {
    const name = useCreateSkill((state) => state.name);
    const description = useCreateSkill((state) => state.description);
    const refs = useCreateSkill((state) => state.refs);
    const galaxy = useCreateSkill((state) => state.galaxy);
    const owners = useCreateSkill((state) => state.owners);
    const setOwners = useCreateSkill((state) => state.setOwners);
    const submitting = useCreateSkill((state) => state.submitting);
    const error = useCreateSkill((state) => state.error);
    const report = useCreateSkill((state) => state.report);
    const setName = useCreateSkill((state) => state.setName);
    const setDescription = useCreateSkill((state) => state.setDescription);
    const toggleRef = useCreateSkill((state) => state.toggleRef);
    const setGalaxy = useCreateSkill((state) => state.setGalaxy);
    const reset = useCreateSkill((state) => state.reset);
    const submit = useCreateSkill((state) => state.submit);

    const graph = useGraph((state) => state.graph);
    const graphLoad = useGraph((state) => state.load);
    const selectSkill = useSkillDetail((state) => state.select);
    const setView = useNav((state) => state.setView);

    const allRefs = graph?.nodes.filter((n) => n.kind === 'ref') ?? [];
    const onSubmit = async () => {
        const created = await submit();
        if (created) {
            reset();
            await graphLoad();
            selectSkill(created.name);
            setView('skill');
        }
    };

    return (
        <div className="mx-auto flex max-w-2xl flex-col gap-4">
            <div>
                <h2 className="text-lg font-bold tracking-tight">New Skill</h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                    Runs the playbook's own bootstrap-skill scaffolder: SKILL.md skeleton, the
                    Available Skills table row, and regenerated REF back-links, in one gated
                    transaction. Author the body afterwards; install to the runtime manually.
                </p>
            </div>

            <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
                Name (kebab-case)
                <input
                    className={`${FIELD_CLASSES} font-mono`}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="bootstrap-terraform"
                />
            </label>

            <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
                Description (one line, shown in the skills table)
                <textarea
                    className={`${FIELD_CLASSES} h-16`}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Scaffold a Terraform module conforming to REF-Terraform."
                />
            </label>

            <GalaxyField
                label="Galaxy (which body of knowledge this planet joins)"
                value={galaxy}
                onChange={setGalaxy}
            />

            <OwnersField value={owners} onChange={setOwners} />

            <div className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
                REFs this skill instantiates (frontmatter `refs:`)
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
                                        className={cn(
                                            'rounded-full border px-2 py-0.5 text-[11px]',
                                            refs.includes(ref.id)
                                                ? 'border-link/70 bg-primary/15 text-link'
                                                : 'border-border text-muted-foreground hover:text-foreground',
                                        )}
                                    >
                                        {shortName(ref.id)}
                                    </button>
                                ))}
                            </div>
                        );
                    })}
                </div>
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
