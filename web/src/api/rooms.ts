import { findFreeRooms, getRoomAvailability, getRoomSchedule, searchRooms } from "../data/repository";

export interface AvailabilityQuery {
  date: string;
  time: string;
  duration: number;
}

export { findFreeRooms, getRoomAvailability, getRoomSchedule, searchRooms };
