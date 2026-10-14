import type { StandingResponse } from '@/models';

export interface IdentityState {
    /** Who this browser acts as and what OWNERS lets them do; null when nobody is
     *  signed in (or before the first load), which renders no write control. */
    me: StandingResponse | null;
    loaded: boolean;
}
