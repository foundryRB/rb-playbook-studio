import { useCallback, useEffect, useRef, useState } from 'react';
import type { Components } from 'react-markdown';

import type {
    AgentResponse,
    DoorResponse,
    GalaxyResponse,
    NebulaDetailResponse,
    PlaybookResponse,
    RefDetailResponse,
    SkillFileResponse,
    SkillResponse,
} from '@/models';
import { UniverseSceneApp } from '@/three/UniverseScene';
import { apiFetch } from '@/utils';
import { galaxyDomains, useGraph } from '@/viewmodels/graph';
import { normalizeToken } from '@/viewmodels/graph/panel.model';
import { buildUniverseModel, splitSkillFiles } from '@/viewmodels/graph/scene.model';
import type { SceneBody, UniverseModel } from '@/viewmodels/graph/scene.model';
import { useNebulae } from '@/viewmodels/nebulae';
import { Spinner } from '@/views/atoms/Spinner';
import { MapFilters } from '@/views/molecules/MapFilters';
import { UniversePanel, type PanelDoc } from '@/views/organisms/UniversePanel';

declare global {
    interface Window {
        __universe3d?: () => unknown;
        __universe3dSnapshot?: () => unknown;
        __universe3dRenderOnce?: () => void;
        __universe3dApp?: UniverseSceneApp;
        __universe3dDoc?: () => unknown;
    }
}

/** The one React boundary that owns the SceneApp (REF-ThreeJS: create on
 *  mount, dispose on unmount; three.js objects never enter React state).
 *  Reading happens in a DOM panel with the studio's own markdown renderer
 *  and travel-links; inside a headset the scene's canvas panel takes over. */
export const Universe3D = () => {
    const graph = useGraph((state) => state.graph);
    const loading = useGraph((state) => state.loading);
    const error = useGraph((state) => state.error);
    const load = useGraph((state) => state.load);
    const nebulae = useNebulae((state) => state.nebulae);
    const loadNebulae = useNebulae((state) => state.load);
    const visibleDomains = useGraph((state) => state.visibleDomains);
    const showSkills = useGraph((state) => state.showSkills);
    const showAgents = useGraph((state) => state.showAgents);
    const showDoors = useGraph((state) => state.showDoors);
    const containerRef = useRef<HTMLDivElement>(null);
    const appRef = useRef<UniverseSceneApp | null>(null);
    const modelRef = useRef<UniverseModel | null>(null);
    const docRef = useRef<PanelDoc | null>(null);
    const [doc, setDocState] = useState<PanelDoc | null>(null);
    const [presenting, setPresenting] = useState(false);
    const [worlds, setWorlds] = useState<{ done: number; total: number } | null>(null);
    const [veilDismissed, setVeilDismissed] = useState(false);
    const [galaxyContext, setGalaxyContext] = useState<string | null>(null);

    const setDoc = useCallback((next: PanelDoc | null) => {
        docRef.current = next;
        setDocState(next);
    }, []);

    const closeDoc = useCallback(() => {
        setDoc(null);
        appRef.current?.closePanel();
        appRef.current?.clearBonds();
    }, [setDoc]);

    const resetFilters = useGraph((state) => state.resetFilters);

    const travel = useCallback(
        (id: string) => {
            const app = appRef.current;
            if (!app) {
                return;
            }
            // A filtered-out destination would land the camera on nothing;
            // widen the view first.
            if (!app.isBodyVisible(id)) {
                resetFilters();
                app.applyFilter({
                    galaxy: null,
                    domains: null,
                    showSkills: true,
                    showAgents: true,
                    showDoors: true,
                });
            }
            app.select(id);
        },
        [resetFilters],
    );

    useEffect(() => {
        void load();
        void loadNebulae();
    }, [load, loadNebulae]);

    useEffect(() => {
        const container = containerRef.current;
        // The unearned zone rides along: wait for the nebula roster to settle
        // (it resolves to [] on failure) so the scene builds exactly once.
        if (!container || !graph || nebulae === null) {
            return;
        }
        const model = buildUniverseModel(graph, nebulae);
        modelRef.current = model;
        const app = new UniverseSceneApp(container, model, (body) => {
            // Carter's bonds: a planet, agent, or door belongs to its home
            // system but stays bound to every sun it cites; selection shows
            // the bonds.
            if (body.kind === 'planet' || body.kind === 'agent' || body.kind === 'door') {
                const cited = graph.edges
                    .filter(
                        (e) =>
                            (e.kind === 'skill-to-ref' ||
                                e.kind === 'door-to-ref' ||
                                e.kind === 'agent-to-ref') &&
                            e.source === body.id,
                    )
                    .map((e) => e.target)
                    .slice(1);
                app.showBonds(body.id, cited);
                if (body.kind === 'agent') {
                    app.showRoute(body.id);
                }
            } else {
                app.clearBonds();
            }
            void openDocument(body).then((next) => {
                if (!next) {
                    return;
                }
                docRef.current = next;
                setDocState(next);
                if (app.isPresenting()) {
                    app.showDocument(next.title, next.meta, next.markdown, next.accent);
                }
            });
        });
        appRef.current = app;
        app.onWorldProgress = (done, total) => {
            setWorlds(done >= total ? null : { done, total });
        };
        const pending = (app.stats() as { texturesPending: number }).texturesPending;
        setWorlds(pending > 0 ? { done: 0, total: pending } : null);
        setVeilDismissed(false);
        app.onGalaxyContext = (name) => {
            setGalaxyContext(name);
        };
        app.onXrPresence = (isPresenting) => {
            setPresenting(isPresenting);
            const current = docRef.current;
            if (isPresenting && current) {
                app.showDocument(current.title, current.meta, current.markdown, current.accent);
            }
            if (!isPresenting) {
                app.closePanel();
            }
        };
        window.__universe3d = () => app.stats();
        window.__universe3dSnapshot = () => app.snapshot();
        window.__universe3dRenderOnce = () => app.renderOnce();
        window.__universe3dApp = app;
        window.__universe3dDoc = () => docRef.current;
        return () => {
            delete window.__universe3d;
            delete window.__universe3dSnapshot;
            delete window.__universe3dRenderOnce;
            delete window.__universe3dApp;
            delete window.__universe3dDoc;
            appRef.current = null;
            app.dispose();
        };
        // The doc panel lives in React state; only new corpus data (the graph
        // or the nebula roster) rebuilds the scene.
    }, [graph, nebulae]);

    useEffect(() => {
        const onKey = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                closeDoc();
            }
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [closeDoc]);

    // Filters belong to a galaxy: leaving its sphere of influence clears
    // them, and while inside one they scope to its bodies only.
    useEffect(() => {
        resetFilters();
    }, [galaxyContext, resetFilters]);

    useEffect(() => {
        appRef.current?.applyFilter({
            galaxy: galaxyContext,
            domains: visibleDomains,
            showSkills,
            showAgents,
            showDoors,
        });
    }, [graph, galaxyContext, visibleDomains, showSkills, showAgents, showDoors]);

    if (error) {
        return <p className="text-sm text-destructive">{error}</p>;
    }

    const resolveTarget = (token: string): string | null => {
        const id = normalizeToken(token);
        return modelRef.current?.bodies.some((b) => b.id === id) ? id : null;
    };

    const linkComponents: Components = {
        // Wide tables scroll inside their own box; the panel never squeezes.
        table: ({ children }) => (
            <div className="overflow-x-auto">
                <table>{children}</table>
            </div>
        ),
        a: ({ href, children }) => {
            const target = resolveTarget(href ?? '');
            if (target) {
                return (
                    <button
                        onClick={() => travel(target)}
                        className="font-medium text-link underline decoration-link/50 underline-offset-2 hover:decoration-link"
                    >
                        {children}
                    </button>
                );
            }
            if (href && /^https?:\/\//.test(href)) {
                return (
                    <a href={href} target="_blank" rel="noreferrer">
                        {children}
                    </a>
                );
            }
            return <span>{children}</span>;
        },
        code: ({ className, children }) => {
            const text = typeof children === 'string' ? children : undefined;
            const target = text && !text.includes('\n') ? resolveTarget(text) : null;
            if (target) {
                return (
                    <button
                        onClick={() => travel(target)}
                        title={`Travel to ${target}`}
                        className="rounded border border-link/40 bg-primary/10 px-1 py-0.5 font-mono text-[0.8em] text-link hover:bg-primary/20"
                    >
                        {text}
                    </button>
                );
            }
            return <code className={className}>{children}</code>;
        },
    };

    return (
        <div className="relative h-full w-full">
            {loading && !graph && <Spinner />}
            <div ref={containerRef} className="absolute inset-0" />

            <div className="pointer-events-none absolute left-3 top-12 z-10 flex flex-col gap-1.5">
                <div className="pointer-events-auto flex items-center gap-2">
                    <button
                        onClick={() => {
                            closeDoc();
                            appRef.current?.flyHome();
                        }}
                        className="rounded-full border border-border bg-background/80 px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground hover:text-foreground"
                    >
                        home
                    </button>
                    {doc && (
                        <span className="rounded-full bg-background/80 px-2.5 py-0.5 text-[11px] text-muted-foreground">
                            {doc.title}
                        </span>
                    )}
                </div>
                <p className="text-[10px] text-muted-foreground/70">
                    click a body to read · drag to orbit · scroll to zoom · double-click space: home
                    · esc closes
                </p>
                {galaxyContext && (
                    <div className="pointer-events-auto max-w-[560px] space-y-1 rounded-lg bg-background/70 p-1.5 backdrop-blur">
                        <div className="flex items-center justify-between gap-2 px-1">
                            <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/80">
                                {galaxyContext} galaxy
                            </p>
                            <button
                                onClick={() => appRef.current?.clearGalaxyContext()}
                                title="Leave this galaxy's focus (filters clear)"
                                className="text-[10px] text-muted-foreground/70 hover:text-foreground"
                            >
                                ✕
                            </button>
                        </div>
                        <MapFilters domains={galaxyDomains(graph, galaxyContext)} />
                    </div>
                )}
            </div>

            {doc && !presenting && (
                <UniversePanel
                    doc={doc}
                    graph={graph}
                    components={linkComponents}
                    onTravel={travel}
                    onClose={closeDoc}
                />
            )}

            {worlds && !veilDismissed && (
                <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-4 bg-[#02040a]/85 backdrop-blur-sm">
                    <Spinner />
                    <p className="text-sm font-medium text-foreground">charting the universe</p>
                    <div className="h-1.5 w-56 overflow-hidden rounded-full bg-secondary">
                        <div
                            className="h-full rounded-full bg-primary transition-[width] duration-200"
                            style={{ width: `${Math.round((worlds.done / worlds.total) * 100)}%` }}
                        />
                    </div>
                    <p className="text-xs text-muted-foreground">
                        forging world {Math.min(worlds.done + 1, worlds.total)} of {worlds.total}
                    </p>
                    <button
                        onClick={() => setVeilDismissed(true)}
                        className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground hover:text-foreground"
                    >
                        enter anyway
                    </button>
                </div>
            )}
        </div>
    );
};

/** Fetch the selected body's document: a typed payload for the DOM panel and
 *  raw markdown for the in-headset canvas panel. */
async function openDocument(body: SceneBody): Promise<PanelDoc | null> {
    const node = body.node;
    const galaxyMeta = body.galaxy ? ` in the ${body.galaxy} galaxy` : '';
    try {
        if (body.kind === 'galaxy' && body.galaxy) {
            const galaxy = await apiFetch<GalaxyResponse>(`/api/galaxies/${body.galaxy}`);
            return {
                id: body.id,
                title: galaxy.title,
                meta: 'a galaxy: one body of earned knowledge',
                markdown: stripFrontmatter(galaxy.raw),
                accent: body.color,
                payload: { kind: 'galaxy', galaxy },
            };
        }
        if (body.kind === 'nebula') {
            const nebula = await apiFetch<NebulaDetailResponse>(`/api/nebulae/${body.label}`);
            return {
                id: body.id,
                title: nebula.territory,
                meta: 'a nebula: unearned stardust, quarantined until smelted',
                markdown: nebula.raw,
                accent: body.color,
                payload: { kind: 'nebula', nebula },
            };
        }
        if (body.kind === 'moon' && body.moonOf && body.file) {
            const file = await apiFetch<SkillFileResponse>(
                `/api/skills/${body.moonOf}/files/${body.file}`,
            );
            const fenced = /\.(md|markdown)$/i.test(body.file)
                ? file.content
                : `\`\`\`\n${file.content}\n\`\`\``;
            return {
                id: body.id,
                title: body.file,
                meta: `moon of ${body.moonOf}${galaxyMeta}`,
                markdown: fenced,
                accent: body.color,
                payload: {
                    kind: 'moon',
                    moonOf: body.moonOf,
                    file: body.file,
                    content: file.content,
                },
            };
        }
        if (body.kind === 'ring' && body.moonOf && body.files) {
            // A ring reads as its folder: the file roster, and the README the
            // folder fronts itself with when it has one.
            const folder = body.id.slice(`ring:${body.moonOf}/`.length);
            const readme = body.files.find((f) => /^[^/]+\/README\.md$/i.test(f));
            const markdown = readme
                ? (await apiFetch<SkillFileResponse>(`/api/skills/${body.moonOf}/files/${readme}`))
                      .content
                : '';
            return {
                id: body.id,
                title: folder,
                meta: `ring of ${body.moonOf}${galaxyMeta}: ${body.files.length} file${body.files.length === 1 ? '' : 's'}`,
                markdown,
                accent: body.color,
                payload: { kind: 'ring', moonOf: body.moonOf, folder, files: body.files },
            };
        }
        if (node?.kind === 'ref') {
            const ref = await apiFetch<RefDetailResponse>(`/api/refs/${node.id}`);
            return {
                id: body.id,
                title: node.id,
                meta: `sun${galaxyMeta} (${ref.domain})`,
                markdown: stripFrontmatter(ref.raw),
                accent: body.color,
                payload: { kind: 'ref', ref },
            };
        }
        if (node?.kind === 'skill') {
            const skill = await apiFetch<SkillResponse>(`/api/skills/${node.id}`);
            const { folders, loose } = splitSkillFiles(node.moons ?? []);
            const held = [
                loose.length ? `${loose.length} moon${loose.length === 1 ? '' : 's'}` : '',
                folders.size ? `${folders.size} ring${folders.size === 1 ? '' : 's'}` : '',
            ].filter(Boolean);
            const moons = held.length ? ` with ${held.join(' and ')}` : '';
            return {
                id: body.id,
                title: node.id,
                meta: `planet${galaxyMeta}${moons}`,
                markdown: stripFrontmatter(skill.body),
                accent: body.color,
                payload: { kind: 'skill', skill },
            };
        }
        if (node?.kind === 'agent') {
            const agent = await apiFetch<AgentResponse>(`/api/agents/${node.id}`);
            return {
                id: body.id,
                title: node.id,
                meta: `agent${galaxyMeta}`,
                markdown: stripFrontmatter(agent.body),
                accent: body.color,
                payload: { kind: 'agent', agent },
            };
        }
        if (node?.kind === 'playbook') {
            const playbook = await apiFetch<PlaybookResponse>('/api/playbook');
            return {
                id: body.id,
                title: playbook.title,
                meta: 'the universe index',
                markdown: stripFrontmatter(playbook.raw),
                accent: body.color,
                payload: { kind: 'playbook', playbook },
            };
        }
        if (node) {
            const door = await apiFetch<DoorResponse>(`/api/doors/${node.id}`);
            return {
                id: body.id,
                title: node.id,
                meta: `declared ${door.kind} door${galaxyMeta}`,
                markdown: stripFrontmatter(door.raw),
                accent: body.color,
                payload: { kind: 'door', door },
            };
        }
        return null;
    } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load the document.';
        return {
            id: body.id,
            title: body.label,
            meta: body.kind,
            markdown: message,
            accent: body.color,
            payload: { kind: 'error', message },
        };
    }
}

const stripFrontmatter = (raw: string): string => raw.replace(/^---[\s\S]*?---\n/, '');
