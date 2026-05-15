"use client";

import { Copy, KeyRound, Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { useToast } from "@/components/toast";
import {
  createApiKey,
  fetchApiKeys,
  revokeApiKey,
  type ApiKeyCreated,
  type ApiKeyRead,
} from "@/lib/api/api-keys";

/**
 * CRUD für externe API-Schlüssel. Der Roh-Token wird genau einmal
 * (in einem One-Time-Reveal-Block) angezeigt — danach lässt er sich
 * nicht rekonstruieren.
 */
export function ApiKeyManager() {
  const t = useTranslations("apiKeyManager");
  const toast = useToast();
  const [keys, setKeys] = useState<ApiKeyRead[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [justCreated, setJustCreated] = useState<ApiKeyCreated | null>(null);

  useEffect(() => {
    fetchApiKeys().then(setKeys).catch(() => setKeys([]));
  }, []);

  function refresh() {
    fetchApiKeys().then(setKeys).catch(() => {});
  }

  if (keys === null) {
    return (
      <div className="space-y-2">
        <div className="h-12 animate-pulse rounded bg-surface-soft" />
        <div className="h-12 animate-pulse rounded bg-surface-soft" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {justCreated && (
        <TokenReveal token={justCreated} onDismiss={() => setJustCreated(null)} />
      )}

      <div className="flex justify-end">
        {!adding && (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="btn-secondary inline-flex items-center gap-1.5"
          >
            <Plus className="h-3.5 w-3.5" strokeWidth={2} />
            {t("addBtn")}
          </button>
        )}
      </div>

      {adding && (
        <ApiKeyForm
          onCancel={() => setAdding(false)}
          onCreated={(k) => {
            setAdding(false);
            setJustCreated(k);
            refresh();
            toast.show({
              message: t("createdToast"),
              variant: "success",
            });
          }}
        />
      )}

      {keys.length === 0 && !adding && (
        <p className="text-sm text-text-secondary">
          {t("noneYet")}
        </p>
      )}

      {keys.length > 0 && (
        <div className="divide-y divide-border-subtle rounded-lg border border-border-subtle bg-white">
          {keys.map((k) => (
            <ApiKeyRow key={k.id} apiKey={k} onAfterRevoke={refresh} />
          ))}
        </div>
      )}
    </div>
  );
}

function ApiKeyRow({
  apiKey,
  onAfterRevoke,
}: {
  apiKey: ApiKeyRead;
  onAfterRevoke: () => void;
}) {
  const t = useTranslations("apiKeyManager");
  const toast = useToast();
  const revoked = apiKey.revoked_at != null;

  function handleRevoke() {
    if (!confirm(t("revokeConfirm", { name: apiKey.name }))) {
      return;
    }
    revokeApiKey(apiKey.id)
      .then(() => {
        toast.show({ message: t("revokedToast"), variant: "success" });
        onAfterRevoke();
      })
      .catch(() => {
        toast.show({
          message: t("revokeFailToast"),
          variant: "error",
        });
      });
  }

  return (
    <div className="flex flex-wrap items-start justify-between gap-3 px-5 py-4">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <KeyRound className="h-3.5 w-3.5 text-text-meta" strokeWidth={1.75} />
          <span className="font-medium text-text-primary">{apiKey.name}</span>
          {revoked && (
            <span className="rounded-full bg-surface-soft px-2 py-0.5 text-xs text-text-meta">
              {t("revokedTag")}
            </span>
          )}
        </div>
        <p className="mt-1 font-mono text-xs text-text-secondary">
          {apiKey.key_prefix}…
        </p>
        <p className="mt-1 text-xs text-text-meta">
          {t("createdAt", { date: formatDate(apiKey.created_at) })}
          {apiKey.last_used_at && (
            <> · {t("lastUsedAt", { date: formatDate(apiKey.last_used_at) })}</>
          )}
          {revoked && apiKey.revoked_at && (
            <> · {t("revokedAt", { date: formatDate(apiKey.revoked_at) })}</>
          )}
        </p>
        <div className="mt-1 flex flex-wrap gap-1.5">
          {apiKey.scopes.map((s) => (
            <span
              key={s}
              className="rounded-full bg-surface-soft px-2 py-0.5 text-xs text-text-secondary"
            >
              {s}
            </span>
          ))}
        </div>
      </div>

      {!revoked && (
        <button
          type="button"
          onClick={handleRevoke}
          className="btn-tertiary inline-flex items-center gap-1"
          aria-label={t("revokeAria")}
        >
          <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
          {t("revoke")}
        </button>
      )}
    </div>
  );
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ApiKeyForm({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: (k: ApiKeyCreated) => void;
}) {
  const t = useTranslations("apiKeyManager.form");
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const trimmed = name.trim();
    if (!trimmed) {
      setError(t("errEmptyName"));
      return;
    }
    setSaving(true);
    try {
      const created = await createApiKey({ name: trimmed });
      onCreated(created);
    } catch (err) {
      console.error("create api key failed", err);
      setError(t("errCreate"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 rounded-md bg-surface-soft p-4">
      <label className="block">
        <span className="block text-xs font-medium text-text-secondary">
          {t("nameLabel")}
        </span>
        <input
          autoFocus
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("namePlaceholder")}
          maxLength={120}
          className="input mt-1 w-full"
          disabled={saving}
        />
        <span className="mt-1 block text-xs text-text-meta">
          {t("nameHint")}
        </span>
      </label>

      {error && (
        <p className="text-sm" style={{ color: "var(--error)" }}>
          {error}
        </p>
      )}

      <div className="flex justify-end gap-2 border-t border-border-subtle pt-3">
        <button
          type="button"
          onClick={onCancel}
          className="btn-tertiary"
          disabled={saving}
        >
          {t("cancel")}
        </button>
        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? t("creating") : t("create")}
        </button>
      </div>
    </form>
  );
}

function TokenReveal({
  token,
  onDismiss,
}: {
  token: ApiKeyCreated;
  onDismiss: () => void;
}) {
  const t = useTranslations("apiKeyManager");
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard.writeText(token.token).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  return (
    <div
      className="rounded-lg border p-4"
      style={{
        borderColor: "var(--gold)",
        background: "rgba(201,169,97,0.08)",
      }}
    >
      <h4 className="text-sm font-medium text-text-primary">
        {t("tokenTitle", { name: token.name })}
      </h4>
      <p className="mt-1 text-xs text-text-secondary">
        {t("tokenHintBefore")}
        <code className="mx-1 rounded bg-white px-1 font-mono">Authorization</code>
        {t("tokenHintAfter")}
      </p>
      <div className="mt-3 flex items-center gap-2">
        <code className="flex-1 break-all rounded-md border border-border-subtle bg-white px-2 py-1.5 font-mono text-xs">
          {token.token}
        </code>
        <button
          type="button"
          onClick={copy}
          className="btn-secondary inline-flex items-center gap-1"
        >
          <Copy className="h-3.5 w-3.5" strokeWidth={1.75} />
          {copied ? t("copied") : t("copy")}
        </button>
      </div>
      <div className="mt-3 flex justify-end">
        <button type="button" onClick={onDismiss} className="btn-tertiary">
          {t("dismiss")}
        </button>
      </div>
    </div>
  );
}
