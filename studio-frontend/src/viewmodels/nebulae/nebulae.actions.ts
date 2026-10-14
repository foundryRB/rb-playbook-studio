import { create } from 'zustand';

import type { NebulaDetailResponse, NebulaSummaryResponse } from '@/models';
import { apiFetch } from '@/utils';

import type { NebulaeState } from './nebulae.state';

interface NebulaeActions {
    load: () => Promise<void>;
    select: (territory: string) => void;
    clear: () => void;
}

/** The 3D scene waits for the roster to settle before it builds, so the
 *  roster fetch is bounded: past this, it settles to [] through the error
 *  path and the earned universe renders without the unearned zone. */
const LOAD_TIMEOUT_MS = 5000;

/** Monotonic token per detail request: only the latest select's response may
 *  land, so a slow earlier fetch never overwrites a newer selection. */
let selectToken = 0;

/** The unearned zone's viewmodel. Fed by the HTTP-only nebula endpoints;
 *  deliberately separate from the graph store, because nebulae never enter
 *  the reference graph (the quarantine, REF-Forge). */
export const useNebulae = create<NebulaeState & NebulaeActions>()((set) => ({
    nebulae: null,
    loading: false,
    error: null,
    selectedNebula: null,
    detail: null,
    detailLoading: false,
    detailError: null,

    load: async () => {
        set({ loading: true, error: null });
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), LOAD_TIMEOUT_MS);
        try {
            const nebulae = await apiFetch<NebulaSummaryResponse[]>('/api/nebulae', {
                signal: controller.signal,
            });
            set({ nebulae });
        } catch (err) {
            // Settle to an empty roster so dependent views still render.
            set({
                nebulae: [],
                error: err instanceof Error ? err.message : 'Failed to load nebulae',
            });
        } finally {
            clearTimeout(timer);
            set({ loading: false });
        }
    },

    select: (territory) => {
        const token = ++selectToken;
        set({ selectedNebula: territory, detail: null, detailLoading: true, detailError: null });
        void apiFetch<NebulaDetailResponse>(`/api/nebulae/${territory}`)
            .then((detail) => {
                if (token === selectToken) {
                    set({ detail, detailLoading: false });
                }
            })
            .catch((err) => {
                if (token === selectToken) {
                    set({
                        detailError:
                            err instanceof Error ? err.message : 'Failed to load the nebula',
                        detailLoading: false,
                    });
                }
            });
    },

    clear: () => {
        selectToken += 1;
        set({ selectedNebula: null, detail: null, detailLoading: false, detailError: null });
    },
}));
