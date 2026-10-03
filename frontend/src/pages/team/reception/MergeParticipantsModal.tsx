import { useState } from 'react';
import { errorMessage } from '../../../api/client';
import { registrationsApi } from '../../../api/team';
import { ErrorBox, Notice } from '../../../components/ErrorBox';
import { Field } from '../../../components/Field';
import { Modal } from '../../../components/Modal';
import { useToast } from '../../../hooks/useToast';
import { useT } from '../../../i18n';

export interface MergeSelection {
  source?: { id: string; label: string };
  target?: { id: string; label: string };
}

interface Props {
  slug: string;
  selection: MergeSelection;
  onClose: () => void;
  onMerged: () => void;
}

/** Merges two participant records (dublettes): all registrations of the source move to the target. */
export function MergeParticipantsModal({ slug, selection, onClose, onMerged }: Props) {
  const t = useT();
  const toast = useToast();
  const [source, setSource] = useState(selection.source?.id ?? '');
  const [target, setTarget] = useState(selection.target?.id ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const merge = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await registrationsApi.merge(slug, source.trim(), target.trim());
      toast.success(`Zusammengeführt – ${res.moved} Anmeldung(en) verschoben.`);
      onMerged();
      onClose();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      title="Teilnehmer zusammenführen"
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn btn--ghost" onClick={onClose} disabled={busy}>
            {t('common.cancel')}
          </button>
          <button type="button" className="btn btn--danger" onClick={merge} disabled={busy || !source.trim() || !target.trim()}>
            Zusammenführen
          </button>
        </>
      }
    >
      <div className="stack">
        <Notice kind="info">
          Alle Anmeldungen der <strong>Quelle</strong> werden dem <strong>Ziel</strong> zugeordnet; die Quelle wird
          gelöscht. Teilnehmer-IDs finden Sie in der Detailansicht einer Anmeldung (Buttons „Merge-Quelle“ /
          „Merge-Ziel“).
        </Notice>
        <Field label="Quelle (Teilnehmer-ID)" hint={selection.source?.label}>
          {(id) => <input id={id} value={source} onChange={(e) => setSource(e.target.value)} className="mono" />}
        </Field>
        <Field label="Ziel (Teilnehmer-ID)" hint={selection.target?.label}>
          {(id) => <input id={id} value={target} onChange={(e) => setTarget(e.target.value)} className="mono" />}
        </Field>
        <ErrorBox message={error} />
      </div>
    </Modal>
  );
}
