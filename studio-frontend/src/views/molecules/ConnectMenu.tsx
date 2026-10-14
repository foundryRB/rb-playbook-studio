import { useEffect, useState } from 'react';

import { useIdentity } from '@/viewmodels/identity';
import { useSync } from '@/viewmodels/sync';
import { ConnectAgent } from '@/views/molecules/ConnectAgent';

/**
 * Header entry point for the MCP door: visible on the deployed studio to everyone
 * signed in, so their own connect one-liner is one click away.
 */
export const ConnectMenu = () => {
    const deployed = useSync((state) => state.enabled);
    const init = useSync((state) => state.init);
    const me = useIdentity((state) => state.me);
    const [open, setOpen] = useState(false);

    useEffect(() => {
        void init();
    }, [init]);

    if (!deployed || !me) return null;

    return (
        <div className="relative">
            <button
                onClick={() => setOpen((value) => !value)}
                title="Connect an MCP agent to this studio"
                className="rounded-md border border-link/60 px-2 py-1 text-xs font-medium text-foreground hover:bg-secondary"
            >
                {open ? 'Close' : 'Connect agent'}
            </button>
            {open && (
                <div className="absolute right-0 top-9 z-20 w-96 rounded-lg border bg-card p-3 shadow-lg">
                    <p className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                        MCP
                    </p>
                    <ConnectAgent />
                </div>
            )}
        </div>
    );
};
