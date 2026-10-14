import type { Components } from 'react-markdown';

import { useAgentDetail } from '@/viewmodels/agentdetail';
import { useGalaxyDetail } from '@/viewmodels/galaxydetail';
import { useGraph } from '@/viewmodels/graph';
import { useNav } from '@/viewmodels/nav';
import { useSkillDetail } from '@/viewmodels/skilldetail';

/** A corpus path resolved to the thing the studio can open. */
export interface CorpusTarget {
    kind: 'galaxy' | 'ref' | 'skill' | 'agent';
    id: string;
}

/** Map a corpus-relative markdown href onto a studio target.
 *
 *  The corpus links by repo path - AI-PLAYBOOK.md routes to a shelf as
 *  `[galaxies/craft/GALAXY.md](galaxies/craft/GALAXY.md)` - because on disk that
 *  is what resolves, and the link checker validates exactly that. Rendered in the
 *  studio those paths are not URLs the SPA serves, so an untranslated anchor
 *  navigates the browser clean out of the app. Translating here keeps the corpus
 *  authored for the filesystem and still clickable in the reader.
 *
 *  Returns null for anything not addressable as a studio view (an external URL,
 *  a bare anchor, a file with no reader).
 */
export function resolveCorpusHref(href: string): CorpusTarget | null {
    const path = href.split('#')[0].replace(/^\.\//, '').replace(/^\/+/, '');
    if (!path) {
        return null;
    }

    const galaxy = /^galaxies\/([^/]+)\/GALAXY\.md$/.exec(path);
    if (galaxy) {
        return { kind: 'galaxy', id: galaxy[1] };
    }
    // Skills before REFs: a skill lives at galaxies/<g>/skills/<name>/SKILL.md,
    // which the REF pattern must not swallow.
    const skill = /^galaxies\/[^/]+\/skills\/([^/]+)\/SKILL\.md$/.exec(path);
    if (skill) {
        return { kind: 'skill', id: skill[1] };
    }
    const agent = /^galaxies\/[^/]+\/agents\/([^/]+)\.md$/.exec(path);
    if (agent) {
        return { kind: 'agent', id: agent[1] };
    }
    const ref = /^galaxies\/[^/]+\/(REF-[^/]+)\.md$/.exec(path);
    if (ref) {
        return { kind: 'ref', id: ref[1] };
    }
    return null;
}

/** Open a resolved target by replaying the same store actions a click in the
 *  sidebar or on the map would, so the hash, the history entry, and the reader
 *  all follow exactly as they do everywhere else (urlSync mirrors these). */
export function openCorpusTarget(target: CorpusTarget): void {
    const nav = useNav.getState();
    switch (target.kind) {
        case 'galaxy':
            useGalaxyDetail.getState().select(target.id);
            nav.setView('galaxy');
            break;
        case 'ref':
            useGraph.getState().select(target.id);
            nav.setView('ref');
            break;
        case 'skill':
            useSkillDetail.getState().select(target.id);
            nav.setView('skill');
            break;
        case 'agent':
            useAgentDetail.getState().select(target.id);
            nav.setView('agent');
            break;
    }
}

/** react-markdown overrides that keep corpus links inside the studio.
 *
 *  Three cases, and the third matters: a path the studio cannot open renders as
 *  inert text rather than a live anchor, because a link that silently leaves the
 *  SPA is worse than one that visibly does nothing.
 */
export const corpusLinkComponents: Components = {
    a: ({ href, children }) => {
        const target = resolveCorpusHref(href ?? '');
        if (target) {
            return (
                <button
                    onClick={() => openCorpusTarget(target)}
                    title={`Open ${target.id}`}
                    className="font-medium text-link underline decoration-link/40 underline-offset-2 hover:decoration-link"
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
};
