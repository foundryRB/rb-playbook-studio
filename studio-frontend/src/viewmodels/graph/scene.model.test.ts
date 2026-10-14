import { describe, expect } from 'vitest';
import { intent } from '@psa-department-of-engineering/vitest-intent';

import type { GraphResponse, NebulaSummaryResponse } from '@/models';

import { buildUniverseModel, createPositionResolver } from './scene.model';

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
            id: 'REF-Meta',
            kind: 'ref',
            label: 'Meta',
            domain: 'meta',
            summary: 'Meta.',
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
            moons: ['bootstrap.py', 'templates/base.md'],
        },
        {
            id: 'alpha-door',
            kind: 'mcp',
            label: 'alpha-door',
            domain: null,
            summary: 'Knock.',
            galaxy: 'craft',
            moons: [],
        },
        {
            id: 'do-beta',
            kind: 'skill',
            label: 'do-beta',
            domain: null,
            summary: 'Does beta.',
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
            fresh_eyes: false,
        },
        {
            id: 'beta-agent',
            kind: 'agent',
            label: 'beta-agent',
            domain: null,
            summary: 'Runs alpha and beta.',
            galaxy: 'craft',
            moons: [],
            fresh_eyes: true,
        },
    ],
    edges: [
        { source: 'do-alpha', target: 'REF-Alpha', kind: 'skill-to-ref' },
        { source: 'do-beta', target: 'REF-Meta', kind: 'skill-to-ref' },
        { source: 'alpha-door', target: 'REF-Alpha', kind: 'door-to-ref' },
        { source: 'alpha-agent', target: 'REF-Alpha', kind: 'agent-to-ref' },
        { source: 'alpha-agent', target: 'do-alpha', kind: 'agent-to-skill' },
        { source: 'beta-agent', target: 'REF-Alpha', kind: 'agent-to-ref' },
        { source: 'beta-agent', target: 'do-alpha', kind: 'agent-to-skill' },
        { source: 'beta-agent', target: 'do-beta', kind: 'agent-to-skill' },
    ],
};

const dist = (a: readonly number[], b: readonly number[]): number =>
    Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

describe('buildUniverseModel', () => {
    intent(
        'INT-UNIVERSE-003',
        'places every graph node exactly once, plus a moon per loose file and a ring per folder',
        () => {
            const model = buildUniverseModel(graph);
            const ids = model.bodies.map((b) => b.id).sort();
            expect(ids).toEqual([
                'AI-PLAYBOOK',
                'REF-Alpha',
                'REF-Meta',
                'alpha-agent',
                'alpha-door',
                'beta-agent',
                'do-alpha',
                'do-beta',
                'moon:do-alpha/bootstrap.py',
                'ring:do-alpha/templates/',
            ]);
            const moon = model.bodies.find((b) => b.id === 'moon:do-alpha/bootstrap.py');
            expect(moon).toMatchObject({ kind: 'moon', moonOf: 'do-alpha', file: 'bootstrap.py' });
            const ring = model.bodies.find((b) => b.id === 'ring:do-alpha/templates/');
            expect(ring).toMatchObject({
                kind: 'ring',
                moonOf: 'do-alpha',
                files: ['templates/base.md'],
                label: 'templates/ · 1',
            });
        },
    );

    intent('INT-UNIVERSE-003', 'a ring sits on its planet and the moons orbit outside it', () => {
        const model = buildUniverseModel(graph);
        const resolve = createPositionResolver(model);
        const ring = model.bodies.find((b) => b.id === 'ring:do-alpha/templates/')!;
        const moon = model.bodies.find((b) => b.id === 'moon:do-alpha/bootstrap.py')!;
        for (const t of [0, 3.7, 12.4]) {
            expect(resolve(ring.id, t)).toEqual(resolve('do-alpha', t));
            expect(dist(resolve(moon.id, t), resolve('do-alpha', t))).toBeGreaterThan(ring.size);
        }
    });

    intent('INT-UNIVERSE-003', 'a ship with one licensed planet holds station at it', () => {
        const model = buildUniverseModel(graph);
        const agent = model.bodies.find((b) => b.id === 'alpha-agent');
        expect(agent).toMatchObject({ kind: 'agent', galaxy: 'craft' });
        expect(agent?.orbit?.anchorId).toBe('do-alpha');
        expect(agent?.route).toBeUndefined();
        const resolve = createPositionResolver(model);
        for (const t of [0, 3.7, 12.4]) {
            const sun = resolve('REF-Alpha', t);
            const body = resolve('alpha-agent', t);
            const planet = resolve('do-alpha', t);
            expect(dist(body, planet)).toBeLessThan(dist(body, sun));
            for (const galaxy of model.galaxies) {
                expect(dist(body, sun)).toBeLessThan(dist(body, galaxy.center));
            }
        }
    });

    intent('INT-UNIVERSE-003', 'a ship flies the loop of the planets its licence names', () => {
        const model = buildUniverseModel(graph);
        const ship = model.bodies.find((b) => b.id === 'beta-agent')!;
        expect(ship.route?.stops).toEqual(['do-alpha', 'do-beta']);
        const resolve = createPositionResolver(model);
        const legSeconds = ship.route!.legSeconds;
        for (const t of [0, legSeconds * 0.37, legSeconds * 1.2, legSeconds * 5.5]) {
            const at = resolve(ship.id, t);
            const a = resolve('do-alpha', t);
            const b = resolve('do-beta', t);
            const leg = dist(a, b);
            // Always between its two stops (plus the arc it flies above the plane).
            expect(dist(at, a) + dist(at, b)).toBeLessThan(leg * 1.25 + 0.2);
        }
        // Dock to dock: at a whole leg count it sits on a stop.
        const phase = ship.route!.phase;
        const docked = resolve(ship.id, (Math.ceil(phase) - phase) * legSeconds);
        const stopIndex = Math.ceil(phase) % 2;
        const stop = resolve(ship.route!.stops[stopIndex], (Math.ceil(phase) - phase) * legSeconds);
        expect(dist(docked, stop)).toBeLessThan(1e-6);
    });

    intent('INT-UNIVERSE-003', 'clusters suns around their own galaxy center', () => {
        const model = buildUniverseModel(graph);
        const resolve = createPositionResolver(model);
        const craft = model.galaxies.find((g) => g.name === 'craft');
        const maker = model.galaxies.find((g) => g.name === 'maker');
        const alpha = resolve('REF-Alpha', 0);
        expect(dist(alpha, craft!.center)).toBeLessThanOrEqual(craft!.radius + 0.3);
        expect(dist(alpha, craft!.center)).toBeLessThan(dist(alpha, maker!.center));
    });

    intent('INT-UNIVERSE-003', 'keeps planets orbiting their sun and moons their planet', () => {
        const model = buildUniverseModel(graph);
        const resolve = createPositionResolver(model);
        for (const t of [0, 3.7, 12.4]) {
            const sun = resolve('REF-Alpha', t);
            const planet = resolve('do-alpha', t);
            const moon = resolve('moon:do-alpha/bootstrap.py', t);
            for (const galaxy of model.galaxies) {
                expect(dist(planet, sun)).toBeLessThan(dist(planet, galaxy.center));
            }
            expect(dist(moon, planet)).toBeLessThan(dist(moon, sun));
            expect(dist(planet, sun)).toBeGreaterThan(0.05);
        }
    });

    intent('INT-UNIVERSE-003', 'is deterministic: the same graph builds the same universe', () => {
        const first = buildUniverseModel(graph);
        const second = buildUniverseModel(graph);
        expect(second).toEqual(first);
        const resolveFirst = createPositionResolver(first);
        const resolveSecond = createPositionResolver(second);
        expect(resolveSecond('moon:do-alpha/bootstrap.py', 5)).toEqual(
            resolveFirst('moon:do-alpha/bootstrap.py', 5),
        );
    });
});

const nebulaRoster: NebulaSummaryResponse[] = [
    {
        territory: 'padel-club-management',
        subject: 'padel club software',
        note_count: 10,
        unsmelted: 10,
        taken: 0,
        burned: 0,
    },
    {
        territory: 'deep-sea-mining',
        subject: 'mining operations software',
        note_count: 3,
        unsmelted: 2,
        taken: 1,
        burned: 0,
    },
];

describe('buildUniverseModel nebulae', () => {
    intent('INT-UNIVERSE-004', 'derives every nebula from the fetched roster alone', () => {
        const model = buildUniverseModel(graph, nebulaRoster);
        expect(model.nebulae.map((n) => n.name).sort()).toEqual([
            'deep-sea-mining',
            'padel-club-management',
        ]);
        const padel = model.nebulae.find((n) => n.name === 'padel-club-management');
        expect(padel?.noteCount).toBe(10);
        expect(buildUniverseModel(graph).nebulae).toEqual([]);
        const resolve = createPositionResolver(model);
        expect(resolve('nebula:padel-club-management', 7)).toEqual(padel!.center);
    });

    intent('INT-UNIVERSE-004', 'places every nebula outside the whole galaxy scatter', () => {
        const model = buildUniverseModel(graph, nebulaRoster);
        const scatterEdge = model.galaxies.reduce(
            (edge, g) => Math.max(edge, Math.hypot(g.center[0], g.center[2]) + g.radius),
            0,
        );
        for (const nebula of model.nebulae) {
            expect(Math.hypot(nebula.center[0], nebula.center[2])).toBeGreaterThan(scatterEdge);
        }
        const [a, b] = model.nebulae;
        expect(dist(a.center, b.center)).toBeGreaterThanOrEqual(a.radius + b.radius);
    });

    intent('INT-UNIVERSE-004', 'keeps nebulae out of the earned bodies list', () => {
        const bare = buildUniverseModel(graph);
        const model = buildUniverseModel(graph, nebulaRoster);
        expect(model.bodies).toEqual(bare.bodies);
        expect(model.galaxies).toEqual(bare.galaxies);
        const bodyIds = new Set(model.bodies.map((body) => body.id));
        for (const nebula of model.nebulae) {
            expect(bodyIds.has(nebula.name)).toBe(false);
            expect(bodyIds.has(`nebula:${nebula.name}`)).toBe(false);
        }
    });

    intent('INT-UNIVERSE-004', 'is deterministic: the same roster lands the same clouds', () => {
        expect(buildUniverseModel(graph, nebulaRoster)).toEqual(
            buildUniverseModel(graph, nebulaRoster),
        );
    });
});
