import { useEffect } from 'react';

export function useDocumentTitle(title: string | null | undefined) {
  useEffect(() => {
    const prev = document.title;
    document.title = title ? `${title} · Bibby` : 'Bibby';
    return () => {
      document.title = prev;
    };
  }, [title]);
}
