import { useCallback } from 'react';

import { Button } from '@/components/ui/button';
import { cn } from '@/utils';
import { cardOpening, useCreateDoor } from '@/viewmodels/createdoor';
import { useDoorDetail } from '@/viewmodels/doordetail';
import { useGraph } from '@/viewmodels/graph';
import { useNav } from '@/viewmodels/nav';
import { GalaxyField, OwnersField } from '@/views/molecules/CreateFields';
import { ValidationBanner } from '@/views/molecules/ValidationBanner';

const FIELD_CLASSES =
    'w-full rounded-md border border-input bg-background/70 px-3 py-1.5 text-sm outline-none placeholder:text-muted-foreground/50 focus:ring-1 focus:ring-ring';

/** Declare a new MCP or RAG card in a galaxy: the whole card, behind the gates. */
export const CreateDoorForm = () => {
    const kind = useCreateDoor((state) => state.kind);
    const name = useCreateDoor((state) => state.name);
    const galaxy = useCreateDoor((state) => state.galaxy);
    const raw = useCreateDoor((state) => state.raw);
    const owners = useCreateDoor((state) => state.owners);
    const submitting = useCreateDoor((state) => state.submitting);
    const error = useCreateDoor((state) => state.error);
    const report = useCreateDoor((state) => state.report);
    const setKind = useCreateDoor((state) => state.setKind);
    const setName = useCreateDoor((state) => state.setName);
    const setGalaxy = useCreateDoor((state) => state.setGalaxy);
    const setRaw = useCreateDoor((state) => state.setRaw);
    const setOwners = useCreateDoor((state) => state.setOwners);
    const reset = useCreateDoor((state) => state.reset);
    const submit = useCreateDoor((state) => state.submit);

    const graphLoad = useGraph((state) => state.load);
    const selectDoor = useDoorDetail((state) => state.select);
    const setView = useNav((state) => state.setView);
    const chooseGalaxy = useCallback((value: string) => setGalaxy(value), [setGalaxy]);

    const onSubmit = async () => {
        const created = await submit();
        if (created) {
            reset();
            await graphLoad();
            selectDoor(created.name);
            setView('door');
        }
    };

    return (
        <div className="mx-auto flex max-w-2xl flex-col gap-4">
            <div>
                <h2 className="text-lg font-bold tracking-tight">New card</h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                    A declared door (MCP) or retrieval seat (RAG): its name, purpose and the earned
                    doctrine for using it well, filed in a galaxy and judged by the gates.
                </p>
            </div>

            <div className="flex gap-1.5">
                {(['mcp', 'rag'] as const).map((k) => (
                    <button
                        key={k}
                        onClick={() => setKind(k)}
                        className={cn(
                            'rounded-full border px-3 py-0.5 text-xs uppercase tracking-wider',
                            kind === k
                                ? 'border-link/70 bg-primary/15 text-link'
                                : 'border-border text-muted-foreground hover:text-foreground',
                        )}
                    >
                        {k}
                    </button>
                ))}
            </div>

            <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
                Name (kebab-case)
                <input
                    className={`${FIELD_CLASSES} font-mono`}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="estimatekit"
                />
            </label>

            <GalaxyField
                label="Galaxy (where the card is filed)"
                value={galaxy}
                onChange={chooseGalaxy}
            />

            <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
                <span className="flex items-center justify-between">
                    The card (frontmatter and doctrine)
                    <button
                        onClick={() => setRaw(cardOpening(kind, name.trim(), galaxy))}
                        className="rounded-md border border-border px-2 py-0.5 text-[11px] text-muted-foreground hover:text-foreground"
                    >
                        Fill the opening
                    </button>
                </span>
                <textarea
                    className={`${FIELD_CLASSES} h-64 font-mono text-xs`}
                    value={raw}
                    onChange={(e) => setRaw(e.target.value)}
                    spellCheck={false}
                />
            </label>

            <OwnersField value={owners} onChange={setOwners} />

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
