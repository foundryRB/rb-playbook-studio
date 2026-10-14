import type { SyncStatusResponse } from '@/models';

export interface SyncState {
    /** Whether this deployment manages the clone (from /api/health). */
    enabled: boolean | null;
    status: SyncStatusResponse | null;
    busy: 'push' | 'refresh' | null;
    error: string | null;
}
