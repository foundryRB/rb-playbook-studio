import { create } from 'zustand';

import type { HealthResponse, SyncStatusResponse } from '@/models';
import { apiFetch } from '@/utils';

import type { SyncState } from './sync.state';

interface SyncActions {
    /** Discover the capability once, then load the status when enabled. */
    init: () => Promise<void>;
    loadStatus: () => Promise<void>;
    push: () => Promise<void>;
    refresh: () => Promise<void>;
}

export const useSync = create<SyncState & SyncActions>()((set, get) => ({
    enabled: null,
    status: null,
    busy: null,
    error: null,

    init: async () => {
        if (get().enabled !== null) return;
        try {
            const health = await apiFetch<HealthResponse>('/api/health');
            set({ enabled: health.sync });
            if (health.sync) await get().loadStatus();
        } catch {
            set({ enabled: false });
        }
    },

    loadStatus: async () => {
        try {
            const status = await apiFetch<SyncStatusResponse>('/api/sync/status');
            set({ status, error: null });
        } catch (err) {
            set({ error: err instanceof Error ? err.message : 'Failed to load sync status' });
        }
    },

    push: async () => {
        set({ busy: 'push', error: null });
        try {
            const status = await apiFetch<SyncStatusResponse>('/api/sync/push', {
                method: 'POST',
            });
            set({ status });
        } catch (err) {
            set({ error: err instanceof Error ? err.message : 'Push failed' });
        } finally {
            set({ busy: null });
        }
    },

    refresh: async () => {
        set({ busy: 'refresh', error: null });
        try {
            const status = await apiFetch<SyncStatusResponse>('/api/sync/refresh', {
                method: 'POST',
            });
            set({ status });
        } catch (err) {
            set({ error: err instanceof Error ? err.message : 'Refresh failed' });
        } finally {
            set({ busy: null });
        }
    },
}));
