import { create } from 'zustand';

import type { SkillResponse, ValidationReportResponse } from '@/models';
import { gatedSend, parseOwners } from '@/utils';

import type { CreateSkillState } from './createskill.state';

interface CreateSkillActions {
    setName: (name: string) => void;
    setDescription: (description: string) => void;
    toggleRef: (refId: string) => void;
    setGalaxy: (galaxy: string) => void;
    setOwners: (owners: string) => void;
    reset: () => void;
    submit: () => Promise<SkillResponse | null>;
}

const INITIAL: CreateSkillState = {
    name: '',
    description: '',
    refs: [],
    galaxy: 'craft',
    owners: '',
    submitting: false,
    error: null,
    report: null,
};

export const useCreateSkill = create<CreateSkillState & CreateSkillActions>()((set, get) => ({
    ...INITIAL,

    setName: (name) => {
        set({ name });
    },

    setDescription: (description) => {
        set({ description });
    },

    toggleRef: (refId) => {
        const refs = get().refs;
        set({
            refs: refs.includes(refId) ? refs.filter((r) => r !== refId) : [...refs, refId],
        });
    },

    setGalaxy: (galaxy) => {
        set({ galaxy });
    },

    setOwners: (owners) => {
        set({ owners });
    },

    reset: () => {
        set(INITIAL);
    },

    submit: async () => {
        const { name, description, refs, galaxy, owners } = get();
        set({ submitting: true, error: null, report: null });
        const result = await gatedSend<SkillResponse>('/api/skills', 'POST', {
            name: name.trim(),
            description: description.trim(),
            refs,
            galaxy,
            owners: parseOwners(owners),
        });
        set({
            submitting: false,
            error: result.error,
            report: result.report as ValidationReportResponse | null,
        });
        return result.ok;
    },
}));
