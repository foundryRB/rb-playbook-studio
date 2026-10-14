import { create } from 'zustand';

import type { DoorResponse, ValidationReportResponse } from '@/models';
import { apiFetch, gatedSend } from '@/utils';

import type { DoorDetailState } from './doordetail.state';

interface DoorDetailActions {
    select: (name: string) => void;
    clear: () => void;
    startEdit: () => void;
    setDraft: (draft: string) => void;
    cancelEdit: () => void;
    save: () => Promise<void>;
}

const load = (name: string): Promise<DoorResponse> => apiFetch<DoorResponse>(`/api/doors/${name}`);

export const useDoorDetail = create<DoorDetailState & DoorDetailActions>()((set, get) => ({
    selectedDoor: null,
    door: null,
    loading: false,
    error: null,
    editing: false,
    draft: '',
    saving: false,
    saveError: null,
    lastReport: null,

    select: (name) => {
        set({
            selectedDoor: name,
            door: null,
            loading: true,
            error: null,
            editing: false,
            saveError: null,
            lastReport: null,
        });
        void load(name)
            .then((door) => set({ door, loading: false }))
            .catch((err) =>
                set({
                    error: err instanceof Error ? err.message : 'Failed to load the door',
                    loading: false,
                }),
            );
    },

    clear: () => {
        set({ selectedDoor: null, door: null, error: null, editing: false });
    },

    startEdit: () => {
        set({ editing: true, draft: get().door?.raw ?? '', saveError: null });
    },

    setDraft: (draft) => {
        set({ draft });
    },

    cancelEdit: () => {
        set({ editing: false, draft: '', saveError: null });
    },

    save: async () => {
        const { door, draft } = get();
        if (!door) {
            return;
        }
        set({ saving: true, saveError: null });
        const result = await gatedSend<ValidationReportResponse>(`/api/doors/${door.name}`, 'PUT', {
            raw: draft,
        });
        set({
            saving: false,
            lastReport: (result.ok ?? result.report) as ValidationReportResponse | null,
        });
        if (result.error !== null) {
            set({ saveError: result.error });
            return;
        }
        set({ editing: false, draft: '', door: await load(door.name) });
    },
}));
