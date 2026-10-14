import { create } from 'zustand';

import type { RefDetailResponse, ValidationReportResponse } from '@/models';

import type { CreateRefState } from './createref.state';

interface CreateRefActions {
    setField: (field: 'name' | 'domain' | 'galaxy' | 'title' | 'summary', value: string) => void;
    reset: () => void;
    submit: () => Promise<RefDetailResponse | null>;
}

interface GateRejection {
    detail?: string;
    report?: ValidationReportResponse;
}

const INITIAL: CreateRefState = {
    name: 'REF-',
    domain: 'practice',
    galaxy: 'craft',
    title: '',
    summary: '',
    submitting: false,
    error: null,
    report: null,
};

export const useCreateRef = create<CreateRefState & CreateRefActions>()((set, get) => ({
    ...INITIAL,

    setField: (field, value) => {
        set({ [field]: value } as Partial<CreateRefState>);
    },

    reset: () => {
        set(INITIAL);
    },

    submit: async () => {
        const { name, domain, galaxy, title, summary } = get();
        set({ submitting: true, error: null, report: null });
        const response = await fetch('/api/refs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name.trim(), domain, galaxy, title, summary }),
        });
        if (response.ok) {
            const ref = (await response.json()) as RefDetailResponse;
            set({ submitting: false });
            return ref;
        }
        let rejection: GateRejection = {};
        try {
            rejection = (await response.json()) as GateRejection;
        } catch {
            // Non-JSON error body; fall through to the status text.
        }
        set({
            submitting: false,
            error: rejection.detail ?? `${response.status} ${response.statusText}`,
            report: rejection.report ?? null,
        });
        return null;
    },
}));
