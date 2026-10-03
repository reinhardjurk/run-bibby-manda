interface Props {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}

export function Pagination({ page, pageSize, total, onChange }: Props) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages <= 1) return <div className="pagination muted">{total} Einträge</div>;
  return (
    <div className="pagination">
      <span className="muted">
        {total} Einträge · Seite {page} / {pages}
      </span>
      <button type="button" className="btn btn--small" onClick={() => onChange(page - 1)} disabled={page <= 1}>
        ‹
      </button>
      <button type="button" className="btn btn--small" onClick={() => onChange(page + 1)} disabled={page >= pages}>
        ›
      </button>
    </div>
  );
}
