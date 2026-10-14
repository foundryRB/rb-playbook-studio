import { create } from 'zustand';

import type { RefDetailResponse, ValidationReportResponse } from '@/models';
import { apiFetch } from '@/utils';

import type { RefDetailState } from './refdetail.state';

interface RefDetailActions {
    load: (name: string) => Promise<void>;
    clear: () => void;
    startEdit: (sectionNumber: number, body: string) => void;
    startDocEdit: () => void;
    setDraft: (draft: string) => void;
    cancelEdit: () => void;
    save: () => Promise<void>;
}

interface GateRejection {
    detail?: string;
    report?: ValidationReportResponse;
}

/** PUT that surfaces the validation report carried by a 422 rejection. */
async function gatedPut(
    url: string,
    payload: object,
): Promise<{ report: ValidationReportResponse | null; error: string | null }> {
    const response = await fetch(url, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (response.ok) {
        return { report: (await response.json()) as ValidationReportResponse, error: null };
    }
    let rejection: GateRejection = {};
    try {
        rejection = (await response.json()) as GateRejection;
    } catch {
        // Non-JSON error body; fall through to the status text.
    }
    return {
        report: rejection.report ?? null,
        error: rejection.detail ?? `${response.status} ${response.statusText}`,
    };
}

export const useRefDetail = create<RefDetailState & RefDetailActions>()((set, get) => ({
    ref: null,
    loading: false,
    error: null,
    editingSection: null,
    editingDoc: false,
    draft: '',
    saving: false,
    saveError: null,
    lastReport: null,

    load: async (name) => {
        set({
            loading: true,
            error: null,
            editingSection: null,
            editingDoc: false,
            saveError: null,
        });
        try {
            const ref = await apiFetch<RefDetailResponse>(`/api/refs/${name}`);
            set({ ref });
        } catch (err) {
            set({ error: err instanceof Error ? err.message : 'Failed to load REF' });
        } finally {
            set({ loading: false });
        }
    },

    clear: () => {
        set({
            ref: null,
            editingSection: null,
            editingDoc: false,
            saveError: null,
            lastReport: null,
        });
    },

    startEdit: (sectionNumber, body) => {
        set({ editingSection: sectionNumber, editingDoc: false, draft: body, saveError: null });
    },

    startDocEdit: () => {
        const raw = get().ref?.raw ?? '';
        set({ editingDoc: true, editingSection: null, draft: raw, saveError: null });
    },

    setDraft: (draft) => {
        set({ draft });
    },

    cancelEdit: () => {
        set({ editingSection: null, editingDoc: false, draft: '', saveError: null });
    },

    save: async () => {
        const { ref, editingSection, editingDoc, draft } = get();
        if (ref === null || (editingSection === null && !editingDoc)) {
            return;
        }
        set({ saving: true, saveError: null });
        const { report, error } = editingDoc
            ? await gatedPut(`/api/refs/${ref.name}`, { raw: draft })
            : await gatedPut(`/api/refs/${ref.name}/sections/${editingSection}`, { body: draft });
        set({ lastReport: report, saving: false });
        if (error !== null) {
            set({ saveError: error });
            return;
        }
        set({ editingSection: null, editingDoc: false, draft: '' });
        await get().load(ref.name);
    },
}));
