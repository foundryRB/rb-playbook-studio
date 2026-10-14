import { useEffect, useMemo, useState } from 'react';

import type { GraphNodeResponse, GraphResponse } from '@/models';
import {
    DOMAIN_COLORS,
    DOOR_KINDS,
    HOME_EDGE_KINDS,
    isPlanetKind,
    useGraph,
} from '@/viewmodels/graph';
import { useAgentDetail } from '@/viewmodels/agentdetail';
import { useDoorDetail } from '@/viewmodels/doordetail';
import { useGalaxyDetail } from '@/viewmodels/galaxydetail';
import { selectCanCreate, useIdentity } from '@/viewmodels/identity';
import { useNav, type StudioView } from '@/viewmodels/nav';
import { useSkillDetail } from '@/viewmodels/skilldetail';
import { cn } from '@/utils';

const shortName = (id: string): string => id.replace(/^REF-/, '');

/** The create entry points, shown to whoever may create in some galaxy. */
const CREATE_ENTRIES: [StudioView, string][] = [
    ['create', '+ REF'],
    ['createskill', '+ Skill'],
    ['createagent', '+ Agent'],
    ['createdoor', '+ Card'],
];

interface RefBranch {
    ref: GraphNodeResponse;
    children: GraphNodeResponse[];
}

interface GalaxyGroup {
    name: string;
    refs: RefBranch[];
    /** Planets whose first edge points at no REF: a governance violation, not
     *  a bucket. Every skill and door must earn a REF (REF-Universe). */
    orphans: GraphNodeResponse[];
}

interface Tree {
    groups: GalaxyGroup[];
    galaxyOf: Map<string, string>;
    parentRefOf: Map<string, string>;
}

/** The playbook, as a nested tree: each galaxy holds its REFs (sorted by
 *  domain, so colours run in blocks instead of a rainbow), and each REF holds
 *  the skills and doors that cite it first. Skills/doors that cite no REF
 *  surface as flagged orphans, never hidden. */
function buildTree(graph: GraphResponse | null): Tree {
    const galaxyOf = new Map<string, string>();
    const parentRefOf = new Map<string, string>();
    if (!graph) {
        return { groups: [], galaxyOf, parentRefOf };
    }
    for (const node of graph.nodes) {
        if (node.galaxy) {
            galaxyOf.set(node.id, node.galaxy);
        }
    }
    const firstRefOf = (planetId: string): string | null => {
        const edge = graph.edges.find((e) => HOME_EDGE_KINDS.has(e.kind) && e.source === planetId);
        return edge ? edge.target : null;
    };
    const names = [
        ...new Set(graph.nodes.map((n) => n.galaxy).filter((g): g is string => !!g)),
    ].sort();
    const byDomainThenId = (a: GraphNodeResponse, b: GraphNodeResponse): number =>
        (a.domain ?? '').localeCompare(b.domain ?? '') || a.id.localeCompare(b.id);
    const childRank = (n: GraphNodeResponse): number =>
        n.kind === 'skill' ? 0 : n.kind === 'agent' ? 1 : 2;
    const childSort = (a: GraphNodeResponse, b: GraphNodeResponse): number =>
        childRank(a) - childRank(b) || a.id.localeCompare(b.id);

    // A planet hangs under the REF it first cites, wherever that REF lives:
    // its own galaxy is only where its file sits (a skill in maker may cite a
    // craft REF). Grouping is global, so cross-galaxy citations nest correctly
    // and only a truly REF-less planet counts as an orphan.
    const kidsByRef = new Map<string, GraphNodeResponse[]>();
    const orphansByGalaxy = new Map<string, GraphNodeResponse[]>();
    for (const planet of graph.nodes.filter((n) => isPlanetKind(n.kind))) {
        const refId = firstRefOf(planet.id);
        if (refId) {
            parentRefOf.set(planet.id, refId);
            (kidsByRef.get(refId) ?? kidsByRef.set(refId, []).get(refId)!).push(planet);
        } else {
            const key = planet.galaxy ?? '';
            (orphansByGalaxy.get(key) ?? orphansByGalaxy.set(key, []).get(key)!).push(planet);
        }
    }

    const groups = names.map((name): GalaxyGroup => {
        const refs = graph.nodes
            .filter((n) => n.galaxy === name && n.kind === 'ref')
            .sort(byDomainThenId);
        return {
            name,
            refs: refs.map((ref) => ({
                ref,
                children: (kidsByRef.get(ref.id) ?? []).slice().sort(childSort),
            })),
            orphans: (orphansByGalaxy.get(name) ?? []).slice().sort(childSort),
        };
    });
    return { groups, galaxyOf, parentRefOf };
}

export const SidebarNav = () => {
    const graph = useGraph((state) => state.graph);
    const load = useGraph((state) => state.load);
    const select = useGraph((state) => state.select);
    const selectedRef = useGraph((state) => state.selectedRef);
    const selectSkill = useSkillDetail((state) => state.select);
    const selectedSkill = useSkillDetail((state) => state.selectedSkill);
    const selectAgent = useAgentDetail((state) => state.select);
    const selectedAgent = useAgentDetail((state) => state.selectedAgent);
    const selectDoor = useDoorDetail((state) => state.select);
    const selectedDoor = useDoorDetail((state) => state.selectedDoor);
    const selectGalaxy = useGalaxyDetail((state) => state.select);
    const view = useNav((state) => state.view);
    const setView = useNav((state) => state.setView);
    const canCreate = useIdentity(selectCanCreate);
    const expanded = useNav((state) => state.expanded);
    const toggleExpanded = useNav((state) => state.toggleExpanded);
    const setExpanded = useNav((state) => state.setExpanded);
    const [query, setQuery] = useState('');

    useEffect(() => {
        void load();
    }, [load]);

    const q = query.trim().toLowerCase();
    const matches = (node: GraphNodeResponse): boolean => !q || node.id.toLowerCase().includes(q);

    const { groups, galaxyOf, parentRefOf } = useMemo(() => buildTree(graph), [graph]);

    // Reveal the active page in the tree: open its galaxy (and, for a skill or
    // door, the REF it hangs under), so a deep-link lands somewhere visible.
    useEffect(() => {
        const openAncestors = (nodeId: string | null, isPlanet: boolean): void => {
            if (!nodeId) {
                return;
            }
            // A planet lives under its REF, in the REF's galaxy; a REF (or an
            // orphan planet) lives in its own galaxy.
            const refId = isPlanet ? parentRefOf.get(nodeId) : null;
            const galaxy = galaxyOf.get(refId ?? nodeId);
            if (galaxy) {
                setExpanded(`galaxy:${galaxy}`, true);
            }
            if (refId) {
                setExpanded(`ref:${refId}`, true);
            }
        };
        if (view === 'ref') openAncestors(selectedRef, false);
        if (view === 'skill') openAncestors(selectedSkill, true);
        if (view === 'agent') openAncestors(selectedAgent, true);
        if (view === 'door') openAncestors(selectedDoor, true);
    }, [
        view,
        selectedRef,
        selectedSkill,
        selectedAgent,
        selectedDoor,
        galaxyOf,
        parentRefOf,
        setExpanded,
    ]);

    const openRef = (id: string) => {
        select(id);
        setView('ref');
    };
    const openSkill = (id: string) => {
        selectSkill(id);
        setView('skill');
    };
    const openAgent = (id: string) => {
        selectAgent(id);
        setView('agent');
    };
    const openDoor = (id: string) => {
        selectDoor(id);
        setView('door');
    };
    const openGalaxy = (name: string) => {
        selectGalaxy(name);
        setView('galaxy');
    };

    const itemClass = (isActive: boolean) =>
        cn(
            'flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-[13px]',
            isActive
                ? 'bg-secondary font-semibold text-foreground'
                : 'text-muted-foreground hover:bg-secondary/60 hover:text-foreground',
        );

    const planetRow = (planet: GraphNodeResponse, flagged = false) => {
        const isDoor = DOOR_KINDS.has(planet.kind);
        const isAgent = planet.kind === 'agent';
        const active = isDoor
            ? view === 'door' && selectedDoor === planet.id
            : isAgent
              ? view === 'agent' && selectedAgent === planet.id
              : view === 'skill' && selectedSkill === planet.id;
        return (
            <li key={planet.id}>
                <button
                    onClick={() =>
                        isDoor
                            ? openDoor(planet.id)
                            : isAgent
                              ? openAgent(planet.id)
                              : openSkill(planet.id)
                    }
                    title={
                        flagged
                            ? `${planet.summary}\n\nLinks no REF — must cite one.`
                            : planet.summary
                    }
                    className={cn(itemClass(active), 'min-w-0 text-[12px]')}
                >
                    <span
                        className={cn(
                            'h-1.5 w-1.5 shrink-0',
                            isDoor
                                ? 'rounded-[2px] bg-amber-500'
                                : isAgent
                                  ? 'rotate-45 rounded-[1px] bg-lime-500'
                                  : 'rounded-full bg-slate-500',
                            flagged && 'bg-destructive',
                        )}
                    />
                    <span className="truncate">{planet.id}</span>
                </button>
            </li>
        );
    };

    return (
        <nav className="flex h-full flex-col gap-3">
            <button
                onClick={() => setView('playbook')}
                className={cn(
                    'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] font-semibold',
                    view === 'playbook'
                        ? 'bg-secondary text-foreground'
                        : 'text-foreground hover:bg-secondary/60',
                )}
            >
                <span className="h-2 w-2 shrink-0 rounded-full bg-primary" />
                AI-PLAYBOOK
            </button>
            <input
                type="search"
                placeholder="Find a sun, planet, or door..."
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="w-full rounded-md border border-input bg-background/60 px-3 py-1.5 text-sm outline-none placeholder:text-muted-foreground/60 focus:ring-1 focus:ring-ring"
            />
            <div className="flex-1 overflow-y-auto overflow-x-hidden pr-1">
                {groups.map((group) => {
                    let branches = group.refs;
                    let orphans = group.orphans;
                    if (q) {
                        branches = group.refs
                            .filter((b) => matches(b.ref) || b.children.some(matches))
                            .map((b) => ({
                                ref: b.ref,
                                children: matches(b.ref) ? b.children : b.children.filter(matches),
                            }));
                        orphans = group.orphans.filter(matches);
                        if (branches.length === 0 && orphans.length === 0) {
                            return null;
                        }
                    }
                    const galaxyOpen = q ? true : (expanded[`galaxy:${group.name}`] ?? false);
                    return (
                        <div key={group.name} className="mb-3">
                            <div className="flex items-center">
                                <button
                                    onClick={() => toggleExpanded(`galaxy:${group.name}`)}
                                    title={galaxyOpen ? 'Collapse' : 'Expand'}
                                    className="px-1 text-[10px] text-muted-foreground/70 hover:text-foreground"
                                >
                                    {galaxyOpen ? '▾' : '▸'}
                                </button>
                                <button
                                    onClick={() => openGalaxy(group.name)}
                                    title={`Open the ${group.name} galaxy's GALAXY.md`}
                                    className="flex-1 rounded-md px-1 py-0.5 text-left text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/80 hover:bg-secondary/60 hover:text-foreground"
                                >
                                    {group.name} galaxy
                                </button>
                            </div>
                            {galaxyOpen && (
                                <ul>
                                    {branches.map((branch) => {
                                        const hasChildren = branch.children.length > 0;
                                        const refOpen = q
                                            ? true
                                            : (expanded[`ref:${branch.ref.id}`] ?? false);
                                        return (
                                            <li key={branch.ref.id}>
                                                <div className="flex items-center">
                                                    {hasChildren ? (
                                                        <button
                                                            onClick={() =>
                                                                toggleExpanded(
                                                                    `ref:${branch.ref.id}`,
                                                                )
                                                            }
                                                            title={refOpen ? 'Collapse' : 'Expand'}
                                                            className="px-1 text-[9px] text-muted-foreground/60 hover:text-foreground"
                                                        >
                                                            {refOpen ? '▾' : '▸'}
                                                        </button>
                                                    ) : (
                                                        <span className="w-[15px] shrink-0" />
                                                    )}
                                                    <button
                                                        onClick={() => openRef(branch.ref.id)}
                                                        title={branch.ref.summary}
                                                        className={itemClass(
                                                            view === 'ref' &&
                                                                selectedRef === branch.ref.id,
                                                        )}
                                                    >
                                                        <span
                                                            className="h-2 w-2 shrink-0 rounded-full"
                                                            style={{
                                                                backgroundColor:
                                                                    DOMAIN_COLORS[
                                                                        branch.ref.domain ?? ''
                                                                    ] ?? '#64748b',
                                                            }}
                                                        />
                                                        <span className="flex-1 truncate">
                                                            {shortName(branch.ref.id)}
                                                        </span>
                                                        {hasChildren && (
                                                            <span className="shrink-0 rounded-full bg-secondary px-1.5 text-[10px] text-muted-foreground/70">
                                                                {branch.children.length}
                                                            </span>
                                                        )}
                                                    </button>
                                                </div>
                                                {hasChildren && refOpen && (
                                                    <ul className="ml-[15px] border-l border-border/50 pl-1">
                                                        {branch.children.map((c) => planetRow(c))}
                                                    </ul>
                                                )}
                                            </li>
                                        );
                                    })}
                                    {orphans.length > 0 && (
                                        <li className="mt-1.5">
                                            <p className="flex items-center gap-1 px-2 text-[10px] font-semibold uppercase tracking-wide text-destructive/90">
                                                <span>⚠</span> unlinked — must cite a REF
                                            </p>
                                            <ul className="ml-[15px] border-l border-destructive/40 pl-1">
                                                {orphans.map((o) => planetRow(o, true))}
                                            </ul>
                                        </li>
                                    )}
                                </ul>
                            )}
                        </div>
                    );
                })}

                {q &&
                    groups.every(
                        (g) =>
                            g.refs.every((b) => !matches(b.ref) && !b.children.some(matches)) &&
                            !g.orphans.some(matches),
                    ) && (
                        <p className="px-2 text-xs text-muted-foreground">
                            No match for "{query}".
                        </p>
                    )}
            </div>
            {canCreate && (
                <div className="grid grid-cols-2 gap-1.5">
                    {CREATE_ENTRIES.map(([target, label]) => (
                        <button
                            key={target}
                            onClick={() => setView(target)}
                            className={cn(
                                'whitespace-nowrap rounded-md border border-dashed border-border px-2 py-1.5 text-xs font-medium',
                                view === target
                                    ? 'border-link/60 text-link'
                                    : 'text-muted-foreground hover:border-link/40 hover:text-foreground',
                            )}
                        >
                            {label}
                        </button>
                    ))}
                </div>
            )}
        </nav>
    );
};
