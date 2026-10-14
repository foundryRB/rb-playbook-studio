import type { ClaimsState } from './claims.state';

export const selectCriticalClaimCount = (state: ClaimsState): number =>
    state.claims.filter((c) => c.criticality === 'critical').length;
