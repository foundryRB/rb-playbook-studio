import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useNebulae } from './nebulae.actions';

const initial = {
    nebulae: null,
    loading: false,
    error: null,
    selectedNebula: null,
    detail: null,
    detailLoading: false,
    detailError: null,
};

const emptyDetail = (territory: string) => ({ territory, subject: '', raw: '', notes: [] });

const flush = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

describe('useNebulae.select', () => {
    const pending = new Map<string, (body: unknown) => void>();

    beforeEach(() => {
        pending.clear();
        useNebulae.setState(initial);
        vi.stubGlobal(
            'fetch',
            vi.fn(
                (url: RequestInfo | URL) =>
                    new Promise<Response>((resolve) => {
                        pending.set(String(url), (body) =>
                            resolve({ ok: true, json: async () => body } as Response),
                        );
                    }),
            ),
        );
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it('drops a stale response: only the latest selection lands', async () => {
        useNebulae.getState().select('slow-territory');
        useNebulae.getState().select('fast-territory');

        pending.get('/api/nebulae/fast-territory')!(emptyDetail('fast-territory'));
        await flush();
        expect(useNebulae.getState().detail?.territory).toBe('fast-territory');
        expect(useNebulae.getState().detailLoading).toBe(false);

        pending.get('/api/nebulae/slow-territory')!(emptyDetail('slow-territory'));
        await flush();
        expect(useNebulae.getState().detail?.territory).toBe('fast-territory');
    });

    it('ignores an in-flight response after clear', async () => {
        useNebulae.getState().select('gone-territory');
        useNebulae.getState().clear();

        pending.get('/api/nebulae/gone-territory')!(emptyDetail('gone-territory'));
        await flush();
        expect(useNebulae.getState().detail).toBeNull();
        expect(useNebulae.getState().detailLoading).toBe(false);
    });
});

describe('useNebulae.load', () => {
    beforeEach(() => {
        useNebulae.setState(initial);
    });

    afterEach(() => {
        vi.unstubAllGlobals();
        vi.useRealTimers();
    });

    it('settles a hung roster fetch to [] so dependent scenes still build', async () => {
        vi.useFakeTimers();
        vi.stubGlobal(
            'fetch',
            vi.fn(
                (_url: RequestInfo | URL, init?: RequestInit) =>
                    new Promise<Response>((_resolve, reject) => {
                        init?.signal?.addEventListener('abort', () =>
                            reject(new DOMException('The operation was aborted.', 'AbortError')),
                        );
                    }),
            ),
        );

        const settled = useNebulae.getState().load();
        await vi.advanceTimersByTimeAsync(5100);
        await settled;

        const state = useNebulae.getState();
        expect(state.nebulae).toEqual([]);
        expect(state.error).toBeTruthy();
        expect(state.loading).toBe(false);
    });

    it('settles a failed roster fetch to [] with the error kept', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn(() => Promise.reject(new Error('boom'))),
        );
        await useNebulae.getState().load();
        expect(useNebulae.getState().nebulae).toEqual([]);
        expect(useNebulae.getState().error).toBe('boom');
        expect(useNebulae.getState().loading).toBe(false);
    });
});
