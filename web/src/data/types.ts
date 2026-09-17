import type { CalendarContext, Meeting } from "../api/types";

export interface StaticManifest {
  schema_version: number;
  academic_year: string;
  semester: string;
  first_supported_date: string;
  last_supported_date: string;
  supported_dates: string[];
}

export interface StaticRoom {
  id: string; name: string; location_id?: string; location_name?: string;
  class_types?: string[]; capacity?: number; bookable_by_staff?: boolean; bookable_by_student_orgs?: boolean;
}
export interface StaticRooms { schema_version: number; rooms: StaticRoom[] }
export interface StaticLocation { id: string; name: string; official_name: string | null; short_name: string; aliases: string[]; room_count: number; rooms: string[] }
export interface StaticLocations { schema_version: number; locations: StaticLocation[] }
export type OccupiedBlock = [number, number, number[]];
export type UncertainBlock = [number, number, string[], string[]];
export interface StaticDayRoom { status: string; reason: string; schedule: Meeting[]; occupied_blocks: OccupiedBlock[]; uncertain_blocks: UncertainBlock[] }
export interface StaticDay {
  schema_version: number; date: string; status: string; reason: string; reason_code: string;
  calendar: CalendarContext; rooms: Record<string, StaticDayRoom>; unparsed_rooms: string[];
}
