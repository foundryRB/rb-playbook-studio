import { describe, expect } from 'vitest';
import { intent } from '@psa-department-of-engineering/vitest-intent';

import type { GraphResponse } from '@/models';

import {
    AGENT_COLOR,
    computeLayout,
    computeUniverse,
    GALAXY_CORE_PREFIX,
    MCP_COLOR,
    scopeToGalaxy,
    SKILL_COLOR,
} from './graph.model';

const graph: GraphResponse = {
    nodes: [
        {
            id: 'AI-PLAYBOOK',
            kind: 'playbook',
            label: 'AI Playbook',
            domain: null,
            summary: '',
            galaxy: null,
            moons: [],
        },
        {
            id: 'REF-Alpha',
            kind: 'ref',
            label: 'Alpha',
            domain: 'language',
            summary: 'Alpha.',
            galaxy: 'craft',
            moons: [],
        },
        {
            id: 'REF-Beta',
            kind: 'ref',
            label: 'Beta',
            domain: 'meta',
            summary: 'Beta.',
            galaxy: 'maker',
            moons: [],
        },
        {
            id: 'do-alpha',
            kind: 'skill',
            label: 'do-alpha',
            domain: null,
            summary: 'Does alpha.',
            galaxy: 'craft',
            moons: [],
        },
        {
            id: 'alpha-door',
            kind: 'mcp',
            label: 'alpha-door',
            domain: null,
            summary: 'Knock for alpha.',
            galaxy: 'craft',
            moons: [],
        },
        {
            id: 'alpha-agent',
            kind: 'agent',
            label: 'alpha-agent',
            domain: null,
            summary: 'Runs alpha end to end.',
            galaxy: 'craft',
            moons: [],
        },
    ],
    edges: [
        { source: 'do-alpha', target: 'REF-Alpha', kind: 'skill-to-ref' },
        { source: 'alpha-door', target: 'REF-Alpha', kind: 'door-to-ref' },
        { source: 'alpha-agent', target: 'REF-Alpha', kind: 'agent-to-ref' },
        { source: 'alpha-agent', target: 'do-alpha', kind: 'agent-to-skill' },
        { source: 'alpha-agent', target: 'alpha-door', kind: 'agent-to-door' },
        { source: 'AI-PLAYBOOK', target: 'REF-Alpha', kind: 'playbook-to-ref' },
        { source: 'AI-PLAYBOOK', target: 'REF-Beta', kind: 'playbook-to-ref' },
        { source: 'REF-Beta', target: 'REF-Alpha', kind: 'ref-to-ref' },
    ],
};

describe('computeLayout', () => {
    intent('INT-LAYOUT-001', 'puts the playbook at the origin', () => {
        const playbook = computeLayout(graph).find((l) => l.node.id === 'AI-PLAYBOOK');
        expect(playbook).toMatchObject({ x: 0, y: 0 });
    });

    intent('INT-LAYOUT-001', 'places every node exactly once', () => {
        const ids = computeLayout(graph).map((l) => l.node.id);
        expect(ids.sort()).toEqual([
            'AI-PLAYBOOK',
            'REF-Alpha',
            'REF-Beta',
            'alpha-agent',
            'alpha-door',
            'do-alpha',
        ]);
    });

    intent('INT-LAYOUT-001', 'puts skills on a wider ring than refs', () => {
        const layout = computeLayout(graph);
        const radius = (id: string) => {
            const l = layout.find((n) => n.node.id === id);
            return l ? Math.hypot(l.x, l.y) : 0;
        };
        expect(radius('do-alpha')).toBeGreaterThan(radius('REF-Alpha'));
    });

    intent('INT-LAYOUT-001', 'colors refs by their domain', () => {
        const layout = computeLayout(graph);
        const alpha = layout.find((l) => l.node.id === 'REF-Alpha');
        const beta = layout.find((l) => l.node.id === 'REF-Beta');
        expect(alpha?.color).not.toEqual(beta?.color);
    });

    intent('INT-LAYOUT-002', 'places doors on the outer ring, colored by kind', () => {
        const layout = computeLayout(graph);
        const door = layout.find((l) => l.node.id === 'alpha-door');
        const ref = layout.find((l) => l.node.id === 'REF-Alpha');
        expect(Math.hypot(door?.x ?? 0, door?.y ?? 0)).toBeGreaterThan(
            Math.hypot(ref?.x ?? 0, ref?.y ?? 0),
        );
        expect(door?.color).toEqual(MCP_COLOR);
        expect(door?.color).not.toEqual(SKILL_COLOR);
    });

    intent('INT-LAYOUT-003', 'places agents on the outer ring as their own kind', () => {
        const layout = computeLayout(graph);
        const agent = layout.find((l) => l.node.id === 'alpha-agent');
        const ref = layout.find((l) => l.node.id === 'REF-Alpha');
        expect(Math.hypot(agent?.x ?? 0, agent?.y ?? 0)).toBeGreaterThan(
            Math.hypot(ref?.x ?? 0, ref?.y ?? 0),
        );
        expect(agent?.color).toEqual(AGENT_COLOR);
        expect(agent?.color).not.toEqual(SKILL_COLOR);
        expect(agent?.color).not.toEqual(MCP_COLOR);
    });
});

describe('scopeToGalaxy', () => {
    intent('INT-UNIVERSE-001', 'keeps only the galaxy plus a synthesized core', () => {
        const scoped = scopeToGalaxy(graph, 'craft');
        const ids = scoped.nodes.map((n) => n.id).sort();
        expect(ids).toEqual([
            'REF-Alpha',
            'alpha-agent',
            'alpha-door',
            'do-alpha',
            `${GALAXY_CORE_PREFIX}craft`,
        ]);
        const core = scoped.nodes.find((n) => n.id === `${GALAXY_CORE_PREFIX}craft`);
        expect(core).toMatchObject({ kind: 'playbook', label: 'craft', galaxy: 'craft' });
    });

    intent(
        'INT-UNIVERSE-001',
        'rewires hub edges onto the core and drops boundary crossers',
        () => {
            const scoped = scopeToGalaxy(graph, 'craft');
            const kinds = scoped.edges.map((e) => `${e.kind}:${e.source}->${e.target}`).sort();
            expect(kinds).toEqual([
                `agent-to-door:alpha-agent->alpha-door`,
                `agent-to-ref:alpha-agent->REF-Alpha`,
                `agent-to-skill:alpha-agent->do-alpha`,
                `door-to-ref:alpha-door->REF-Alpha`,
                `playbook-to-ref:${GALAXY_CORE_PREFIX}craft->REF-Alpha`,
                `skill-to-ref:do-alpha->REF-Alpha`,
            ]);
        },
    );
});

describe('computeUniverse', () => {
    intent('INT-UNIVERSE-002', 'counts suns, carried planets, and doors per galaxy', () => {
        expect(computeUniverse(graph)).toEqual([
            { name: 'craft', refs: 1, skills: 1, agents: 1, doors: 1 },
            { name: 'maker', refs: 1, skills: 0, agents: 0, doors: 0 },
        ]);
    });
});
