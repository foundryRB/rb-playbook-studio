import { useEffect } from 'react';

import { useIdentity } from '@/viewmodels/identity';
import { useSync } from '@/viewmodels/sync';
import { cn } from '@/utils';

/**
 * Unpushed-commit count, with deliberate push and upstream refresh for an admin.
 * Renders nothing on a local run (the working tree is operator-owned).
 */
export const SyncControls = () => {
    const enabled = useSync((state) => state.enabled);
    const status = useSync((state) => state.status);
    const busy = useSync((state) => state.busy);
    const error = useSync((state) => state.error);
    const init = useSync((state) => state.init);
    const push = useSync((state) => state.push);
    const refresh = useSync((state) => state.refresh);
    const administers = useIdentity((state) => state.me?.can_administer ?? false);

    useEffect(() => {
        void init();
    }, [init]);

    if (!enabled) return null;

    const unpushed = status?.unpushed_commits ?? 0;

    return (
        <div className="flex items-center gap-2">
            {error && (
                <span className="max-w-64 truncate text-xs text-destructive" title={error}>
                    {error}
                </span>
            )}
            <span
                className={cn(
                    'rounded-full border px-2 py-0.5 text-xs',
                    unpushed > 0
                        ? 'border-link/60 text-foreground'
                        : 'border-border text-muted-foreground',
                )}
                title={status?.diff_stat || 'Nothing waiting to publish'}
            >
                {unpushed} unpushed
            </span>
            {administers && (
                <button
                    onClick={() => void refresh()}
                    disabled={busy !== null}
                    title="Pull the latest playbook content from upstream"
                    className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50"
                >
                    {busy === 'refresh' ? 'Refreshing…' : 'Refresh'}
                </button>
            )}
            {administers && (
                <button
                    onClick={() => void push()}
                    disabled={busy !== null || unpushed === 0}
                    title="Publish accumulated commits to the content repo"
                    className="rounded-md border border-link/60 px-2 py-1 text-xs font-medium text-foreground hover:bg-secondary disabled:opacity-50"
                >
                    {busy === 'push' ? 'Pushing…' : 'Push'}
                </button>
            )}
        </div>
    );
};
