import { useId, type ReactNode } from 'react';

interface Props {
  label: ReactNode;
  hint?: ReactNode;
  required?: boolean;
  error?: string | null;
  children: (id: string) => ReactNode;
  className?: string;
}

/** Accessible label + control wrapper. The render-prop receives a unique id for the control. */
export function Field({ label, hint, required, error, children, className }: Props) {
  const id = useId();
  return (
    <div className={`field${className ? ` ${className}` : ''}${error ? ' field--error' : ''}`}>
      <label className="field__label" htmlFor={id}>
        {label}
        {required && (
          <span className="field__req" aria-hidden="true">
            {' '}
            *
          </span>
        )}
      </label>
      {children(id)}
      {hint && <div className="field__hint">{hint}</div>}
      {error && (
        <div className="field__error" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}

export function Checkbox({
  label,
  checked,
  onChange,
  required,
  disabled,
}: {
  label: ReactNode;
  checked: boolean;
  onChange: (v: boolean) => void;
  required?: boolean;
  disabled?: boolean;
}) {
  return (
    <label className="checkbox">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        required={required}
        disabled={disabled}
      />
      <span>
        {label}
        {required && (
          <span className="field__req" aria-hidden="true">
            {' '}
            *
          </span>
        )}
      </span>
    </label>
  );
}
