import { create } from 'zustand';

import type { StandingResponse } from '@/models';
import { apiFetch } from '@/utils';

import type { IdentityState } from './identity.state';

interface IdentityActions {
    /** Ask the studio who is signed in, once. Controls render from the answer. */
    load: () => Promise<void>;
}

export const useIdentity = create<IdentityState & IdentityActions>()((set, get) => ({
    me: null,
    loaded: false,

    load: async () => {
        if (get().loaded) return;
        try {
            set({ me: await apiFetch<StandingResponse>('/api/me'), loaded: true });
        } catch {
            set({ me: null, loaded: true });
        }
    },
}));

/** Whether the signed-in person may create anything anywhere (a create entry point). */
export const selectCanCreate = (state: IdentityState): boolean =>
    (state.me?.galaxies.length ?? 0) > 0;
