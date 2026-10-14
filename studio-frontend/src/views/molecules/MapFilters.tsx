import { DOMAIN_COLORS, DOMAIN_ORDER, useGraph } from '@/viewmodels/graph';
import { cn } from '@/utils';

export interface MapFiltersProps {
    /** Restrict the legend to one galaxy's own domain vocabulary; defaults
     *  to the full palette. */
    domains?: readonly string[];
}

/** Interactive legend: click a domain to focus on it (solo), click more to
 *  widen the focus set, click an active chip to drop it. */
export const MapFilters = ({ domains }: MapFiltersProps) => {
    const visibleDomains = useGraph((state) => state.visibleDomains);
    const showSkills = useGraph((state) => state.showSkills);
    const showAgents = useGraph((state) => state.showAgents);
    const showDoors = useGraph((state) => state.showDoors);
    const toggleDomain = useGraph((state) => state.toggleDomain);
    const toggleSkills = useGraph((state) => state.toggleSkills);
    const toggleAgents = useGraph((state) => state.toggleAgents);
    const toggleDoors = useGraph((state) => state.toggleDoors);
    const resetFilters = useGraph((state) => state.resetFilters);

    const filtered = visibleDomains !== null || !showSkills || !showAgents || !showDoors;
    const shown = domains ?? DOMAIN_ORDER;

    return (
        <div className="flex flex-wrap items-center gap-1.5">
            {shown.map((domain) => {
                const activeChip = visibleDomains === null || visibleDomains.includes(domain);
                const title =
                    visibleDomains === null
                        ? `Focus on ${domain}`
                        : activeChip
                          ? `Remove ${domain} from focus`
                          : `Add ${domain} to focus`;
                return (
                    <button
                        key={domain}
                        onClick={() => toggleDomain(domain)}
                        title={title}
                        className={cn(
                            'rounded-full px-2 py-0.5 text-[11px] font-medium transition-opacity',
                            activeChip
                                ? 'text-white'
                                : 'border border-border text-muted-foreground opacity-60 hover:opacity-100',
                        )}
                        style={
                            activeChip
                                ? { backgroundColor: DOMAIN_COLORS[domain] ?? '#64748b' }
                                : undefined
                        }
                    >
                        {domain}
                    </button>
                );
            })}
            <button
                onClick={toggleSkills}
                title={showSkills ? 'Hide skills' : 'Show skills'}
                className={cn(
                    'rounded-full px-2 py-0.5 text-[11px] font-medium transition-opacity',
                    showSkills
                        ? 'bg-slate-500 text-white'
                        : 'border border-border text-muted-foreground opacity-60 hover:opacity-100',
                )}
            >
                skills
            </button>
            <button
                onClick={toggleAgents}
                title={showAgents ? 'Hide agents' : 'Show agents'}
                className={cn(
                    'rounded-full px-2 py-0.5 text-[11px] font-medium transition-opacity',
                    showAgents
                        ? 'bg-lime-600 text-white'
                        : 'border border-border text-muted-foreground opacity-60 hover:opacity-100',
                )}
            >
                agents
            </button>
            <button
                onClick={toggleDoors}
                title={showDoors ? 'Hide doors (mcps, rags)' : 'Show doors (mcps, rags)'}
                className={cn(
                    'rounded-full px-2 py-0.5 text-[11px] font-medium transition-opacity',
                    showDoors
                        ? 'bg-amber-600 text-white'
                        : 'border border-border text-muted-foreground opacity-60 hover:opacity-100',
                )}
            >
                doors
            </button>
            {filtered && (
                <button
                    onClick={resetFilters}
                    className="rounded-full border border-link/50 px-2 py-0.5 text-[11px] font-medium text-link hover:bg-primary/10"
                >
                    show all
                </button>
            )}
        </div>
    );
};
