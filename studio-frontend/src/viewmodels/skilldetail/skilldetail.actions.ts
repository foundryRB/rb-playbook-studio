import { create } from 'zustand';

import type { SkillFileResponse, SkillResponse, ValidationReportResponse } from '@/models';
import { apiFetch, gatedSend } from '@/utils';

import type { SkillDetailState } from './skilldetail.state';

interface SkillDetailActions {
    select: (name: string) => void;
    load: (name: string) => Promise<void>;
    openFile: (path: string) => Promise<void>;
    startEdit: () => void;
    setDraft: (draft: string) => void;
    cancelEdit: () => void;
    save: () => Promise<void>;
    install: () => Promise<void>;
}

export const useSkillDetail = create<SkillDetailState & SkillDetailActions>()((set, get) => ({
    selectedSkill: null,
    skill: null,
    loading: false,
    error: null,
    activeFile: 'SKILL.md',
    fileContent: null,
    fileLoading: false,
    editing: false,
    draft: '',
    saving: false,
    saveError: null,
    installing: false,
    lastReport: null,

    select: (name) => {
        set({ selectedSkill: name, activeFile: 'SKILL.md', fileContent: null });
    },

    load: async (name) => {
        set({ loading: true, error: null, editing: false, saveError: null });
        try {
            const skill = await apiFetch<SkillResponse>(`/api/skills/${name}`);
            set({ skill });
            if (get().activeFile !== 'SKILL.md') {
                await get().openFile(get().activeFile);
            }
        } catch (err) {
            set({ error: err instanceof Error ? err.message : 'Failed to load skill' });
        } finally {
            set({ loading: false });
        }
    },

    openFile: async (path) => {
        set({ activeFile: path, editing: false, saveError: null });
        if (path === 'SKILL.md') {
            set({ fileContent: null });
            return;
        }
        set({ fileLoading: true });
        try {
            const skill = get().skill;
            const file = await apiFetch<SkillFileResponse>(
                `/api/skills/${skill?.name}/files/${path}`,
            );
            set({ fileContent: file.content });
        } catch (err) {
            set({ error: err instanceof Error ? err.message : 'Failed to load file' });
        } finally {
            set({ fileLoading: false });
        }
    },

    startEdit: () => {
        const { activeFile, skill, fileContent } = get();
        const source = activeFile === 'SKILL.md' ? (skill?.raw ?? '') : (fileContent ?? '');
        set({ editing: true, draft: source, saveError: null });
    },

    setDraft: (draft) => {
        set({ draft });
    },

    cancelEdit: () => {
        set({ editing: false, draft: '', saveError: null });
    },

    save: async () => {
        const { skill, activeFile, draft } = get();
        if (!skill) {
            return;
        }
        set({ saving: true, saveError: null });
        const url =
            activeFile === 'SKILL.md'
                ? `/api/skills/${skill.name}`
                : `/api/skills/${skill.name}/files/${activeFile}`;
        const result = await gatedSend<ValidationReportResponse>(url, 'PUT', { raw: draft });
        set({
            saving: false,
            lastReport: (result.ok ?? result.report) as ValidationReportResponse | null,
        });
        if (result.error !== null) {
            set({ saveError: result.error });
            return;
        }
        set({ editing: false, draft: '' });
        await get().load(skill.name);
        if (activeFile !== 'SKILL.md') {
            await get().openFile(activeFile);
        }
    },

    install: async () => {
        const { skill } = get();
        if (!skill) {
            return;
        }
        set({ installing: true });
        try {
            await apiFetch(`/api/skills/${skill.name}/install`, { method: 'POST' });
            await get().load(skill.name);
        } catch (err) {
            set({ error: err instanceof Error ? err.message : 'Install failed' });
        } finally {
            set({ installing: false });
        }
    },
}));
