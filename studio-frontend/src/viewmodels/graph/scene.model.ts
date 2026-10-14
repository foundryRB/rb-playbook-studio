import type { GraphNodeResponse, GraphResponse, NebulaSummaryResponse } from '@/models';

import {
    AGENT_COLOR,
    DOMAIN_COLORS,
    DOOR_KINDS,
    HOME_EDGE_KINDS,
    isPlanetKind,
    MCP_COLOR,
    NEBULA_COLOR,
    RAG_COLOR,
    SKILL_COLOR,
} from './graph.model';

/** The 3D universe, in meters around a standing viewer, as a deterministic
 *  orbital model: static suns, orbiting planets and doors, moons (a skill's
 *  top-level files, REF-Universe par. 3) around their planet, and rings (a
 *  skill's folders: the material a planet holds, one ring per folder). All
 *  variation is seeded from names, so the universe is organic yet identical
 *  on every load. */

export type Vec3 = [number, number, number];

export type BodyKind =
    'hub' | 'sun' | 'planet' | 'agent' | 'door' | 'moon' | 'ring' | 'galaxy' | 'nebula';

export interface OrbitSpec {
    anchorId: string;
    radius: number;
    /** Radians per second. */
    speed: number;
    phase: number;
    incline: number;
}

export interface SceneBody {
    id: string;
    kind: BodyKind;
    label: string;
    galaxy: string | null;
    color: string;
    size: number;
    seed: number;
    node: GraphNodeResponse | null;
    /** Stellar magnitude for suns: drives surface brightness and flare. */
    intensity?: number;
    moonOf?: string;
    file?: string;
    /** A ring's files: the folder's contents, relative to the skill. */
    files?: string[];
    position?: Vec3;
    orbit?: OrbitSpec;
    /** A ship's flight plan: the planets its licence names, flown as a loop. */
    route?: RouteSpec;
}

export interface RouteSpec {
    /** Body ids, in licence order; the loop closes from the last to the first. */
    stops: string[];
    /** Seconds one leg takes, dock to dock. */
    legSeconds: number;
    /** Where along the loop the ship starts, in legs. */
    phase: number;
}

export type GalaxyMorphology = 'spiral' | 'barred' | 'elliptical' | 'irregular';

export interface SceneGalaxy {
    name: string;
    center: Vec3;
    radius: number;
    color: string;
    seed: number;
    /** Disc inclination [aboutX, aboutZ]: real galaxies never share a plane. */
    tilt: [number, number];
    /** Real galaxies come in kinds; seeded, so each shelf keeps its shape. */
    morphology: GalaxyMorphology;
}

/** A nebula: unearned stardust rendered as a dim cloud OUTSIDE the galaxy
 *  scatter. Never a graph body; the quarantine keeps it off the earned maps'
 *  data spine, so it rides in its own list. */
export interface SceneNebula {
    name: string;
    center: Vec3;
    radius: number;
    color: string;
    seed: number;
    noteCount: number;
}

export interface UniverseModel {
    galaxies: SceneGalaxy[];
    bodies: SceneBody[];
    nebulae: SceneNebula[];
}

const EYE_HEIGHT = 1.5;
const GALAXY_RING_RADIUS = 4.0;
const GALAXY_DISC_RADIUS = 2.2;
/** The closest two suns of one galaxy ever sit. A star system is its sun
 *  plus its planets' orbits plus their moons' orbits, so the gap between
 *  suns has to hold two half-systems without their moons trading places. */
const SUN_MIN_SEPARATION = 0.68;
const GALAXY_PALETTE = ['#38bdf8', '#34d399', '#fbbf24', '#fb7185', '#2dd4bf', '#c084fc'];

/** FNV-1a over the name, so every body's look is stable across loads. */
export function hashSeed(text: string): number {
    let hash = 0x811c9dc5;
    for (let i = 0; i < text.length; i += 1) {
        hash ^= text.charCodeAt(i);
        hash = Math.imul(hash, 0x01000193);
    }
    return hash >>> 0;
}

/** Deterministic PRNG (mulberry32). */
export function seededRandom(seed: number): () => number {
    let state = seed || 1;
    return () => {
        state |= 0;
        state = (state + 0x6d2b79f5) | 0;
        let t = Math.imul(state ^ (state >>> 15), 1 | state);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

const nodeColor = (node: GraphNodeResponse): string => {
    if (node.kind === 'ref') {
        return DOMAIN_COLORS[node.domain ?? ''] ?? SKILL_COLOR;
    }
    if (node.kind === 'mcp') {
        return MCP_COLOR;
    }
    if (node.kind === 'rag') {
        return RAG_COLOR;
    }
    if (node.kind === 'agent') {
        return AGENT_COLOR;
    }
    return SKILL_COLOR;
};

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

/** A galaxy's disc grows with its suns: a two-sun shelf is a wisp, a
 *  forty-sun shelf a spiral. One formula, so the scene's filter re-flow
 *  shrinks a disc the same way the model grew it. */
export function galaxyDiscRadius(suns: number): number {
    return Math.min(Math.max(0.6 + 0.3 * Math.sqrt(suns), 0.6), GALAXY_DISC_RADIUS * 1.25);
}

/** Lerp two hex colors without dragging three.js into the model. */
function mixHex(a: string, b: string, t: number): string {
    const pa = parseInt(a.slice(1), 16);
    const pb = parseInt(b.slice(1), 16);
    const channel = (shift: number): number => {
        const ca = (pa >> shift) & 0xff;
        const cb = (pb >> shift) & 0xff;
        return Math.round(ca + (cb - ca) * t);
    };
    const value = (channel(16) << 16) | (channel(8) << 8) | channel(0);
    return `#${value.toString(16).padStart(6, '0')}`;
}

export function buildUniverseModel(
    graph: GraphResponse,
    nebulaSummaries: NebulaSummaryResponse[] = [],
): UniverseModel {
    const names = [
        ...new Set(graph.nodes.map((n) => n.galaxy).filter((g): g is string => !!g)),
    ].sort();

    // Scattered placement with rejection sampling: real galaxies never sit
    // on a neat ring. Seeded from the roster, deterministic per universe.
    const uniRand = seededRandom(hashSeed(`universe:${names.join(',')}`));
    const placedCenters: { center: Vec3; radius: number }[] = [];
    const galaxies: SceneGalaxy[] = names.map((name, i) => {
        const seed = hashSeed(`galaxy:${name}`);
        const rand = seededRandom(seed);
        const suns = graph.nodes.filter((n) => n.kind === 'ref' && n.galaxy === name).length;
        const radius = galaxyDiscRadius(suns);
        const fallbackAngle = (2 * Math.PI * i) / names.length - Math.PI / 2;
        let center: Vec3 = [
            GALAXY_RING_RADIUS * Math.cos(fallbackAngle),
            EYE_HEIGHT,
            GALAXY_RING_RADIUS * Math.sin(fallbackAngle),
        ];
        for (let attempt = 0; attempt < 48; attempt += 1) {
            const angle = uniRand() * Math.PI * 2;
            const distance = 3.3 + uniRand() * 3.2;
            const candidate: Vec3 = [
                distance * Math.cos(angle),
                EYE_HEIGHT + (uniRand() - 0.5) * 2.2,
                distance * Math.sin(angle),
            ];
            const clearOfHub = Math.hypot(candidate[0], candidate[2]) >= radius + 0.9;
            const clearOfOthers = placedCenters.every(
                (p) =>
                    Math.hypot(
                        candidate[0] - p.center[0],
                        candidate[1] - p.center[1],
                        candidate[2] - p.center[2],
                    ) >=
                    p.radius + radius + 0.7,
            );
            if (clearOfHub && clearOfOthers) {
                center = candidate;
                break;
            }
        }
        placedCenters.push({ center, radius });
        const morphRoll = rand();
        const morphology: GalaxyMorphology =
            morphRoll < 0.4
                ? 'spiral'
                : morphRoll < 0.65
                  ? 'barred'
                  : morphRoll < 0.85
                    ? 'elliptical'
                    : 'irregular';
        return {
            name,
            center,
            radius,
            color: name === 'maker' ? '#94a3b8' : GALAXY_PALETTE[i % GALAXY_PALETTE.length],
            seed,
            tilt: [(rand() - 0.5) * 1.4, (rand() - 0.5) * 0.9],
            morphology,
        };
    });

    // Rotate a galaxy-local offset by the disc inclination (Z first, then X;
    // the same order three.js applies to an 'XYZ' Euler with y = 0).
    const tiltLocal = (local: Vec3, tx: number, tz: number): Vec3 => {
        const [x0, y0, z0] = local;
        const x1 = x0 * Math.cos(tz) - y0 * Math.sin(tz);
        const y1 = x0 * Math.sin(tz) + y0 * Math.cos(tz);
        const y2 = y1 * Math.cos(tx) - z0 * Math.sin(tx);
        const z2 = y1 * Math.sin(tx) + z0 * Math.cos(tx);
        return [x1, y2, z2];
    };
    const bodies: SceneBody[] = [];

    const playbook = graph.nodes.find((n) => n.kind === 'playbook');
    if (playbook) {
        bodies.push({
            id: playbook.id,
            kind: 'hub',
            label: playbook.label,
            galaxy: null,
            // The universe's core shines indigo; PLAYBOOK_COLOR is the 2D ink.
            color: '#818cf8',
            size: 0.11,
            seed: hashSeed(playbook.id),
            node: playbook,
            position: [0, EYE_HEIGHT, 0],
        });
    }

    for (const galaxy of galaxies) {
        const suns = graph.nodes.filter((n) => n.kind === 'ref' && n.galaxy === galaxy.name);
        // Phyllotaxis seats with clustered jitter, then a relaxation pass:
        // real star fields clump and void, but neighbors never collide.
        const locals: Vec3[] = suns.map((sun, i) => {
            const rand = seededRandom(hashSeed(sun.id));
            const jitter = galaxy.morphology === 'irregular' ? 1.1 : 0.6;
            const thickness = galaxy.morphology === 'elliptical' ? galaxy.radius * 0.5 : 0.3;
            const r =
                galaxy.radius * 0.92 * Math.sqrt((i + 0.6) / suns.length) * (0.8 + rand() * 0.4);
            const theta = i * GOLDEN_ANGLE + (rand() - 0.5) * jitter;
            return [r * Math.cos(theta), (rand() - 0.5) * thickness, r * Math.sin(theta)];
        });
        const minSep = Math.min(
            SUN_MIN_SEPARATION,
            (galaxy.radius * 1.7) / Math.max(Math.sqrt(suns.length), 1),
        );
        for (let pass = 0; pass < 12; pass += 1) {
            for (let a = 0; a < locals.length; a += 1) {
                for (let b = a + 1; b < locals.length; b += 1) {
                    const dx = locals[b][0] - locals[a][0];
                    const dz = locals[b][2] - locals[a][2];
                    const d = Math.hypot(dx, dz);
                    if (d > 0.0001 && d < minSep) {
                        const push = (minSep - d) / 2 / d;
                        locals[a][0] -= dx * push;
                        locals[a][2] -= dz * push;
                        locals[b][0] += dx * push;
                        locals[b][2] += dz * push;
                    }
                }
            }
            for (const local of locals) {
                const rr = Math.hypot(local[0], local[2]);
                const cap = galaxy.radius * 0.98;
                if (rr > cap) {
                    local[0] *= cap / rr;
                    local[2] *= cap / rr;
                }
            }
        }
        suns.forEach((sun, i) => {
            const seed = hashSeed(sun.id);
            const rand = seededRandom(seed ^ 0x515);
            const local = tiltLocal(locals[i], galaxy.tilt[0], galaxy.tilt[1]);
            // Stellar hierarchy: dwarfs through giants, and a seeded
            // temperature so same-domain suns are siblings, never clones.
            const magnitude = rand();
            const temp = rand();
            const tint = temp < 0.5 ? '#fff3e0' : temp < 0.8 ? '#ffd2a0' : '#cfe4ff';
            bodies.push({
                id: sun.id,
                kind: 'sun',
                label: sun.id.replace(/^REF-/, ''),
                galaxy: galaxy.name,
                color: mixHex(nodeColor(sun), tint, 0.25 + rand() * 0.2),
                size: 0.032 + magnitude ** 1.6 * 0.06,
                seed,
                node: sun,
                intensity: 1.05 + magnitude * 0.55,
                position: [
                    galaxy.center[0] + local[0],
                    galaxy.center[1] + local[1],
                    galaxy.center[2] + local[2],
                ],
            });
        });
    }

    const planets = graph.nodes.filter((n) => isPlanetKind(n.kind));
    const siblings = new Map<string, number>();
    /** Each planet's outermost ring edge, for a ship holding station at it. */
    const systemEdge = new Map<string, number>();
    for (const planet of planets) {
        const seed = hashSeed(planet.id);
        const rand = seededRandom(seed);
        const isDoor = DOOR_KINDS.has(planet.kind);
        const isAgent = planet.kind === 'agent';
        const primary = graph.edges.find(
            (e) => HOME_EDGE_KINDS.has(e.kind) && e.source === planet.id,
        );
        const anchorId =
            primary && bodiesHas(bodies, primary.target)
                ? primary.target
                : `galaxy:${planet.galaxy ?? names[0]}`;
        const rank = siblings.get(anchorId) ?? 0;
        siblings.set(anchorId, rank + 1);
        const anchoredToGalaxy = anchorId.startsWith('galaxy:');
        const planetSize = (isDoor ? 0.02 : isAgent ? 0.014 : 0.016) + rand() * 0.008;
        bodies.push({
            id: planet.id,
            kind: isDoor ? 'door' : isAgent ? 'agent' : 'planet',
            label: planet.id,
            galaxy: planet.galaxy ?? null,
            color: nodeColor(planet),
            size: planetSize,
            seed,
            node: planet,
            orbit: {
                anchorId,
                radius: anchoredToGalaxy
                    ? galaxyOrbitRadius(rand)
                    : 0.11 + rank * 0.036 + rand() * 0.026,
                speed: (isDoor ? 0.05 : isAgent ? 0.11 : 0.08) + rand() * 0.1,
                phase: rand() * Math.PI * 2,
                incline: (rand() - 0.5) * 0.9,
            },
        });

        // A skill's folders are rings: the material a planet holds, drawn
        // around it rather than scattered as a swarm of moons. Its loose
        // top-level files are the moons, orbiting outside the ring system.
        const { folders, loose } = splitSkillFiles(planet.moons ?? []);
        let ringEdge = 0;
        [...folders.entries()]
            .sort(([a], [b]) => a.localeCompare(b))
            .forEach(([folder, files], r) => {
                const ringSeed = hashSeed(`${planet.id}/${folder}/`);
                const ringRand = seededRandom(ringSeed);
                const outer = ringOuterRadius(planetSize, r);
                ringEdge = Math.max(ringEdge, outer);
                bodies.push({
                    id: `ring:${planet.id}/${folder}/`,
                    kind: 'ring',
                    label: `${folder}/ · ${files.length}`,
                    galaxy: planet.galaxy ?? null,
                    color: '#d8cfbf',
                    size: outer,
                    seed: ringSeed,
                    node: null,
                    moonOf: planet.id,
                    files,
                    orbit: {
                        anchorId: planet.id,
                        radius: 0,
                        speed: 0,
                        phase: 0,
                        incline: (ringRand() - 0.5) * 1.2,
                    },
                });
            });

        systemEdge.set(planet.id, ringEdge);
        const moonBase = Math.max(0.035, ringEdge + 0.012);
        for (const [m, file] of loose.entries()) {
            const moonSeed = hashSeed(`${planet.id}/${file}`);
            const moonRand = seededRandom(moonSeed);
            bodies.push({
                id: `moon:${planet.id}/${file}`,
                kind: 'moon',
                label: file,
                galaxy: planet.galaxy ?? null,
                color: '#cbd5e1',
                size: 0.006 + moonRand() * 0.003,
                seed: moonSeed,
                node: null,
                moonOf: planet.id,
                file,
                orbit: {
                    anchorId: planet.id,
                    radius: moonBase + m * 0.014 + moonRand() * 0.008,
                    speed: 0.5 + moonRand() * 0.7,
                    phase: moonRand() * Math.PI * 2,
                    incline: (moonRand() - 0.5) * 1.4,
                },
            });
        }
    }

    // A ship flies the route of the planets its licence names (REF-Universe
    // par. 3): with two or more it loops dock to dock; with one it holds
    // station between that planet's rings and its moons; with none it keeps
    // to its home sun. The licence comes from the graph's agent-to-skill
    // edges, so the flight plan is the frontmatter, drawn.
    const licence = new Map<string, string[]>();
    for (const edge of graph.edges) {
        if (edge.kind === 'agent-to-skill') {
            licence.set(edge.source, [...(licence.get(edge.source) ?? []), edge.target]);
        }
    }
    for (const ship of bodies) {
        if (ship.kind !== 'agent') {
            continue;
        }
        const stops = (licence.get(ship.id) ?? []).filter(
            (id) => id !== ship.id && bodies.some((b) => b.id === id && b.kind === 'planet'),
        );
        const rand = seededRandom(ship.seed ^ 0x5a11);
        if (stops.length >= 2) {
            ship.route = {
                stops,
                legSeconds: 16 + rand() * 12,
                phase: rand() * stops.length,
            };
        } else if (stops.length === 1) {
            ship.orbit = {
                anchorId: stops[0],
                radius: Math.max(0.03, (systemEdge.get(stops[0]) ?? 0) + 0.008),
                speed: 0.35 + rand() * 0.2,
                phase: rand() * Math.PI * 2,
                incline: (rand() - 0.5) * 0.5,
            };
        }
    }

    // Nebulae drift beyond the whole earned scatter: strictly farther from
    // the hub than any galaxy's outer edge (REF-Universe: the unearned zone
    // renders visible, second-class, honest). Everything derives from the
    // fetched roster; no territory is ever hand-placed.
    const sorted = [...nebulaSummaries].sort((a, b) => a.territory.localeCompare(b.territory));
    const scatterEdge = galaxies.reduce(
        (edge, g) => Math.max(edge, Math.hypot(g.center[0], g.center[2]) + g.radius),
        GALAXY_RING_RADIUS,
    );
    const nebRand = seededRandom(hashSeed(`nebulae:${sorted.map((n) => n.territory).join(',')}`));
    const nebulae: SceneNebula[] = [];
    sorted.forEach((summary, i) => {
        const seed = hashSeed(`nebula:${summary.territory}`);
        const radius = Math.min(0.5 + 0.12 * Math.sqrt(summary.note_count), 1.1);
        const baseDistance = scatterEdge + 0.9 + radius;
        const fallbackAngle = (2 * Math.PI * i) / sorted.length + Math.PI / 5;
        let center: Vec3 = [
            baseDistance * Math.cos(fallbackAngle),
            EYE_HEIGHT,
            baseDistance * Math.sin(fallbackAngle),
        ];
        for (let attempt = 0; attempt < 48; attempt += 1) {
            const angle = nebRand() * Math.PI * 2;
            const distance = baseDistance + nebRand() * 1.6;
            const candidate: Vec3 = [
                distance * Math.cos(angle),
                EYE_HEIGHT + (nebRand() - 0.5) * 2.4,
                distance * Math.sin(angle),
            ];
            const clearOfOthers = nebulae.every(
                (p) =>
                    Math.hypot(
                        candidate[0] - p.center[0],
                        candidate[1] - p.center[1],
                        candidate[2] - p.center[2],
                    ) >=
                    p.radius + radius + 0.8,
            );
            if (clearOfOthers) {
                center = candidate;
                break;
            }
        }
        nebulae.push({
            name: summary.territory,
            center,
            radius,
            color: NEBULA_COLOR,
            seed,
            noteCount: summary.note_count,
        });
    });

    return { galaxies, bodies, nebulae };
}

function bodiesHas(bodies: SceneBody[], id: string): boolean {
    return bodies.some((b) => b.id === id);
}

/** A skill's files, split the way the picture draws them: each top-level
 *  folder with its contents (a ring), and the loose top-level files (moons). */
export function splitSkillFiles(files: readonly string[]): {
    folders: Map<string, string[]>;
    loose: string[];
} {
    const folders = new Map<string, string[]>();
    const loose: string[] = [];
    for (const file of files) {
        const slash = file.indexOf('/');
        if (slash === -1) {
            loose.push(file);
            continue;
        }
        const folder = file.slice(0, slash);
        const inside = folders.get(folder) ?? [];
        inside.push(file);
        folders.set(folder, inside);
    }
    return { folders, loose };
}

/** The outer edge of a planet's r-th ring; rings nest outward, Saturn-like. */
function ringOuterRadius(planetSize: number, r: number): number {
    return planetSize * (2.4 + r * 0.6);
}

function galaxyOrbitRadius(rand: () => number): number {
    return GALAXY_DISC_RADIUS * (1.05 + rand() * 0.25);
}

/** Resolve any body's world position at time t (seconds); moons chase their
 *  orbiting planet, so resolution recurses through the anchor chain. */
export function createPositionResolver(model: UniverseModel): (id: string, t: number) => Vec3 {
    const byId = new Map(model.bodies.map((b) => [b.id, b]));
    const galaxyCenters = new Map(model.galaxies.map((g) => [`galaxy:${g.name}`, g.center]));
    const nebulaCenters = new Map(model.nebulae.map((n) => [`nebula:${n.name}`, n.center]));
    const resolve = (id: string, t: number): Vec3 => {
        const galaxyCenter = galaxyCenters.get(id);
        if (galaxyCenter) {
            return galaxyCenter;
        }
        const nebulaCenter = nebulaCenters.get(id);
        if (nebulaCenter) {
            return nebulaCenter;
        }
        const body = byId.get(id);
        if (!body) {
            return [0, EYE_HEIGHT, 0];
        }
        if (body.position) {
            return body.position;
        }
        const route = body.route;
        if (route && route.stops.length >= 2) {
            const legs = route.stops.length;
            const along = (t / route.legSeconds + route.phase) % legs;
            const leg = Math.floor(along);
            const f = along - leg;
            const from = resolve(route.stops[leg], t);
            const to = resolve(route.stops[(leg + 1) % legs], t);
            // Slow out of dock, slow into the next: a smoothstep along the leg,
            // arcing above the disc plane so the ship clears the systems it crosses.
            const s = f * f * (3 - 2 * f);
            const length = Math.hypot(to[0] - from[0], to[1] - from[1], to[2] - from[2]);
            const lift = Math.sin(f * Math.PI) * Math.min(length * 0.18, 0.09);
            return [
                from[0] + (to[0] - from[0]) * s,
                from[1] + (to[1] - from[1]) * s + lift,
                from[2] + (to[2] - from[2]) * s,
            ];
        }
        const orbit = body.orbit;
        if (!orbit) {
            return [0, EYE_HEIGHT, 0];
        }
        const [ax, ay, az] = resolve(orbit.anchorId, t);
        const theta = orbit.phase + orbit.speed * t;
        const x = orbit.radius * Math.cos(theta);
        const flat = orbit.radius * Math.sin(theta);
        const y = flat * Math.sin(orbit.incline);
        const z = flat * Math.cos(orbit.incline);
        return [ax + x, ay + y, az + z];
    };
    return resolve;
}
