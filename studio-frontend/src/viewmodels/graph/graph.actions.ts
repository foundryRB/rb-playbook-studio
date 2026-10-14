import { create } from 'zustand';

import type { GraphResponse } from '@/models';
import { useNav } from '@/viewmodels/nav';
import { apiFetch } from '@/utils';

import type { GraphState } from './graph.state';

interface GraphActions {
    load: () => Promise<void>;
    select: (nodeId: string | null) => void;
    hover: (nodeId: string | null) => void;
    toggleDomain: (domain: string) => void;
    toggleSkills: () => void;
    toggleAgents: () => void;
    toggleDoors: () => void;
    enterGalaxy: (name: string) => void;
    exitToUniverse: () => void;
    resetFilters: () => void;
}

export const useGraph = create<GraphState & GraphActions>()((set, get) => ({
    graph: null,
    loading: false,
    error: null,
    selectedRef: null,
    hoveredNode: null,
    visibleDomains: null,
    showSkills: true,
    showAgents: true,
    showDoors: true,
    galaxy: null,

    load: async () => {
        set({ loading: true, error: null });
        try {
            const graph = await apiFetch<GraphResponse>('/api/graph');
            set({ graph });
        } catch (err) {
            set({ error: err instanceof Error ? err.message : 'Failed to load graph' });
        } finally {
            set({ loading: false });
        }
    },

    select: (nodeId) => {
        set({ selectedRef: nodeId });
    },

    hover: (nodeId) => {
        set({ hoveredNode: nodeId });
    },

    toggleDomain: (domain) => {
        const visible = get().visibleDomains;
        if (visible === null) {
            // Everything visible: clicking a chip focuses (solos) that domain.
            set({ visibleDomains: [domain] });
            return;
        }
        const next = visible.includes(domain)
            ? visible.filter((d) => d !== domain)
            : [...visible, domain];
        set({ visibleDomains: next.length === 0 ? null : next });
    },

    toggleSkills: () => {
        set({ showSkills: !get().showSkills });
    },

    toggleAgents: () => {
        set({ showAgents: !get().showAgents });
    },

    toggleDoors: () => {
        set({ showDoors: !get().showDoors });
    },

    enterGalaxy: (name) => {
        // Entering a galaxy reveals its section in the sidebar tree; leaving
        // collapses it again (see exitToUniverse), so the tree tracks where you
        // are through every entry path: the map disc, the pill, and back/forward.
        useNav.getState().setExpanded(`galaxy:${name}`, true);
        set({
            galaxy: name,
            selectedRef: null,
            hoveredNode: null,
            visibleDomains: null,
            showSkills: true,
            showAgents: true,
            showDoors: true,
        });
    },

    exitToUniverse: () => {
        const leaving = get().galaxy;
        if (leaving) {
            useNav.getState().setExpanded(`galaxy:${leaving}`, false);
        }
        set({ galaxy: null, selectedRef: null, hoveredNode: null });
    },

    resetFilters: () => {
        set({ visibleDomains: null, showSkills: true, showAgents: true, showDoors: true });
    },
}));
