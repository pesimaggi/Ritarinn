/**
 * Shown for Samantekt and Á mannamáli until Milestone 2 lands.
 *
 * The brief is explicit that unavailable functionality should be disabled and
 * documented rather than quietly routed to a hosted service. This states both
 * halves: what is missing, and what Ritarinn will not do instead.
 */

import { is } from "../i18n/is";

export interface FeaturePlaceholderProps {
  title: string;
  description: string;
}

export function FeaturePlaceholder({ title, description }: FeaturePlaceholderProps) {
  return (
    <section className="ritarinn-placeholder">
      <h2>{title}</h2>
      <p>{description}</p>
      <p className="ritarinn-placeholder__promise">{is.features.neverCloud}</p>
      <p className="ritarinn-placeholder__version">{is.features.plannedFor}</p>
    </section>
  );
}
