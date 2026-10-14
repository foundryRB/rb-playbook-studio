import type { GraphNodeResponse, GraphResponse } from '@/models';

/** Fixed presentation order and color for each REF domain. */
export const DOMAIN_ORDER = [
    'meta',
    'architecture',
    'language',
    'framework',
    'practice',
    'methodology',
    'pkm',
] as const;

export const DOMAIN_COLORS: Record<string, string> = {
    meta: '#8b5cf6',
    architecture: '#0ea5e9',
    language: '#10b981',
    framework: '#f59e0b',
    practice: '#f43f5e',
    methodology: '#6366f1',
    pkm: '#14b8a6',
};

export const SKILL_COLOR = '#94a3b8';
export const AGENT_COLOR = '#84cc16';
export const PLAYBOOK_COLOR = '#0f172a';
export const MCP_COLOR = '#d97706';
export const RAG_COLOR = '#d946ef';
/** Nebulae are unearned (REF-Forge): one muted hue, never a bright body. */
export const NEBULA_COLOR = '#64748b';

/** Declared-door planet kinds (REF-Universe: mcps and rags orbit like skills). */
export const DOOR_KINDS: ReadonlySet<string> = new Set(['mcp', 'rag']);

/** Every planet kind that rides the outer ring: carried (skill, agent) and
 *  declared (mcp, rag). REF-Universe §3's one axis, as a predicate. */
export const isPlanetKind = (kind: string): boolean =>
    kind === 'skill' || kind === 'agent' || DOOR_KINDS.has(kind);

/** The edge kinds whose FIRST occurrence names a planet's home sun. */
export const HOME_EDGE_KINDS: ReadonlySet<string> = new Set([
    'skill-to-ref',
    'door-to-ref',
    'agent-to-ref',
]);

export const GALAXY_CORE_PREFIX = 'galaxy-core:';

const outerColor = (kind: string): string =>
    kind === 'mcp'
        ? MCP_COLOR
        : kind === 'rag'
          ? RAG_COLOR
          : kind === 'agent'
            ? AGENT_COLOR
            : SKILL_COLOR;

export interface LaidOutNode {
    node: GraphNodeResponse;
    x: number;
    y: number;
    /** Angle in radians; NaN for the center node. Drives rotated labels. */
    angle: number;
    color: string;
}

export interface DomainArc {
    domain: string;
    startAngle: number;
    endAngle: number;
    color: string;
}

export const REF_RADIUS = 215;
export const SKILL_RADIUS = 350;

const polar = (radius: number, angle: number): { x: number; y: number } => ({
    x: Math.round(radius * Math.cos(angle) * 100) / 100,
    y: Math.round(radius * Math.sin(angle) * 100) / 100,
});

/**
 * Radial layout: playbook at the origin, REFs on an inner ring grouped by
 * domain (DOMAIN_ORDER), planets (skills, agents, doors) on an outer ring
 * near the mean angle of the REFs they cite.
 */
export function computeLayout(graph: GraphResponse): LaidOutNode[] {
    const refs = graph.nodes.filter((n) => n.kind === 'ref');
    const skills = graph.nodes.filter((n) => isPlanetKind(n.kind));
    const playbook = graph.nodes.filter((n) => n.kind === 'playbook');

    const sortedRefs = sortRefsByDomain(refs);

    const refAngle = new Map<string, number>();
    const out: LaidOutNode[] = playbook.map((node) => ({
        node,
        x: 0,
        y: 0,
        angle: Number.NaN,
        color: PLAYBOOK_COLOR,
    }));

    sortedRefs.forEach((node, i) => {
        const angle = (2 * Math.PI * i) / sortedRefs.length - Math.PI / 2;
        refAngle.set(node.id, angle);
        out.push({
            node,
            ...polar(REF_RADIUS, angle),
            angle,
            color: DOMAIN_COLORS[node.domain ?? ''] ?? SKILL_COLOR,
        });
    });

    const desiredAngle = (skillId: string): number => {
        const targets = graph.edges
            .filter((e) => HOME_EDGE_KINDS.has(e.kind) && e.source === skillId)
            .map((e) => refAngle.get(e.target))
            .filter((a): a is number => a !== undefined);
        if (targets.length === 0) {
            return Math.PI / 2;
        }
        // Mean of unit vectors, so angles across the wrap point average correctly.
        const x = targets.reduce((acc, a) => acc + Math.cos(a), 0);
        const y = targets.reduce((acc, a) => acc + Math.sin(a), 0);
        return Math.atan2(y, x);
    };

    // Evenly spaced on the outer ring, ordered by where their REFs sit.
    const sortedSkills = [...skills].sort((a, b) => desiredAngle(a.id) - desiredAngle(b.id));
    sortedSkills.forEach((node, i) => {
        const angle = (2 * Math.PI * i) / sortedSkills.length - Math.PI / 2;
        out.push({ node, ...polar(SKILL_RADIUS, angle), angle, color: outerColor(node.kind) });
    });

    return out;
}

export interface GalaxySummary {
    name: string;
    refs: number;
    skills: number;
    agents: number;
    doors: number;
}

/** Per-galaxy counts of suns, carried planets (skills, agents), and doors. */
export function computeUniverse(graph: GraphResponse): GalaxySummary[] {
    const by = new Map<string, GalaxySummary>();
    for (const node of graph.nodes) {
        if (!node.galaxy) {
            continue;
        }
        const summary = by.get(node.galaxy) ?? {
            name: node.galaxy,
            refs: 0,
            skills: 0,
            agents: 0,
            doors: 0,
        };
        if (node.kind === 'ref') {
            summary.refs += 1;
        } else if (node.kind === 'skill') {
            summary.skills += 1;
        } else if (node.kind === 'agent') {
            summary.agents += 1;
        } else if (DOOR_KINDS.has(node.kind)) {
            summary.doors += 1;
        }
        by.set(node.galaxy, summary);
    }
    return [...by.values()].sort((a, b) => a.name.localeCompare(b.name));
}

/**
 * The galaxy drill-down: exactly that galaxy's nodes plus a synthesized
 * routing core at the center; hub edges rewire onto the core, and every
 * edge crossing the galaxy boundary is dropped.
 */
export function scopeToGalaxy(graph: GraphResponse, galaxy: string): GraphResponse {
    const core: GraphNodeResponse = {
        id: `${GALAXY_CORE_PREFIX}${galaxy}`,
        kind: 'playbook',
        label: galaxy,
        domain: null,
        summary: `The ${galaxy} galaxy's routing core (GALAXY.md).`,
        galaxy,
        moons: [],
    };
    const scoped = graph.nodes.filter((n) => n.galaxy === galaxy);
    const inScope = new Set(scoped.map((n) => n.id));
    const seen = new Set<string>();
    const edges = graph.edges.flatMap((edge) => {
        const rewired =
            edge.kind === 'playbook-to-ref'
                ? inScope.has(edge.target)
                    ? { ...edge, source: core.id }
                    : null
                : inScope.has(edge.source) && inScope.has(edge.target)
                  ? edge
                  : null;
        if (rewired === null) {
            return [];
        }
        const key = `${rewired.kind}|${rewired.source}|${rewired.target}`;
        if (seen.has(key)) {
            return [];
        }
        seen.add(key);
        return [rewired];
    });
    return { nodes: [core, ...scoped], edges };
}

/** One arc per contiguous domain group on the REF ring, for cluster accents. */
export function computeDomainArcs(graph: GraphResponse): DomainArc[] {
    const sortedRefs = sortRefsByDomain(graph.nodes.filter((n) => n.kind === 'ref'));
    if (sortedRefs.length === 0) {
        return [];
    }
    const slot = (2 * Math.PI) / sortedRefs.length;
    const arcs: DomainArc[] = [];
    let start = 0;
    for (let i = 1; i <= sortedRefs.length; i += 1) {
        const domain = sortedRefs[start].domain ?? 'practice';
        if (i === sortedRefs.length || (sortedRefs[i].domain ?? 'practice') !== domain) {
            arcs.push({
                domain,
                startAngle: start * slot - Math.PI / 2 - slot * 0.32,
                endAngle: (i - 1) * slot - Math.PI / 2 + slot * 0.32,
                color: DOMAIN_COLORS[domain] ?? SKILL_COLOR,
            });
            start = i;
        }
    }
    return arcs;
}

function sortRefsByDomain(refs: GraphNodeResponse[]): GraphNodeResponse[] {
    return [...refs].sort((a, b) => {
        const da = DOMAIN_ORDER.indexOf((a.domain ?? 'practice') as (typeof DOMAIN_ORDER)[number]);
        const db = DOMAIN_ORDER.indexOf((b.domain ?? 'practice') as (typeof DOMAIN_ORDER)[number]);
        return da === db ? a.id.localeCompare(b.id) : da - db;
    });
}

export const selectNodeCount = (state: { graph: GraphResponse | null }): number =>
    state.graph?.nodes.length ?? 0;

/** A galaxy's own domain vocabulary, in palette order: the filter legend
 *  never advertises a domain the galaxy has no sun for. */
export function galaxyDomains(graph: GraphResponse | null, galaxy: string | null): string[] {
    if (!graph || !galaxy) {
        return [...DOMAIN_ORDER];
    }
    const present = new Set(
        graph.nodes
            .filter((n) => n.kind === 'ref' && n.galaxy === galaxy)
            .map((n) => n.domain)
            .filter((d): d is string => !!d),
    );
    // Palette order first; domains a future galaxy invents sort last but
    // still filter (they get the neutral chip color).
    const rank = (d: string): number => {
        const i = DOMAIN_ORDER.indexOf(d as (typeof DOMAIN_ORDER)[number]);
        return i === -1 ? Number.MAX_SAFE_INTEGER : i;
    };
    return [...present].sort((a, b) => rank(a) - rank(b));
}
