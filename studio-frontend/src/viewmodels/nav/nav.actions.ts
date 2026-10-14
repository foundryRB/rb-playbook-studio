import { create } from 'zustand';

import type { NavState, StudioView } from './nav.state';

interface NavActions {
    setView: (view: StudioView) => void;
    toggleExpanded: (key: string) => void;
    setExpanded: (key: string, open: boolean) => void;
}

export const useNav = create<NavState & NavActions>()((set) => ({
    view: 'map',
    expanded: {},

    setView: (view) => {
        set({ view });
    },

    toggleExpanded: (key) => {
        set((state) => ({ expanded: { ...state.expanded, [key]: !state.expanded[key] } }));
    },

    setExpanded: (key, open) => {
        set((state) => ({ expanded: { ...state.expanded, [key]: open } }));
    },
}));
