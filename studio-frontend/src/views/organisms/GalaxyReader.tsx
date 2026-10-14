import { Card, CardContent } from '@/components/ui/card';
import { useGalaxyDetail } from '@/viewmodels/galaxydetail';
import { useGraph } from '@/viewmodels/graph';
import { useNav } from '@/viewmodels/nav';
import { Spinner } from '@/views/atoms/Spinner';
import { corpusLinkComponents } from '@/views/molecules/CorpusLink';
import { Markdown } from '@/views/molecules/Markdown';

/** A galaxy's GALAXY.md: the routing table and registries that make one body
 *  of earned knowledge navigable. */
export const GalaxyReader = () => {
    const galaxyDoc = useGalaxyDetail((state) => state.galaxyDoc);
    const loading = useGalaxyDetail((state) => state.loading);
    const error = useGalaxyDetail((state) => state.error);
    const enterGalaxy = useGraph((state) => state.enterGalaxy);
    const setView = useNav((state) => state.setView);

    if (loading) {
        return <Spinner />;
    }
    if (error) {
        return <p className="text-sm text-destructive">{error}</p>;
    }
    if (!galaxyDoc) {
        return <p className="text-sm text-muted-foreground">Pick a galaxy on the map.</p>;
    }

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-xl font-bold">{galaxyDoc.title}</h1>
                <span className="rounded-full bg-indigo-500/15 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-indigo-600 ring-1 ring-inset ring-indigo-500/30 dark:text-indigo-300">
                    galaxy
                </span>
                <button
                    onClick={() => {
                        enterGalaxy(galaxyDoc.name);
                        setView('map');
                    }}
                    className="rounded-full border border-border px-2 py-0.5 text-[11px] text-muted-foreground hover:text-foreground"
                >
                    open in the map
                </button>
            </div>
            {galaxyDoc.sections.map((section) => (
                <Card key={section.title}>
                    <CardContent className="p-5">
                        <h2 className="mb-2 text-sm font-semibold">{section.title}</h2>
                        <Markdown components={corpusLinkComponents}>{section.body}</Markdown>
                    </CardContent>
                </Card>
            ))}
        </div>
    );
};
