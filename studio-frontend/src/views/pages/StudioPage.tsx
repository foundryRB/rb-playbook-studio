import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/utils';
import { galaxyDomains, useGraph } from '@/viewmodels/graph';
import { useNav } from '@/viewmodels/nav';
import { AgentReader } from '@/views/organisms/AgentReader';
import { CreateAgentForm } from '@/views/organisms/CreateAgentForm';
import { CreateDoorForm } from '@/views/organisms/CreateDoorForm';
import { CreateRefForm } from '@/views/organisms/CreateRefForm';
import { CreateSkillForm } from '@/views/organisms/CreateSkillForm';
import { DoorReader } from '@/views/organisms/DoorReader';
import { GalaxyReader } from '@/views/organisms/GalaxyReader';
import { GovernanceRail } from '@/views/organisms/GovernanceRail';
import { MapFilters } from '@/views/molecules/MapFilters';
import { NebulaReader } from '@/views/organisms/NebulaReader';
import { PlaybookGraph } from '@/views/organisms/PlaybookGraph';
import { PlaybookReader } from '@/views/organisms/PlaybookReader';
import { RefReader } from '@/views/organisms/RefReader';
import { SidebarNav } from '@/views/organisms/SidebarNav';
import { SkillReader } from '@/views/organisms/SkillReader';
import { Universe3D } from '@/views/organisms/Universe3D';
import { UniverseMap } from '@/views/organisms/UniverseMap';

export const StudioPage = () => {
    const view = useNav((state) => state.view);
    const setView = useNav((state) => state.setView);
    const galaxy = useGraph((state) => state.galaxy);
    const graph = useGraph((state) => state.graph);
    const exitToUniverse = useGraph((state) => state.exitToUniverse);

    // The 3D view is its own navigator, so it runs edge to edge: the tree
    // sidebar is redundant there, and stepping into it would tear down the
    // scene (and pay the reload) just to move. Every other view keeps the tree.
    const immersive = view === 'map3d';

    return (
        <div
            className={cn(
                'grid h-[calc(100vh-6.5rem)] grid-rows-[minmax(0,1fr)] gap-4',
                immersive ? 'grid-cols-[minmax(0,1fr)]' : 'grid-cols-[230px_minmax(0,1fr)]',
            )}
        >
            {!immersive && (
                <Card className="min-h-0 overflow-hidden">
                    <CardContent className="h-full p-3 pt-3">
                        <SidebarNav />
                    </CardContent>
                </Card>
            )}

            {view === 'map' && (
                <div className="app-map-row flex min-h-0 min-w-0 gap-4">
                    <Card className="relative min-w-0 flex-1 overflow-hidden">
                        <div className="absolute inset-0 p-1">
                            {galaxy === null ? <UniverseMap /> : <PlaybookGraph />}
                        </div>
                        <div className="absolute left-3 top-3 z-10 flex max-w-[70%] flex-col gap-1.5">
                            <div className="flex items-center gap-1.5 text-[11px] font-medium">
                                <button
                                    onClick={exitToUniverse}
                                    className={
                                        galaxy === null
                                            ? 'cursor-default rounded-full bg-primary px-2 py-0.5 text-primary-foreground'
                                            : 'rounded-full border border-border px-2 py-0.5 text-muted-foreground hover:text-foreground'
                                    }
                                >
                                    universe
                                </button>
                                {galaxy !== null && (
                                    <>
                                        <span className="text-muted-foreground">/</span>
                                        <span className="rounded-full bg-primary px-2 py-0.5 text-primary-foreground">
                                            {galaxy}
                                        </span>
                                    </>
                                )}
                            </div>
                            {galaxy !== null && (
                                <MapFilters domains={galaxyDomains(graph, galaxy)} />
                            )}
                        </div>
                        <button
                            onClick={() => setView('map3d')}
                            title="Browse the universe in 3D (VR-ready)"
                            className="absolute right-3 top-3 z-10 rounded-full border border-border bg-background/80 px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground hover:text-foreground"
                        >
                            3D
                        </button>
                    </Card>
                    <div className="min-h-0 w-[360px] shrink-0">
                        <GovernanceRail />
                    </div>
                </div>
            )}
            {view === 'map3d' && (
                <Card className="relative min-h-0 min-w-0 overflow-hidden">
                    <div className="absolute inset-0">
                        <Universe3D />
                    </div>
                    <button
                        onClick={() => setView('map')}
                        title="Back to the 2D universe map"
                        className="absolute left-3 top-3 z-10 rounded-full border border-border bg-background/80 px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground hover:text-foreground"
                    >
                        2D map
                    </button>
                </Card>
            )}
            {view === 'playbook' && (
                <div className="min-h-0 min-w-0 overflow-y-auto pr-1">
                    <PlaybookReader />
                </div>
            )}
            {view === 'galaxy' && (
                <div className="min-h-0 min-w-0 overflow-y-auto pr-1">
                    <GalaxyReader />
                </div>
            )}
            {view === 'nebula' && (
                <div className="min-h-0 min-w-0 overflow-y-auto pr-1">
                    <NebulaReader />
                </div>
            )}
            {view === 'door' && (
                <div className="min-h-0 min-w-0 overflow-y-auto pr-1">
                    <DoorReader />
                </div>
            )}
            {view === 'ref' && (
                <div className="min-h-0 min-w-0 overflow-y-auto pr-1">
                    <RefReader />
                </div>
            )}
            {view === 'skill' && (
                <div className="min-h-0 min-w-0 overflow-y-auto pr-1">
                    <SkillReader />
                </div>
            )}
            {view === 'agent' && (
                <div className="min-h-0 min-w-0 overflow-y-auto pr-1">
                    <AgentReader />
                </div>
            )}
            {view === 'create' && (
                <div className="min-h-0 min-w-0 overflow-y-auto pr-1">
                    <CreateRefForm />
                </div>
            )}
            {view === 'createskill' && (
                <div className="min-h-0 min-w-0 overflow-y-auto pr-1">
                    <CreateSkillForm />
                </div>
            )}
            {view === 'createagent' && (
                <div className="min-h-0 min-w-0 overflow-y-auto pr-1">
                    <CreateAgentForm />
                </div>
            )}
            {view === 'createdoor' && (
                <div className="min-h-0 min-w-0 overflow-y-auto pr-1">
                    <CreateDoorForm />
                </div>
            )}
        </div>
    );
};
