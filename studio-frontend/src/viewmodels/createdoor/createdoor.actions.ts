import { create } from 'zustand';

import type { DoorResponse, ValidationReportResponse } from '@/models';
import { gatedSend, parseOwners } from '@/utils';

import type { CardKind, CreateDoorState } from './createdoor.state';

interface CreateDoorActions {
    setKind: (kind: CardKind) => void;
    setName: (name: string) => void;
    setGalaxy: (galaxy: string) => void;
    setRaw: (raw: string) => void;
    setOwners: (owners: string) => void;
    reset: () => void;
    submit: () => Promise<DoorResponse | null>;
}

const INITIAL: CreateDoorState = {
    kind: 'mcp',
    name: '',
    galaxy: 'craft',
    raw: '',
    owners: '',
    submitting: false,
    error: null,
    report: null,
};

/** The card's opening lines for a name and galaxy: the frontmatter every card
 *  carries and its heading, for the author to fill with purpose and doctrine. */
export const cardOpening = (kind: CardKind, name: string, galaxy: string): string =>
    [
        '---',
        `name: ${name || '<name>'}`,
        `galaxy: ${galaxy}`,
        'refs:',
        '  - <home REF>',
        '---',
        '',
        `# ${kind.toUpperCase()}: ${name || '<name>'}`,
        '',
        '> When to knock here, in one line.',
        '',
    ].join('\n');

export const useCreateDoor = create<CreateDoorState & CreateDoorActions>()((set, get) => ({
    ...INITIAL,

    setKind: (kind) => {
        set({ kind });
    },

    setName: (name) => {
        set({ name });
    },

    setGalaxy: (galaxy) => {
        set({ galaxy });
    },

    setRaw: (raw) => {
        set({ raw });
    },

    setOwners: (owners) => {
        set({ owners });
    },

    reset: () => {
        set(INITIAL);
    },

    submit: async () => {
        const { kind, name, galaxy, raw, owners } = get();
        set({ submitting: true, error: null, report: null });
        const result = await gatedSend<DoorResponse>('/api/doors', 'POST', {
            kind,
            name: name.trim(),
            galaxy,
            raw,
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
