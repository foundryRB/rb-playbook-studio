import type { RefDetailState } from './refdetail.state';

export const selectEditableSectionCount = (state: RefDetailState): number =>
    state.ref?.sections.filter((s) => !s.generated).length ?? 0;
