import { create } from 'zustand';

import type { AgentResponse, ValidationReportResponse } from '@/models';
import { apiFetch, gatedSend } from '@/utils';

import type { AgentDetailState } from './agentdetail.state';

interface AgentDetailActions {
    select: (name: string) => void;
    load: (name: string) => Promise<void>;
    startEdit: () => void;
    setDraft: (draft: string) => void;
    cancelEdit: () => void;
    save: () => Promise<void>;
}

export const useAgentDetail = create<AgentDetailState & AgentDetailActions>()((set, get) => ({
    selectedAgent: null,
    agent: null,
    loading: false,
    error: null,
    editing: false,
    draft: '',
    saving: false,
    saveError: null,
    lastReport: null,

    select: (name) => {
        set({ selectedAgent: name });
    },

    load: async (name) => {
        set({ loading: true, error: null, editing: false, saveError: null });
        try {
            const agent = await apiFetch<AgentResponse>(`/api/agents/${name}`);
            set({ agent });
        } catch (err) {
            set({ error: err instanceof Error ? err.message : 'Failed to load agent' });
        } finally {
            set({ loading: false });
        }
    },

    startEdit: () => {
        set({ editing: true, draft: get().agent?.raw ?? '', saveError: null });
    },

    setDraft: (draft) => {
        set({ draft });
    },

    cancelEdit: () => {
        set({ editing: false, draft: '', saveError: null });
    },

    save: async () => {
        const { agent, draft } = get();
        if (!agent) {
            return;
        }
        set({ saving: true, saveError: null });
        const result = await gatedSend<ValidationReportResponse>(
            `/api/agents/${agent.name}`,
            'PUT',
            { raw: draft },
        );
        set({
            saving: false,
            lastReport: (result.ok ?? result.report) as ValidationReportResponse | null,
        });
        if (result.error !== null) {
            set({ saveError: result.error });
            return;
        }
        set({ editing: false, draft: '' });
        await get().load(agent.name);
    },
}));
