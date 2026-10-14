import type { ReactNode } from 'react';

import { Lockup } from '@/components/Lockup';
import { useNav } from '@/viewmodels/nav';
import { useAppearance } from '../../vodafone/useAppearance';
import { Appearance } from '../../vodafone/Appearance';
import { AmbientField } from '@/views/atoms/AmbientField';
import { ConnectMenu } from '@/views/molecules/ConnectMenu';
import { IdentityChip } from '@/views/molecules/IdentityChip';
import { SyncControls } from '@/views/molecules/SyncControls';
import { cn } from '@/utils';

export interface MainLayoutProps {
    children: ReactNode;
}

export const MainLayout = ({ children }: MainLayoutProps) => {
    const view = useNav((state) => state.view);
    const setView = useNav((state) => state.setView);
    const { resolved: mode } = useAppearance();

    const tab = (target: 'map' | 'playbook', label: string) => (
        <button
            onClick={() => setView(target)}
            aria-current={view === target ? 'page' : undefined}
            className={cn(
                'rounded-md px-3 py-1 text-sm font-medium transition-colors',
                view === target
                    ? 'bg-secondary text-foreground'
                    : 'text-muted-foreground hover:text-foreground',
            )}
        >
            {label}
        </button>
    );

    return (
        <div className="flex min-h-screen flex-col">
            <AmbientField />
            <header className="sticky top-0 z-10 border-b border-border/70 bg-background/85 backdrop-blur">
                <div className="app-frame app-header">
                    <div className="flex items-center gap-2.5">
                        <Lockup mode={mode} height={36} />
                        <h1 className="text-sm font-medium tracking-tight">Playbook Studio</h1>
                    </div>
                    <nav aria-label="Primary navigation">
                        {tab('map', 'Map')}
                        {tab('playbook', 'Playbook')}
                    </nav>
                    <div className="ml-auto flex items-center gap-3">
                        <SyncControls />
                        <ConnectMenu />
                        <IdentityChip />
                        <Appearance />
                    </div>
                </div>
            </header>
            <main className="app-frame app-main flex-1">{children}</main>
        </div>
    );
};
