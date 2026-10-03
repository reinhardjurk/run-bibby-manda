import { useState } from 'react';
import { Modal } from './Modal';
import { useT } from '../i18n';

interface Props {
  title: string;
  message: React.ReactNode;
  confirmLabel?: string;
  danger?: boolean;
  /** When set, the user must type this exact text to enable the confirm button. */
  requireText?: string;
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
}

export function ConfirmDialog({ title, message, confirmLabel, danger, requireText, onConfirm, onCancel }: Props) {
  const t = useT();
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  const ok = !requireText || typed === requireText;

  const confirm = async () => {
    setBusy(true);
    try {
      await onConfirm();
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      title={title}
      onClose={onCancel}
      footer={
        <>
          <button type="button" className="btn btn--ghost" onClick={onCancel} disabled={busy}>
            {t('common.cancel')}
          </button>
          <button
            type="button"
            className={`btn ${danger ? 'btn--danger' : 'btn--primary'}`}
            onClick={confirm}
            disabled={!ok || busy}
          >
            {confirmLabel ?? t('common.yes')}
          </button>
        </>
      }
    >
      <div className="stack">
        <div>{message}</div>
        {requireText && (
          <label className="field">
            <span className="field__label">
              Zur Bestätigung <code>{requireText}</code> eingeben
            </span>
            <input value={typed} onChange={(e) => setTyped(e.target.value)} autoFocus />
          </label>
        )}
      </div>
    </Modal>
  );
}
