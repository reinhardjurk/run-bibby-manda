import { createContext, useContext } from 'react';
import type { EventOut, MeResponse } from '../../api/types';

export interface TeamContextValue {
  slug: string;
  me: MeResponse;
  events: EventOut[];
  eventsLoading: boolean;
  reloadEvents: () => void;
  selectedEventId: string;
  setSelectedEventId: (id: string) => void;
  selectedEvent: EventOut | null;
  logout: () => Promise<void>;
}

export const TeamContext = createContext<TeamContextValue | null>(null);

export function useTeam(): TeamContextValue {
  const ctx = useContext(TeamContext);
  if (!ctx) throw new Error('useTeam must be used inside <TeamLayout>');
  return ctx;
}
