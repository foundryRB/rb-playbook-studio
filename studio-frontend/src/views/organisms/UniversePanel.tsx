import { useState } from 'react';
import type { Components } from 'react-markdown';

import type {
    AgentResponse,
    DoorResponse,
    GalaxyResponse,
    GraphResponse,
    NebulaDetailResponse,
    NebulaNoteResponse,
    PlaybookResponse,
    RefDetailResponse,
    SkillResponse,
} from '@/models';
import { cn } from '@/utils';
import { DomainBadge } from '@/views/atoms/DomainBadge';
import { Markdown } from '@/views/molecules/Markdown';
import { SlotBadge, slotOf } from '@/views/molecules/SectionSlot';
import { EgoGraph } from '@/views/organisms/EgoGraph';

/** What the universe panel knows about the selected body's document. */
export type PanelPayload =
    | { kind: 'ref'; ref: RefDetailResponse }
    | { kind: 'skill'; skill: SkillResponse }
    | { kind: 'agent'; agent: AgentResponse }
    | { kind: 'door'; door: DoorResponse }
    | { kind: 'galaxy'; galaxy: GalaxyResponse }
    | { kind: 'playbook'; playbook: PlaybookResponse }
    | { kind: 'moon'; moonOf: string; file: string; content: string }
    | { kind: 'ring'; moonOf: string; folder: string; files: string[] }
    | { kind: 'nebula'; nebula: NebulaDetailResponse }
    | { kind: 'error'; message: string };

export interface PanelDoc {
    id: string;
    title: string;
    meta: string;
    accent: string;
    /** Raw markdown for the in-headset canvas panel. */
    markdown: string;
    payload: PanelPayload;
}

interface UniversePanelProps {
    doc: PanelDoc;
    graph: GraphResponse | null;
    components: Components;
    onTravel: (id: string) => void;
    onClose: () => void;
}

const KIND_LABEL: Record<PanelPayload['kind'], string> = {
    ref: 'sun',
    skill: 'planet',
    agent: 'agent',
    door: 'door',
    galaxy: 'galaxy',
    playbook: 'the hub',
    moon: 'moon',
    ring: 'ring',
    nebula: 'nebula · unearned',
    error: 'error',
};

const Chip = ({
    label,
    onClick,
    title,
}: {
    label: string;
    onClick?: () => void;
    title?: string;
}) =>
    onClick ? (
        <button
            onClick={onClick}
            title={title ?? `Travel to ${label}`}
            className="rounded-md border border-link/40 bg-primary/10 px-2 py-0.5 font-mono text-[11px] text-link hover:bg-primary/20"
        >
            {label}
        </button>
    ) : (
        <span className="rounded-md border border-border px-2 py-0.5 font-mono text-[11px] text-muted-foreground">
            {label}
        </span>
    );

const ChipRow = ({
    caption,
    ids,
    onTravel,
}: {
    caption: string;
    ids: string[];
    onTravel: (id: string) => void;
}) =>
    ids.length === 0 ? null : (
        <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] text-muted-foreground">{caption}:</span>
            {ids.map((id) => (
                <Chip key={id} label={id} onClick={() => onTravel(id)} />
            ))}
        </div>
    );

/** The graph-derived neighborhood, exactly what the 2D reader's Connections
 *  rail knows, rendered as travel chips. */
const Connections = ({
    id,
    graph,
    onTravel,
}: {
    id: string;
    graph: GraphResponse | null;
    onTravel: (id: string) => void;
}) => {
    if (!graph) {
        return null;
    }
    const edges = graph.edges;
    const cites = edges
        .filter((e) => e.kind === 'ref-to-ref' && e.source === id)
        .map((e) => e.target);
    const citedBy = edges
        .filter((e) => e.kind === 'ref-to-ref' && e.target === id)
        .map((e) => e.source);
    const skills = edges
        .filter((e) => e.kind === 'skill-to-ref' && e.target === id)
        .map((e) => e.source);
    const doors = edges
        .filter((e) => e.kind === 'door-to-ref' && e.target === id)
        .map((e) => e.source);
    const agents = edges
        .filter((e) => e.kind === 'agent-to-ref' && e.target === id)
        .map((e) => e.source);
    if (cites.length + citedBy.length + skills.length + doors.length + agents.length === 0) {
        return null;
    }
    return (
        <section className="space-y-1.5 rounded-md border border-border bg-secondary/30 p-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Connections
            </h3>
            <EgoGraph refName={id} onPick={onTravel} />
            <ChipRow caption="cites" ids={cites} onTravel={onTravel} />
            <ChipRow caption="cited by" ids={citedBy} onTravel={onTravel} />
            <ChipRow caption="instantiated by" ids={skills} onTravel={onTravel} />
            <ChipRow caption="orbited by" ids={agents} onTravel={onTravel} />
            <ChipRow caption="doors" ids={doors} onTravel={onTravel} />
        </section>
    );
};

const SectionCards = ({
    sections,
    components,
}: {
    sections: { title: string; body: string; number?: number; generated?: boolean }[];
    components: Components;
}) => (
    <>
        {sections.map((section, i) => (
            <section
                key={`${section.title}-${i}`}
                className="rounded-md border border-border bg-card/60 p-3"
            >
                <div className="mb-1.5 flex items-center justify-between gap-2">
                    <h3 className="text-sm font-semibold">{section.title}</h3>
                    <SlotBadge
                        slot={slotOf({
                            number: section.number ?? i,
                            title: section.title,
                            body: section.body,
                            generated: section.generated ?? false,
                        })}
                    />
                </div>
                <Markdown components={components}>{section.body}</Markdown>
            </section>
        ))}
    </>
);

/** One stardust note's frontmatter, as muted chips. */
const NoteFacts = ({ note }: { note: NebulaNoteResponse }) => (
    <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-muted-foreground">
        <span className="rounded border border-border px-1.5 py-0.5 font-mono">{note.type}</span>
        <span className="rounded border border-border px-1.5 py-0.5">
            confidence {note.confidence}
        </span>
        {note.vote && (
            <span className="rounded border border-border px-1.5 py-0.5">vote {note.vote}</span>
        )}
        <span className="rounded border border-border px-1.5 py-0.5">{note.status}</span>
        {note.seats.map((seat) => (
            <span key={seat} className="rounded border border-border/60 px-1.5 py-0.5 italic">
                {seat}
            </span>
        ))}
    </div>
);

/** A nebula's stardust: the roster of notes, each readable in place, and the
 *  fronting NEBULA.md. Dashed borders and muted ink throughout: unearned
 *  content stays visibly second-class (REF-Forge quarantine). */
const NebulaStardust = ({
    nebula,
    components,
}: {
    nebula: NebulaDetailResponse;
    components: Components;
}) => {
    const [openNote, setOpenNote] = useState<string | null>(null);
    const note = nebula.notes.find((n) => n.name === openNote) ?? null;
    return (
        <>
            <blockquote className="border-l-2 border-slate-500/60 pl-3 text-sm italic text-muted-foreground">
                Unearned stardust: nothing here informs work outside the Forge until it is smelted.
            </blockquote>
            <section className="space-y-1.5 rounded-md border border-dashed border-border bg-secondary/20 p-3">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Stardust ({nebula.notes.length})
                </h3>
                <div className="flex flex-wrap gap-1.5">
                    {nebula.notes.map((n) => (
                        <button
                            key={n.name}
                            onClick={() => setOpenNote(openNote === n.name ? null : n.name)}
                            title={`${n.type} · ${n.status}`}
                            className={
                                openNote === n.name
                                    ? 'rounded-md border border-dashed border-slate-400/70 bg-secondary/60 px-2 py-0.5 font-mono text-[11px] text-foreground'
                                    : 'rounded-md border border-dashed border-border px-2 py-0.5 font-mono text-[11px] text-muted-foreground hover:text-foreground'
                            }
                        >
                            {n.name}
                        </button>
                    ))}
                </div>
            </section>
            {note && (
                <section className="space-y-2 rounded-md border border-dashed border-border bg-card/40 p-3">
                    <NoteFacts note={note} />
                    <Markdown components={components}>{note.body}</Markdown>
                    {note.sources.length > 0 && (
                        <div className="space-y-0.5 text-[11px] text-muted-foreground">
                            <span className="font-semibold uppercase tracking-wider">sources</span>
                            {note.sources.map((source) => (
                                <a
                                    key={source}
                                    href={source}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="block truncate underline decoration-border underline-offset-2 hover:text-foreground"
                                >
                                    {source}
                                </a>
                            ))}
                        </div>
                    )}
                </section>
            )}
            <div className="rounded-md border border-dashed border-border bg-card/40 p-3 opacity-90">
                <Markdown components={components}>{nebula.raw}</Markdown>
            </div>
        </>
    );
};

/** The 3D view's reading surface: the 2D readers' structure (section cards,
 *  slot badges, domain badge, connections, file lists) with travel controls. */
export const UniversePanel = ({
    doc,
    graph,
    components,
    onTravel,
    onClose,
}: UniversePanelProps) => {
    const [wide, setWide] = useState(false);
    const payload = doc.payload;

    return (
        <aside
            className={cn(
                'absolute bottom-3 right-3 top-3 z-10 flex flex-col overflow-hidden rounded-lg border border-border bg-background/95 shadow-xl backdrop-blur transition-[width]',
                wide ? 'w-[min(880px,72%)]' : 'w-[min(520px,46%)]',
            )}
            style={{ borderLeftWidth: 3, borderLeftColor: doc.accent }}
        >
            <header className="flex items-start justify-between gap-2 border-b border-border px-4 py-3">
                <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                        <h2 className="truncate text-base font-bold">{doc.title}</h2>
                        <span
                            className="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
                            style={{ backgroundColor: `${doc.accent}26`, color: doc.accent }}
                        >
                            {KIND_LABEL[payload.kind]}
                        </span>
                        {payload.kind === 'ref' && <DomainBadge domain={payload.ref.domain} />}
                    </div>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">{doc.meta}</p>
                </div>
                <div className="flex shrink-0 gap-1.5">
                    <button
                        onClick={() => setWide((w) => !w)}
                        title={wide ? 'Narrow panel' : 'Widen panel'}
                        className="rounded-md border border-border px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground"
                    >
                        {wide ? '⇥' : '⇤'}
                    </button>
                    <button
                        onClick={onClose}
                        title="Close (Esc)"
                        className="rounded-md border border-border px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground"
                    >
                        ✕
                    </button>
                </div>
            </header>

            <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-3">
                {payload.kind === 'ref' && (
                    <>
                        <blockquote
                            className="border-l-2 pl-3 text-sm italic text-muted-foreground"
                            style={{ borderColor: doc.accent }}
                        >
                            {payload.ref.summary}
                        </blockquote>
                        <Connections id={doc.id} graph={graph} onTravel={onTravel} />
                        <SectionCards sections={payload.ref.sections} components={components} />
                    </>
                )}

                {payload.kind === 'skill' && (
                    <>
                        <blockquote
                            className="border-l-2 pl-3 text-sm italic text-muted-foreground"
                            style={{ borderColor: doc.accent }}
                        >
                            {payload.skill.description}
                        </blockquote>
                        <div className="space-y-1.5 rounded-md border border-border bg-secondary/30 p-3">
                            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                Solar system
                            </h3>
                            {payload.skill.refs.length > 0 && (
                                <div className="flex flex-wrap items-center gap-1.5">
                                    <span className="text-[11px] text-muted-foreground">home:</span>
                                    <button
                                        onClick={() => onTravel(payload.skill.refs[0])}
                                        title={`Travel to ${payload.skill.refs[0]}, this skill's home sun`}
                                        className="rounded-md border border-link bg-primary/20 px-2 py-0.5 font-mono text-[11px] font-semibold text-link hover:bg-primary/30"
                                    >
                                        ⌂ {payload.skill.refs[0]}
                                    </button>
                                </div>
                            )}
                            <ChipRow
                                caption="also cites"
                                ids={payload.skill.refs.slice(1)}
                                onTravel={onTravel}
                            />
                            <div className="flex flex-wrap items-center gap-1.5">
                                <span className="text-[11px] text-muted-foreground">moons:</span>
                                {payload.skill.files.filter((f) => f !== 'SKILL.md').length ===
                                    0 && (
                                    <span className="text-[11px] text-muted-foreground/70">
                                        none: SKILL.md flies alone
                                    </span>
                                )}
                                {payload.skill.files
                                    .filter((f) => f !== 'SKILL.md')
                                    .map((f) => (
                                        <Chip
                                            key={f}
                                            label={f}
                                            onClick={() =>
                                                onTravel(`moon:${payload.skill.name}/${f}`)
                                            }
                                        />
                                    ))}
                            </div>
                            <p className="text-[11px] text-muted-foreground/70">
                                {payload.skill.installed
                                    ? 'installed in this runtime'
                                    : 'not installed in this runtime'}
                            </p>
                            <EgoGraph refName={doc.id} onPick={onTravel} />
                        </div>
                        <div className="rounded-md border border-border bg-card/60 p-3">
                            <Markdown components={components}>{payload.skill.body}</Markdown>
                        </div>
                    </>
                )}

                {payload.kind === 'agent' && (
                    <>
                        <blockquote
                            className="border-l-2 pl-3 text-sm italic text-muted-foreground"
                            style={{ borderColor: doc.accent }}
                        >
                            {payload.agent.summary}
                        </blockquote>
                        <div className="space-y-1.5 rounded-md border border-border bg-secondary/30 p-3">
                            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                                Solar system
                            </h3>
                            {payload.agent.refs.length > 0 && (
                                <div className="flex flex-wrap items-center gap-1.5">
                                    <span className="text-[11px] text-muted-foreground">home:</span>
                                    <button
                                        onClick={() => onTravel(payload.agent.refs[0])}
                                        title={`Travel to ${payload.agent.refs[0]}, this agent's home sun`}
                                        className="rounded-md border border-link bg-primary/20 px-2 py-0.5 font-mono text-[11px] font-semibold text-link hover:bg-primary/30"
                                    >
                                        ⌂ {payload.agent.refs[0]}
                                    </button>
                                </div>
                            )}
                            <ChipRow
                                caption="also cites"
                                ids={payload.agent.refs.slice(1)}
                                onTravel={onTravel}
                            />
                            <ChipRow
                                caption="licensed skills"
                                ids={payload.agent.skills}
                                onTravel={onTravel}
                            />
                            <ChipRow
                                caption="needs doors"
                                ids={payload.agent.doors}
                                onTravel={onTravel}
                            />
                            <p className="text-[11px] text-muted-foreground/70">
                                posture: {payload.agent.posture.permission}
                                {payload.agent.posture.writes ? ' · writes' : ' · read-only'}
                                {payload.agent.posture.fresh_eyes ? ' · fresh eyes' : ''}
                            </p>
                            <EgoGraph refName={doc.id} onPick={onTravel} />
                        </div>
                        <div className="rounded-md border border-border bg-card/60 p-3">
                            <Markdown components={components}>{payload.agent.body}</Markdown>
                        </div>
                    </>
                )}

                {payload.kind === 'door' && (
                    <>
                        <ChipRow
                            caption="doctrine suns"
                            ids={payload.door.refs}
                            onTravel={onTravel}
                        />
                        <EgoGraph refName={doc.id} onPick={onTravel} />
                        <div className="rounded-md border border-border bg-card/60 p-3">
                            <Markdown components={components}>{doc.markdown}</Markdown>
                        </div>
                        <p className="text-[11px] text-muted-foreground/70">
                            A declared door: the corpus holds purpose and doctrine, the server
                            declares its own interface at connect, the environment binds endpoint
                            and credential.
                        </p>
                    </>
                )}

                {payload.kind === 'galaxy' && (
                    <SectionCards sections={payload.galaxy.sections} components={components} />
                )}

                {payload.kind === 'playbook' && (
                    <SectionCards sections={payload.playbook.sections} components={components} />
                )}

                {payload.kind === 'nebula' && (
                    <NebulaStardust nebula={payload.nebula} components={components} />
                )}

                {payload.kind === 'moon' && (
                    <>
                        <ChipRow caption="moon of" ids={[payload.moonOf]} onTravel={onTravel} />
                        <div className="rounded-md border border-border bg-card/60 p-3">
                            <Markdown components={components}>{doc.markdown}</Markdown>
                        </div>
                    </>
                )}

                {payload.kind === 'ring' && (
                    <>
                        <ChipRow caption="ring of" ids={[payload.moonOf]} onTravel={onTravel} />
                        <ul className="space-y-0.5 font-mono text-[11px] text-muted-foreground">
                            {payload.files.map((file) => (
                                <li key={file}>{file}</li>
                            ))}
                        </ul>
                        {doc.markdown && (
                            <div className="rounded-md border border-border bg-card/60 p-3">
                                <Markdown components={components}>{doc.markdown}</Markdown>
                            </div>
                        )}
                    </>
                )}

                {payload.kind === 'error' && (
                    <p className="text-sm text-destructive">{payload.message}</p>
                )}
            </div>

            <footer className="border-t border-border px-4 py-1.5 text-[10px] text-muted-foreground/70">
                chips and highlighted references travel there
            </footer>
        </aside>
    );
};
