import { useEffect, useMemo } from 'react';

import { computeUniverse, NEBULA_COLOR, useGraph } from '@/viewmodels/graph';
import { useNav } from '@/viewmodels/nav';
import { useNebulae } from '@/viewmodels/nebulae';
import { Spinner } from '@/views/atoms/Spinner';

const HUB_COLOR = 'hsl(var(--brand))';
const GALAXY_RING = 300;
/** Nebulae sit beyond the earned galaxies: farther out, dimmer, dashed. */
const NEBULA_RING = 452;
/** Same palette as the 3D scene, so the two universe views read as one place. */
const GALAXY_COLORS = ['#38bdf8', '#34d399', '#fbbf24', '#fb7185', '#2dd4bf', '#c084fc'];
const MAKER_COLOR = '#94a3b8';

const polar = (radius: number, angle: number): { x: number; y: number } => ({
    x: radius * Math.cos(angle),
    y: radius * Math.sin(angle),
});

/** The universe view: every galaxy as a luminous body around the playbook hub,
 *  the unearned nebulae drifting dimmer and dashed beyond the earned ring. The
 *  surface is transparent, so it sits on the card and follows the light/dark
 *  theme; labels ride the shared --graph-* tokens for the same reason. */
export const UniverseMap = () => {
    const graph = useGraph((state) => state.graph);
    const loading = useGraph((state) => state.loading);
    const error = useGraph((state) => state.error);
    const load = useGraph((state) => state.load);
    const enterGalaxy = useGraph((state) => state.enterGalaxy);
    const setView = useNav((state) => state.setView);
    const nebulae = useNebulae((state) => state.nebulae);
    const nebulaeError = useNebulae((state) => state.error);
    const loadNebulae = useNebulae((state) => state.load);
    const selectNebula = useNebulae((state) => state.select);

    useEffect(() => {
        void load();
        void loadNebulae();
    }, [load, loadNebulae]);

    const galaxies = useMemo(() => (graph ? computeUniverse(graph) : []), [graph]);

    if (loading && !graph) {
        return <Spinner />;
    }
    if (error) {
        return <p className="text-sm text-destructive">{error}</p>;
    }
    if (!graph) {
        return null;
    }

    return (
        <svg
            viewBox="-535 -535 1070 1070"
            className="h-full w-full"
            role="img"
            aria-label="Universe map: one body per galaxy"
        >
            <defs>
                <radialGradient id="hub-grad" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stopColor="hsl(var(--foreground))" />
                    <stop offset="30%" stopColor={HUB_COLOR} />
                    <stop offset="100%" stopColor={HUB_COLOR} stopOpacity="0" />
                </radialGradient>
                {[...GALAXY_COLORS, MAKER_COLOR].map((color) => (
                    <radialGradient
                        key={color}
                        id={`glx-${color.slice(1)}`}
                        cx="50%"
                        cy="50%"
                        r="50%"
                    >
                        <stop offset="0%" stopColor={color} stopOpacity="0.5" />
                        <stop offset="50%" stopColor={color} stopOpacity="0.16" />
                        <stop offset="100%" stopColor={color} stopOpacity="0" />
                    </radialGradient>
                ))}
                <radialGradient id="neb-grad" cx="50%" cy="50%" r="50%">
                    <stop offset="0%" stopColor={NEBULA_COLOR} stopOpacity="0.2" />
                    <stop offset="100%" stopColor={NEBULA_COLOR} stopOpacity="0" />
                </radialGradient>
                <filter id="soft-glow" x="-60%" y="-60%" width="220%" height="220%">
                    <feGaussianBlur stdDeviation="6" />
                </filter>
            </defs>

            {galaxies.map((galaxy, i) => {
                const angle = (2 * Math.PI * i) / galaxies.length - Math.PI / 2;
                const { x, y } = polar(GALAXY_RING, angle);
                return (
                    <line
                        key={`spoke-${galaxy.name}`}
                        x1={0}
                        y1={0}
                        x2={x}
                        y2={y}
                        stroke="var(--graph-edge-hub)"
                        strokeWidth={1}
                        strokeOpacity={0.25}
                    />
                );
            })}

            <g className="cursor-pointer" onClick={() => setView('playbook')}>
                <circle r={82} fill={HUB_COLOR} opacity={0.26} filter="url(#soft-glow)" />
                <circle r={70} fill="url(#hub-grad)" />
                <circle
                    r={42}
                    fill={HUB_COLOR}
                    stroke="var(--graph-node-stroke)"
                    strokeWidth={1.5}
                />
                <text
                    y={-2}
                    textAnchor="middle"
                    fill="hsl(var(--foreground))"
                    fontSize={11}
                    fontWeight={700}
                    letterSpacing="0.1em"
                    style={{ pointerEvents: 'none' }}
                >
                    UNIVERSE
                </text>
                <text
                    y={12}
                    textAnchor="middle"
                    fill="hsl(var(--muted-foreground))"
                    fontSize={8.5}
                    style={{ pointerEvents: 'none' }}
                >
                    AI-PLAYBOOK.md
                </text>
            </g>

            {galaxies.map((galaxy, i) => {
                const angle = (2 * Math.PI * i) / galaxies.length - Math.PI / 2;
                const { x, y } = polar(GALAXY_RING, angle);
                const planets = galaxy.skills + galaxy.agents + galaxy.doors;
                const radius = Math.min(46 + Math.sqrt(galaxy.refs + planets) * 7, 110);
                const isMaker = galaxy.name === 'maker';
                const color = isMaker ? MAKER_COLOR : GALAXY_COLORS[i % GALAXY_COLORS.length];
                return (
                    <g
                        key={galaxy.name}
                        transform={`translate(${x} ${y})`}
                        className="cursor-pointer"
                        onClick={() => enterGalaxy(galaxy.name)}
                    >
                        <circle
                            r={radius * 1.12}
                            fill={color}
                            opacity={0.14}
                            filter="url(#soft-glow)"
                        />
                        <circle r={radius} fill={`url(#glx-${color.slice(1)})`} />
                        <circle
                            r={radius * 0.9}
                            fill="none"
                            stroke={color}
                            strokeOpacity={isMaker ? 0.4 : 0.5}
                            strokeWidth={1.5}
                            strokeDasharray={isMaker ? '5 5' : undefined}
                        />
                        <circle
                            r={radius * 0.5}
                            fill="none"
                            stroke={color}
                            strokeOpacity={0.22}
                            strokeDasharray="2 5"
                        />
                        <text
                            y={-6}
                            textAnchor="middle"
                            fill="var(--graph-label)"
                            fontSize={17}
                            fontWeight={700}
                            style={{ pointerEvents: 'none' }}
                        >
                            {galaxy.name}
                        </text>
                        <text
                            y={12}
                            textAnchor="middle"
                            fill="var(--graph-label-muted)"
                            fontSize={10.5}
                            style={{ pointerEvents: 'none' }}
                        >
                            {galaxy.refs} suns &middot; {planets} planets
                        </text>
                        {(galaxy.doors > 0 || galaxy.agents > 0) && (
                            <text
                                y={26}
                                textAnchor="middle"
                                fill="var(--graph-label-muted)"
                                fontSize={9}
                                style={{ pointerEvents: 'none' }}
                            >
                                {[
                                    galaxy.agents > 0 ? `${galaxy.agents} agents` : null,
                                    galaxy.doors > 0 ? `${galaxy.doors} doors` : null,
                                ]
                                    .filter(Boolean)
                                    .join(' · ')}{' '}
                                among them
                            </text>
                        )}
                    </g>
                );
            })}

            {/* The unearned zone: dim, dashed, second-class beside the
                galaxies (REF-Forge quarantine; the graph never carries these,
                they ride the HTTP-only nebula roster). */}
            {(nebulae ?? []).map((nebula, i, all) => {
                const angle = (2 * Math.PI * i) / all.length - Math.PI / 2 + Math.PI / 7;
                const { x, y } = polar(NEBULA_RING, angle);
                const radius = Math.min(30 + Math.sqrt(nebula.note_count) * 6, 60);
                return (
                    <g
                        key={nebula.territory}
                        transform={`translate(${x} ${y})`}
                        className="cursor-pointer"
                        onClick={() => {
                            selectNebula(nebula.territory);
                            setView('nebula');
                        }}
                    >
                        <circle r={radius * 1.1} fill="url(#neb-grad)" filter="url(#soft-glow)" />
                        <circle
                            r={radius}
                            fill="none"
                            stroke={NEBULA_COLOR}
                            strokeOpacity={0.5}
                            strokeWidth={1.25}
                            strokeDasharray="3 6"
                        />
                        <text
                            y={-4}
                            textAnchor="middle"
                            fill="var(--graph-label-muted)"
                            fontSize={12}
                            fontWeight={500}
                            style={{ pointerEvents: 'none' }}
                        >
                            {nebula.territory}
                        </text>
                        <text
                            y={11}
                            textAnchor="middle"
                            fill="var(--graph-label-muted)"
                            fillOpacity={0.75}
                            fontSize={8.5}
                            style={{ pointerEvents: 'none' }}
                        >
                            {nebula.note_count} stardust &middot; unearned
                        </text>
                    </g>
                );
            })}

            {/* An honest gap: when the roster fetch fails, say the unearned
                zone is missing instead of silently hiding it. */}
            {nebulaeError && (
                <text
                    y={522}
                    textAnchor="middle"
                    fill="var(--graph-label-muted)"
                    fillOpacity={0.7}
                    fontSize={10}
                >
                    nebulae unavailable
                </text>
            )}
        </svg>
    );
};
