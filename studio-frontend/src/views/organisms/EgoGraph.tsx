import { useMemo } from 'react';

import { AGENT_COLOR, DOMAIN_COLORS, SKILL_COLOR, useGraph } from '@/viewmodels/graph';
import { useAgentDetail } from '@/viewmodels/agentdetail';
import { useDoorDetail } from '@/viewmodels/doordetail';
import { useNav } from '@/viewmodels/nav';
import { useSkillDetail } from '@/viewmodels/skilldetail';

export interface EgoGraphProps {
    refName: string;
    /** Override the default open-the-reader navigation (the 3D panel travels
     *  to the body instead). */
    onPick?: (id: string) => void;
}

const shortLabel = (id: string): string => id.replace(/^REF-/, '');

interface Neighbour {
    id: string;
    kind: 'ref' | 'skill' | 'agent' | 'door';
    inbound: boolean;
}

/** The selected REF and its direct connections, at a glance and clickable. */
export const EgoGraph = ({ refName, onPick }: EgoGraphProps) => {
    const graph = useGraph((state) => state.graph);
    const select = useGraph((state) => state.select);
    const setView = useNav((state) => state.setView);
    const selectSkill = useSkillDetail((state) => state.select);
    const selectAgent = useAgentDetail((state) => state.select);
    const selectDoor = useDoorDetail((state) => state.select);

    const neighbours = useMemo<Neighbour[]>(() => {
        if (!graph) {
            return [];
        }
        const out: Neighbour[] = [];
        const seen = new Set<string>();
        for (const e of graph.edges) {
            let other: Neighbour | null = null;
            if (e.source === refName && e.kind === 'ref-to-ref') {
                other = { id: e.target, kind: 'ref', inbound: false };
            } else if (e.target === refName && e.kind === 'ref-to-ref') {
                other = { id: e.source, kind: 'ref', inbound: true };
            } else if (e.target === refName && e.kind === 'skill-to-ref') {
                other = { id: e.source, kind: 'skill', inbound: true };
            } else if (e.target === refName && e.kind === 'door-to-ref') {
                other = { id: e.source, kind: 'door', inbound: true };
            } else if (e.source === refName && e.kind === 'skill-to-ref') {
                // The ego is a skill: its doctrine suns.
                other = { id: e.target, kind: 'ref', inbound: false };
            } else if (e.source === refName && e.kind === 'door-to-ref') {
                // The ego is a door: its doctrine suns.
                other = { id: e.target, kind: 'ref', inbound: false };
            } else if (e.target === refName && e.kind === 'agent-to-ref') {
                other = { id: e.source, kind: 'agent', inbound: true };
            } else if (e.source === refName && e.kind === 'agent-to-ref') {
                // The ego is an agent: its doctrine suns.
                other = { id: e.target, kind: 'ref', inbound: false };
            } else if (e.source === refName && e.kind === 'agent-to-skill') {
                // The ego is an agent: the skills it is licensed to run.
                other = { id: e.target, kind: 'skill', inbound: false };
            } else if (e.target === refName && e.kind === 'agent-to-skill') {
                // The ego is a skill: the agents licensed to run it.
                other = { id: e.source, kind: 'agent', inbound: true };
            } else if (e.source === refName && e.kind === 'agent-to-door') {
                // The ego is an agent: the doors it needs bound.
                other = { id: e.target, kind: 'door', inbound: false };
            } else if (e.target === refName && e.kind === 'agent-to-door') {
                // The ego is a door: the agents that need it.
                other = { id: e.source, kind: 'agent', inbound: true };
            }
            if (other && !seen.has(other.id)) {
                seen.add(other.id);
                out.push(other);
            }
        }
        return out;
    }, [graph, refName]);

    const domainOf = (id: string): string | null =>
        graph?.nodes.find((n) => n.id === id)?.domain ?? null;

    if (!graph || neighbours.length === 0) {
        return null;
    }

    const R = 84;
    const size = 360;
    const center = size / 2;
    const selfColor = DOMAIN_COLORS[domainOf(refName) ?? ''] ?? SKILL_COLOR;

    return (
        <svg
            viewBox={`0 0 ${size} ${size}`}
            className="mx-auto w-full max-w-[340px] overflow-visible"
            role="img"
            aria-label="Connections"
        >
            {neighbours.map((n, i) => {
                const angle = (2 * Math.PI * i) / neighbours.length - Math.PI / 2;
                const x = center + R * Math.cos(angle);
                const y = center + R * Math.sin(angle);
                const color =
                    n.kind === 'ref'
                        ? (DOMAIN_COLORS[domainOf(n.id) ?? ''] ?? SKILL_COLOR)
                        : n.kind === 'door'
                          ? '#d97706'
                          : n.kind === 'agent'
                            ? AGENT_COLOR
                            : SKILL_COLOR;
                const label = shortLabel(n.id);
                const flip = Math.cos(angle) < 0;
                const deg = (angle * 180) / Math.PI;
                const lx = center + (R + 10) * Math.cos(angle);
                const ly = center + (R + 10) * Math.sin(angle);
                return (
                    <g
                        key={n.id}
                        className="cursor-pointer"
                        onClick={() => {
                            if (onPick) {
                                onPick(n.id);
                            } else if (n.kind === 'ref') {
                                select(n.id);
                                setView('ref');
                            } else if (n.kind === 'door') {
                                selectDoor(n.id);
                                setView('door');
                            } else if (n.kind === 'agent') {
                                selectAgent(n.id);
                                setView('agent');
                            } else {
                                selectSkill(n.id);
                                setView('skill');
                            }
                        }}
                    >
                        <line
                            x1={center}
                            y1={center}
                            x2={x}
                            y2={y}
                            stroke={n.inbound ? 'var(--graph-edge-skill)' : 'var(--graph-edge)'}
                            strokeWidth={1}
                            strokeOpacity={0.55}
                            strokeDasharray={n.kind === 'skill' ? '2 3' : undefined}
                        />
                        {n.kind === 'door' ? (
                            <rect
                                x={x - 3.5}
                                y={y - 3.5}
                                width={7}
                                height={7}
                                rx={1}
                                fill={color}
                            />
                        ) : n.kind === 'agent' ? (
                            <rect
                                x={x - 3.5}
                                y={y - 3.5}
                                width={7}
                                height={7}
                                rx={1}
                                fill={color}
                                transform={`rotate(45 ${x} ${y})`}
                            />
                        ) : (
                            <circle cx={x} cy={y} r={n.kind === 'ref' ? 5 : 3.5} fill={color} />
                        )}
                        <text
                            x={lx}
                            y={ly}
                            dy="0.32em"
                            transform={`rotate(${flip ? deg + 180 : deg} ${lx} ${ly})`}
                            textAnchor={flip ? 'end' : 'start'}
                            fill={
                                n.kind === 'ref' ? 'var(--graph-label)' : 'var(--graph-label-muted)'
                            }
                            fontSize={8.5}
                        >
                            {label.length > 20 ? `${label.slice(0, 19)}…` : label}
                        </text>
                    </g>
                );
            })}
            <circle
                cx={center}
                cy={center}
                r={9}
                fill={selfColor}
                stroke="var(--graph-node-stroke)"
                strokeWidth={1.5}
            />
        </svg>
    );
};
