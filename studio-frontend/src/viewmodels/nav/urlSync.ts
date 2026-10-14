import { useEffect } from 'react';

import { useAgentDetail } from '@/viewmodels/agentdetail';
import { useGalaxyDetail } from '@/viewmodels/galaxydetail';
import { useGraph } from '@/viewmodels/graph';
import { useNebulae } from '@/viewmodels/nebulae';
import { useDoorDetail } from '@/viewmodels/doordetail';
import { useSkillDetail } from '@/viewmodels/skilldetail';

import { useNav } from './nav.actions';

/** URL <-> navigation sync (REF-Frontend: the location IS the state, so the
 *  browser's back/forward work and every page is a shareable link). Hash
 *  routing, deliberately: the prod SPA is served by StaticFiles, which 404s a
 *  deep path like /ref/REF-Foo on refresh; a hash rides under "/" and always
 *  survives. All in-app navigation already flows through these store actions,
 *  so mirroring them to the hash needs no change to any button. */

const enc = encodeURIComponent;

/** The canonical hash for the current navigation state. */
function pathForState(): string {
    const view = useNav.getState().view;
    switch (view) {
        case 'map': {
            const galaxy = useGraph.getState().galaxy;
            return galaxy ? `/g/${enc(galaxy)}` : '/';
        }
        case 'map3d':
            return '/3d';
        case 'playbook':
            return '/playbook';
        case 'ref': {
            const id = useGraph.getState().selectedRef;
            return id ? `/ref/${enc(id)}` : '/';
        }
        case 'skill': {
            const id = useSkillDetail.getState().selectedSkill;
            return id ? `/skill/${enc(id)}` : '/';
        }
        case 'agent': {
            const id = useAgentDetail.getState().selectedAgent;
            return id ? `/agent/${enc(id)}` : '/';
        }
        case 'door': {
            const id = useDoorDetail.getState().selectedDoor;
            return id ? `/door/${enc(id)}` : '/';
        }
        case 'galaxy': {
            const id = useGalaxyDetail.getState().selectedGalaxy;
            return id ? `/galaxy/${enc(id)}` : '/';
        }
        case 'nebula': {
            const id = useNebulae.getState().selectedNebula;
            return id ? `/nebula/${enc(id)}` : '/';
        }
        case 'create':
            return '/create';
        case 'createskill':
            return '/createskill';
        case 'createagent':
            return '/createagent';
        case 'createdoor':
            return '/createdoor';
        default:
            return '/';
    }
}

/** Apply a hash to the stores by replaying the same actions a click would:
 *  the readers load on their id, so a cold deep-link hydrates itself. */
function applyPath(path: string): void {
    const [head, rawId] = path.replace(/^\/+/, '').split('/');
    const id = rawId ? decodeURIComponent(rawId) : null;
    const nav = useNav.getState();
    const graph = useGraph.getState();
    switch (head) {
        case '':
        case undefined:
            graph.exitToUniverse();
            nav.setView('map');
            break;
        case 'g':
            if (id) {
                graph.enterGalaxy(id);
            } else {
                graph.exitToUniverse();
            }
            nav.setView('map');
            break;
        case '3d':
            nav.setView('map3d');
            break;
        case 'playbook':
            nav.setView('playbook');
            break;
        case 'ref':
            if (id) {
                graph.select(id);
                nav.setView('ref');
            }
            break;
        case 'skill':
            if (id) {
                useSkillDetail.getState().select(id);
                nav.setView('skill');
            }
            break;
        case 'agent':
            if (id) {
                useAgentDetail.getState().select(id);
                nav.setView('agent');
            }
            break;
        case 'door':
            if (id) {
                useDoorDetail.getState().select(id);
                nav.setView('door');
            }
            break;
        case 'galaxy':
            if (id) {
                useGalaxyDetail.getState().select(id);
                nav.setView('galaxy');
            }
            break;
        case 'nebula':
            if (id) {
                useNebulae.getState().select(id);
                nav.setView('nebula');
            }
            break;
        case 'create':
            nav.setView('create');
            break;
        case 'createskill':
            nav.setView('createskill');
            break;
        case 'createagent':
            nav.setView('createagent');
            break;
        case 'createdoor':
            nav.setView('createdoor');
            break;
        default:
            nav.setView('map');
    }
}

const currentHash = (): string => window.location.hash.replace(/^#/, '') || '/';

/** Wire the two directions once. Returns a teardown. A single `applying` flag
 *  breaks the echo: while a hash is being applied to the stores, the store
 *  subscriptions that would push it back are suppressed. */
function wireUrlSync(): () => void {
    let applying = false;

    const pushFromState = (): void => {
        if (applying) {
            return;
        }
        const next = pathForState();
        if (currentHash() !== next) {
            window.location.hash = next; // new history entry; fires 'hashchange'
        }
    };

    const applyFromHash = (): void => {
        applying = true;
        try {
            applyPath(currentHash());
        } finally {
            applying = false;
        }
    };

    // Initial: hydrate a deep-link, or stamp the base hash without a history entry.
    applying = true;
    try {
        if (window.location.hash && currentHash() !== '/') {
            applyPath(currentHash());
        } else {
            window.history.replaceState(null, '', `#${pathForState()}`);
        }
    } finally {
        applying = false;
    }

    window.addEventListener('hashchange', applyFromHash);
    const stores = [
        useNav,
        useGraph,
        useSkillDetail,
        useAgentDetail,
        useDoorDetail,
        useGalaxyDetail,
        useNebulae,
    ];
    const unsubscribes = stores.map((store) => store.subscribe(pushFromState));

    return () => {
        window.removeEventListener('hashchange', applyFromHash);
        unsubscribes.forEach((unsub) => unsub());
    };
}

/** Mount once (in App) to bind the location to the navigation stores. */
export function useUrlSync(): void {
    useEffect(() => wireUrlSync(), []);
}
