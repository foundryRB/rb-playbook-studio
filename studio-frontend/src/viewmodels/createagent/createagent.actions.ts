import { create } from 'zustand';

import type { AgentResponse, ValidationReportResponse } from '@/models';
import { gatedSend, parseOwners } from '@/utils';

import type { CreateAgentState } from './createagent.state';

interface CreateAgentActions {
    setName: (name: string) => void;
    setTitle: (title: string) => void;
    setDescription: (description: string) => void;
    toggleRef: (refId: string) => void;
    toggleSkill: (skillId: string) => void;
    toggleDoor: (doorId: string) => void;
    setGalaxy: (galaxy: string) => void;
    setOwners: (owners: string) => void;
    setWrites: (writes: boolean) => void;
    setFreshEyes: (freshEyes: boolean) => void;
    reset: () => void;
    submit: () => Promise<AgentResponse | null>;
}

const INITIAL: CreateAgentState = {
    name: '',
    title: '',
    description: '',
    refs: [],
    skills: [],
    doors: [],
    galaxy: 'craft',
    owners: '',
    writes: false,
    freshEyes: false,
    submitting: false,
    error: null,
    report: null,
};

const toggled = (list: string[], id: string): string[] =>
    list.includes(id) ? list.filter((x) => x !== id) : [...list, id];

export const useCreateAgent = create<CreateAgentState & CreateAgentActions>()((set, get) => ({
    ...INITIAL,

    setName: (name) => {
        set({ name });
    },

    setTitle: (title) => {
        set({ title });
    },

    setDescription: (description) => {
        set({ description });
    },

    toggleRef: (refId) => {
        set({ refs: toggled(get().refs, refId) });
    },

    toggleSkill: (skillId) => {
        set({ skills: toggled(get().skills, skillId) });
    },

    toggleDoor: (doorId) => {
        set({ doors: toggled(get().doors, doorId) });
    },

    setGalaxy: (galaxy) => {
        set({ galaxy });
    },

    setOwners: (owners) => {
        set({ owners });
    },

    setWrites: (writes) => {
        set({ writes });
    },

    setFreshEyes: (freshEyes) => {
        set({ freshEyes });
    },

    reset: () => {
        set(INITIAL);
    },

    submit: async () => {
        const { name, title, description, refs, skills, doors, galaxy, writes, freshEyes, owners } =
            get();
        set({ submitting: true, error: null, report: null });
        // Posture and appearance defaults stay with bootstrap-agent: the
        // studio sends only what the author chose.
        const result = await gatedSend<AgentResponse>('/api/agents', 'POST', {
            name: name.trim(),
            title: title.trim(),
            description: description.trim(),
            refs,
            skills,
            doors,
            galaxy,
            writes,
            fresh_eyes: freshEyes,
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
