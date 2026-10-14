import { useEffect, useMemo, useState } from 'react';

import type { GraphResponse } from '@/models';
import {
    DOOR_KINDS,
    computeDomainArcs,
    computeLayout,
    REF_RADIUS,
    scopeToGalaxy,
    useGraph,
} from '@/viewmodels/graph';
import { useAgentDetail } from '@/viewmodels/agentdetail';
import { useDoorDetail } from '@/viewmodels/doordetail';
import { useGalaxyDetail } from '@/viewmodels/galaxydetail';
import { useNav } from '@/viewmodels/nav';
import { useSkillDetail } from '@/viewmodels/skilldetail';
import { Spinner } from '@/views/atoms/Spinner';

const EDGE_COLORS: Record<string, string> = {
    'playbook-to-ref': 'var(--graph-edge-hub)',
    'ref-to-ref': 'var(--graph-edge)',
    'skill-to-ref': 'var(--graph-edge-skill)',
    'door-to-ref': 'var(--graph-edge-skill)',
    'agent-to-ref': 'var(--graph-edge-skill)',
    'agent-to-skill': 'var(--graph-edge-skill)',
    'agent-to-door': 'var(--graph-edge-skill)',
};

const NODE_STROKE = 'var(--graph-node-stroke)';
const REF_LABEL = 'var(--graph-label)';
const SKILL_LABEL = 'var(--graph-label-muted)';

/** Fade-glide-fade choreography: labels/edges fade out, dots glide to the
 *  re-flowed circle, then labels/edges fade back in at the new geometry. */
const GLIDE_MS = 500;
const SETTLE_MS = 520;

const shortLabel = (id: string): string => id.replace(/^REF-/, '');

const truncated = (label: string): string => (label.length > 24 ? `${label.slice(0, 23)}…` : label);

const polarPoint = (radius: number, angle: number): [number, number] => [
    radius * Math.cos(angle),
    radius * Math.sin(angle),
];

const arcPath = (radius: number, start: number, end: number): string => {
    const [x1, y1] = polarPoint(radius, start);
    const [x2, y2] = polarPoint(radius, end);
    const largeArc = end - start > Math.PI ? 1 : 0;
    return `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2}`;
};

export const PlaybookGraph = () => {
    const graph = useGraph((state) => state.graph);
    const loading = useGraph((state) => state.loading);
    const error = useGraph((state) => state.error);
    const selectedRef = useGraph((state) => state.selectedRef);
    const hoveredNode = useGraph((state) => state.hoveredNode);
    const visibleDomains = useGraph((state) => state.visibleDomains);
    const showSkills = useGraph((state) => state.showSkills);
    const showAgents = useGraph((state) => state.showAgents);
    const showDoors = useGraph((state) => state.showDoors);
    const galaxy = useGraph((state) => state.galaxy);
    const load = useGraph((state) => state.load);
    const select = useGraph((state) => state.select);
    const hover = useGraph((state) => state.hover);
    const setView = useNav((state) => state.setView);
    const selectSkill = useSkillDetail((state) => state.select);
    const selectAgent = useAgentDetail((state) => state.select);
    const selectDoor = useDoorDetail((state) => state.select);
    const selectGalaxy = useGalaxyDetail((state) => state.select);

    const [settling, setSettling] = useState(false);
    const filterKey = `${visibleDomains?.join(',') ?? '*'}|${showSkills}|${showAgents}|${showDoors}|${galaxy ?? '*'}`;

    useEffect(() => {
        void load();
    }, [load]);

    useEffect(() => {
        setSettling(true);
        const timer = setTimeout(() => setSettling(false), SETTLE_MS);
        return () => clearTimeout(timer);
    }, [filterKey]);

    const domainVisible = (domain: string | null | undefined): boolean =>
        visibleDomains === null || visibleDomains.includes(domain ?? '');

    const base = useMemo<GraphResponse | null>(
        () => (graph ? (galaxy ? scopeToGalaxy(graph, galaxy) : graph) : null),
        [graph, galaxy],
    );

    const visibleGraph = useMemo<GraphResponse | null>(() => {
        if (!base) {
            return null;
        }
        const byId = new Map(base.nodes.map((n) => [n.id, n]));
        const nodeVisible = (id: string): boolean => {
            const node = byId.get(id);
            if (!node) {
                return false;
            }
            if (node.kind === 'playbook') {
                return true;
            }
            if (node.kind === 'ref') {
                return domainVisible(node.domain);
            }
            const isDoor = DOOR_KINDS.has(node.kind);
            const isAgent = node.kind === 'agent';
            if (isDoor ? !showDoors : isAgent ? !showAgents : !showSkills) {
                return false;
            }
            const edgeKind = isDoor ? 'door-to-ref' : isAgent ? 'agent-to-ref' : 'skill-to-ref';
            const targets = base.edges
                .filter((e) => e.kind === edgeKind && e.source === id)
                .map((e) => byId.get(e.target));
            return targets.length === 0 || targets.some((t) => t && domainVisible(t.domain));
        };
        return {
            nodes: base.nodes.filter((n) => nodeVisible(n.id)),
            edges: base.edges.filter((e) => nodeVisible(e.source) && nodeVisible(e.target)),
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [base, filterKey]);

    const fullLayout = useMemo(() => (base ? computeLayout(base) : []), [base]);
    const layout = useMemo(() => (visibleGraph ? computeLayout(visibleGraph) : []), [visibleGraph]);
    const arcs = useMemo(
        () => (visibleGraph ? computeDomainArcs(visibleGraph) : []),
        [visibleGraph],
    );
    const positions = useMemo(() => new Map(layout.map((l) => [l.node.id, l])), [layout]);

    if (loading && !graph) {
        return <Spinner />;
    }
    if (error) {
        return <p className="text-sm text-destructive">{error}</p>;
    }
    if (!graph || !visibleGraph) {
        return null;
    }

    const active = hoveredNode ?? selectedRef;
    const activeEdges = visibleGraph.edges.filter(
        (e) => e.source === active || e.target === active,
    );
    const neighbourIds = new Set(activeEdges.flatMap((e) => [e.source, e.target]));

    const edgePath = (x1: number, y1: number, x2: number, y2: number): string => {
        // Chords curve gently toward the hub; spokes from the hub stay straight.
        if ((x1 === 0 && y1 === 0) || (x2 === 0 && y2 === 0)) {
            return `M ${x1} ${y1} L ${x2} ${y2}`;
        }
        const cx = ((x1 + x2) / 2) * 0.45;
        const cy = ((y1 + y2) / 2) * 0.45;
        return `M ${x1} ${y1} Q ${cx} ${cy} ${x2} ${y2}`;
    };

    const fadeStyle = {
        opacity: settling ? 0 : 1,
        transition: 'opacity 200ms ease',
    } as const;

    return (
        <svg
            viewBox="-535 -535 1070 1070"
            className="h-full w-full"
            role="img"
            aria-label="Playbook reference graph"
            onClick={() => select(null)}
        >
            <g style={fadeStyle}>
                {arcs.map((arc) => (
                    <path
                        key={arc.domain}
                        d={arcPath(REF_RADIUS - 24, arc.startAngle, arc.endAngle)}
                        fill="none"
                        stroke={arc.color}
                        strokeWidth={2.5}
                        strokeOpacity={0.55}
                        strokeLinecap="round"
                    />
                ))}

                {visibleGraph.edges.map((edge) => {
                    const from = positions.get(edge.source);
                    const to = positions.get(edge.target);
                    if (!from || !to) {
                        return null;
                    }
                    const isActive =
                        active !== null && (edge.source === active || edge.target === active);
                    return (
                        <path
                            key={`${edge.source}->${edge.target}`}
                            d={edgePath(from.x, from.y, to.x, to.y)}
                            fill="none"
                            stroke={EDGE_COLORS[edge.kind] ?? 'var(--graph-edge)'}
                            strokeWidth={isActive ? 1.8 : 0.7}
                            strokeOpacity={active === null ? 0.16 : isActive ? 0.95 : 0.04}
                        />
                    );
                })}
            </g>

            {fullLayout.map((home) => {
                const node = home.node;
                const placed = positions.get(node.id) ?? home;
                const hidden = !positions.has(node.id);
                const isRef = node.kind === 'ref';
                const isPlaybook = node.kind === 'playbook';
                const isDoor = DOOR_KINDS.has(node.kind);
                const isAgent = node.kind === 'agent';
                const isFocused = node.id === active || node.id === selectedRef;
                const radius = isPlaybook ? 26 : isRef ? (isFocused ? 11 : 9) : isFocused ? 6 : 4.5;
                const dimmed = active !== null && node.id !== active && !neighbourIds.has(node.id);

                const dist = Math.hypot(placed.x, placed.y);
                const labelDist = dist + radius + 8;
                const [ax, ay] = polarPoint(labelDist, placed.angle);
                const lx = ax - placed.x;
                const ly = ay - placed.y;
                const deg = (placed.angle * 180) / Math.PI;
                const flip = Math.cos(placed.angle) < 0;

                return (
                    <g
                        key={node.id}
                        style={{
                            transform: `translate(${placed.x}px, ${placed.y}px)`,
                            transition: `transform ${GLIDE_MS}ms cubic-bezier(0.4, 0, 0.2, 1), opacity 300ms ease`,
                            opacity: hidden ? 0 : dimmed ? 0.22 : 1,
                            pointerEvents: hidden ? 'none' : undefined,
                        }}
                        className="cursor-pointer"
                        onClick={(event) => {
                            event.stopPropagation();
                            if (isRef) {
                                select(node.id);
                                setView('ref');
                            } else if (node.kind === 'skill') {
                                selectSkill(node.id);
                                setView('skill');
                            } else if (isAgent) {
                                selectAgent(node.id);
                                setView('agent');
                            } else if (isDoor) {
                                selectDoor(node.id);
                                setView('door');
                            } else if (isPlaybook && node.galaxy) {
                                // The galaxy core: open its GALAXY.md.
                                selectGalaxy(node.galaxy);
                                setView('galaxy');
                            } else if (isPlaybook) {
                                setView('playbook');
                            }
                        }}
                        onMouseEnter={() => hover(node.id)}
                        onMouseLeave={() => hover(null)}
                    >
                        {isPlaybook && (
                            <circle r={44} fill="hsl(var(--brand))" fillOpacity={0.12} />
                        )}
                        {isDoor ? (
                            <rect
                                x={-radius}
                                y={-radius}
                                width={radius * 2}
                                height={radius * 2}
                                rx={1.5}
                                fill={placed.color}
                                stroke={NODE_STROKE}
                                strokeWidth={1.5}
                            />
                        ) : isAgent ? (
                            <rect
                                x={-radius}
                                y={-radius}
                                width={radius * 2}
                                height={radius * 2}
                                rx={1.5}
                                fill={placed.color}
                                stroke={NODE_STROKE}
                                strokeWidth={1.5}
                                transform="rotate(45)"
                            />
                        ) : (
                            <circle
                                r={radius}
                                fill={isPlaybook ? 'hsl(var(--brand))' : placed.color}
                                stroke={
                                    node.id === selectedRef ? 'hsl(var(--foreground))' : NODE_STROKE
                                }
                                strokeWidth={node.id === selectedRef ? 2.5 : 1.5}
                            />
                        )}
                        {isPlaybook ? (
                            <text
                                x={0}
                                y={3.5}
                                textAnchor="middle"
                                fill="hsl(var(--foreground))"
                                fontSize={10}
                                fontWeight={700}
                                letterSpacing="0.08em"
                            >
                                {(node.galaxy ? node.label : 'PLAYBOOK').toUpperCase()}
                            </text>
                        ) : (
                            <g style={fadeStyle}>
                                <text
                                    x={lx}
                                    y={ly}
                                    dy="0.32em"
                                    transform={`rotate(${flip ? deg + 180 : deg} ${lx} ${ly})`}
                                    textAnchor={flip ? 'end' : 'start'}
                                    fill={isRef ? REF_LABEL : SKILL_LABEL}
                                    fontSize={isRef ? 12.5 : 10}
                                    fontWeight={isFocused ? 700 : isRef ? 500 : 400}
                                >
                                    <title>{node.id}</title>
                                    {truncated(shortLabel(node.id))}
                                </text>
                            </g>
                        )}
                    </g>
                );
            })}
        </svg>
    );
};
