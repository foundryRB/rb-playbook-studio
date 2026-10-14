import { DOMAIN_COLORS } from '@/viewmodels/graph';

export interface DomainBadgeProps {
    domain: string;
}

export const DomainBadge = ({ domain }: DomainBadgeProps) => (
    <span
        className="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium text-white"
        style={{ backgroundColor: DOMAIN_COLORS[domain] ?? '#64748b' }}
    >
        {domain}
    </span>
);
