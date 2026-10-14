import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useDoorDetail } from '@/viewmodels/doordetail';
import { useGalaxyDetail } from '@/viewmodels/galaxydetail';
import { useGraph } from '@/viewmodels/graph';
import { useNav } from '@/viewmodels/nav';
import { Spinner } from '@/views/atoms/Spinner';
import { corpusLinkComponents } from '@/views/molecules/CorpusLink';
import { Markdown } from '@/views/molecules/Markdown';
import { ValidationBanner } from '@/views/molecules/ValidationBanner';

const stripFrontmatter = (raw: string): string => raw.replace(/^---[\s\S]*?---\n/, '');

/** A declared door's card (MCP or RAG): purpose and doctrine straight from the
 *  corpus, edited whole behind the gates by whoever may change it. Never
 *  interface (the server declares its own) or binding (environment). */
export const DoorReader = () => {
    const door = useDoorDetail((state) => state.door);
    const loading = useDoorDetail((state) => state.loading);
    const error = useDoorDetail((state) => state.error);
    const editing = useDoorDetail((state) => state.editing);
    const draft = useDoorDetail((state) => state.draft);
    const saving = useDoorDetail((state) => state.saving);
    const saveError = useDoorDetail((state) => state.saveError);
    const lastReport = useDoorDetail((state) => state.lastReport);
    const startEdit = useDoorDetail((state) => state.startEdit);
    const setDraft = useDoorDetail((state) => state.setDraft);
    const cancelEdit = useDoorDetail((state) => state.cancelEdit);
    const save = useDoorDetail((state) => state.save);
    const select = useGraph((state) => state.select);
    const selectGalaxy = useGalaxyDetail((state) => state.select);
    const setView = useNav((state) => state.setView);

    if (loading) {
        return <Spinner />;
    }
    if (error) {
        return <p className="text-sm text-destructive">{error}</p>;
    }
    if (!door) {
        return <p className="text-sm text-muted-foreground">Pick a door on the map.</p>;
    }

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-xl font-bold">{door.name}</h1>
                <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-amber-600 ring-1 ring-inset ring-amber-500/30 dark:text-amber-300">
                    {door.kind} door
                </span>
                <button
                    onClick={() => {
                        selectGalaxy(door.galaxy);
                        setView('galaxy');
                    }}
                    className="rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground hover:text-foreground"
                >
                    {door.galaxy} galaxy
                </button>
                {door.can_edit && !editing && (
                    <Button
                        variant="outline"
                        className="ml-auto h-6 px-2.5 text-xs"
                        onClick={startEdit}
                    >
                        Edit
                    </Button>
                )}
            </div>
            {door.refs.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 text-xs">
                    <span className="text-muted-foreground">doctrine suns:</span>
                    {door.refs.map((ref) => (
                        <button
                            key={ref}
                            onClick={() => {
                                select(ref);
                                setView('ref');
                            }}
                            className="rounded-md border border-border px-2 py-0.5 font-medium text-link hover:bg-secondary/60"
                        >
                            {ref}
                        </button>
                    ))}
                </div>
            )}
            {lastReport && <ValidationBanner report={lastReport} />}
            <Card>
                <CardContent className="p-5">
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
                                <Button variant="outline" disabled={saving} onClick={cancelEdit}>
                                    Cancel
                                </Button>
                            </div>
                        </>
                    ) : (
                        <Markdown components={corpusLinkComponents}>
                            {stripFrontmatter(door.raw)}
                        </Markdown>
                    )}
                </CardContent>
            </Card>
            <p className="text-xs text-muted-foreground">
                A declared door: the corpus holds its purpose and doctrine, the server declares its
                own interface at connect, and the binding (endpoint plus credential) lives in your
                environment.
            </p>
        </div>
    );
};
