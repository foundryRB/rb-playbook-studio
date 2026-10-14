import { create } from 'zustand';

import type { IntentClaimResponse, ValidationReportResponse } from '@/models';
import { apiFetch } from '@/utils';

import type { ClaimsState } from './claims.state';

interface ClaimsActions {
    load: () => Promise<void>;
    validate: () => Promise<void>;
}

export const useClaims = create<ClaimsState & ClaimsActions>()((set) => ({
    claims: [],
    loading: false,
    error: null,
    validating: false,
    report: null,

    load: async () => {
        set({ loading: true, error: null });
        try {
            const claims = await apiFetch<IntentClaimResponse[]>('/api/claims');
            set({ claims });
        } catch (err) {
            set({ error: err instanceof Error ? err.message : 'Failed to load claims' });
        } finally {
            set({ loading: false });
        }
    },

    validate: async () => {
        set({ validating: true, error: null });
        try {
            const report = await apiFetch<ValidationReportResponse>('/api/validate', {
                method: 'POST',
            });
            set({ report });
        } catch (err) {
            set({ error: err instanceof Error ? err.message : 'Validation run failed' });
        } finally {
            set({ validating: false });
        }
    },
}));
