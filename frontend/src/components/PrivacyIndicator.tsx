/**
 * The "Staðbundið" indicator.
 *
 * The claim is only made when the backend reports it as true. `localOnly` is
 * computed from the running configuration — bind address, CORS origins,
 * configured providers — not hardcoded, so the badge cannot say "local" about
 * an installation that is not.
 */

import { useState } from "react";

import { is } from "../i18n/is";
import type { ModelsStatusResponse, PrivacyStatusResponse } from "../lib/types";

export interface PrivacyIndicatorProps {
  privacy: PrivacyStatusResponse | null;
  models: ModelsStatusResponse | null;
}

export function PrivacyIndicator({ privacy, models }: PrivacyIndicatorProps) {
  const [open, setOpen] = useState(false);

  const verified = privacy?.localOnly === true;
  const engine = models?.correctionEngines.find((e) => e.available);
  const provider = models?.llmProviders[0];

  return (
    <div className="ritarinn-privacy">
      <button
        type="button"
        className={`ritarinn-privacy__badge${verified ? " is-local" : " is-unverified"}`}
        onClick={() => setOpen((value) => !value)}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        aria-expanded={open}
        title={verified ? is.privacy.tooltip : is.privacy.notLocalWarning}
      >
        <span className="ritarinn-privacy__dot" aria-hidden="true" />
        {verified ? is.privacy.badge : is.privacy.badgeUnverified}
      </button>

      {open && (
        <div className="ritarinn-privacy__popover" role="status">
          <p className="ritarinn-privacy__summary">
            {privacy?.summary ?? is.privacy.tooltip}
          </p>
          <dl className="ritarinn-privacy__details">
            <dt>{is.privacy.engineLabel}</dt>
            <dd>{engine ? `${engine.label}${engine.version ? ` ${engine.version}` : ""}` : "—"}</dd>

            <dt>{is.privacy.runtimeLabel}</dt>
            <dd>
              {provider?.available
                ? `${provider.label} (${provider.endpoint ?? ""})`
                : is.setup.notFound}
            </dd>

            <dt>{is.privacy.modelLabel}</dt>
            <dd>{provider?.selectedModel ?? is.setup.noModelSelected}</dd>

            <dt>{is.privacy.remoteLabel}</dt>
            <dd>
              {privacy?.remoteProviderConfigured ? "—" : is.privacy.remoteNone}
            </dd>

            <dt>{is.privacy.bindLabel}</dt>
            <dd>{privacy?.bindHost ?? "—"}</dd>

            <dt>{is.privacy.outboundLabel}</dt>
            <dd>
              {privacy && privacy.outboundEndpoints.length > 0
                ? privacy.outboundEndpoints.join(", ")
                : is.privacy.outboundNone}
            </dd>
          </dl>
        </div>
      )}
    </div>
  );
}
