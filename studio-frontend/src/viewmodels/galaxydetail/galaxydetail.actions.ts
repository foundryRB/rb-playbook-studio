import { create } from 'zustand';

import type { GalaxyResponse } from '@/models';
import { apiFetch } from '@/utils';

import type { GalaxyDetailState } from './galaxydetail.state';

interface GalaxyDetailActions {
    select: (name: string) => void;
    clear: () => void;
}

export const useGalaxyDetail = create<GalaxyDetailState & GalaxyDetailActions>()((set) => ({
    selectedGalaxy: null,
    galaxyDoc: null,
    loading: false,
    error: null,

    select: (name) => {
        set({ selectedGalaxy: name, galaxyDoc: null, loading: true, error: null });
        void apiFetch<GalaxyResponse>(`/api/galaxies/${name}`)
            .then((galaxyDoc) => set({ galaxyDoc, loading: false }))
            .catch((err) =>
                set({
                    error: err instanceof Error ? err.message : 'Failed to load the galaxy',
                    loading: false,
                }),
            );
    },

    clear: () => {
        set({ selectedGalaxy: null, galaxyDoc: null, error: null });
    },
}));
