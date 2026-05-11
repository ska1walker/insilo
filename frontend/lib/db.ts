import { openDB, type DBSchema, type IDBPDatabase } from "idb";

export type Meeting = {
  id: string;
  title: string;
  createdAt: number;
  durationMs: number;
  mimeType: string;
  byteSize: number;
};

interface InsiloDB extends DBSchema {
  meetings: {
    key: string;
    value: Meeting;
    indexes: { "by-createdAt": number };
  };
  audio_blobs: {
    key: string;
    value: { meetingId: string; blob: Blob };
  };
}

const DB_NAME = "insilo";
const DB_VERSION = 1;

let dbPromise: Promise<IDBPDatabase<InsiloDB>> | null = null;

function getDb() {
  if (!dbPromise) {
    dbPromise = openDB<InsiloDB>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        const meetings = db.createObjectStore("meetings", { keyPath: "id" });
        meetings.createIndex("by-createdAt", "createdAt");
        db.createObjectStore("audio_blobs", { keyPath: "meetingId" });
      },
    });
  }
  return dbPromise;
}

export async function listMeetings(): Promise<Meeting[]> {
  const db = await getDb();
  const all = await db.getAllFromIndex("meetings", "by-createdAt");
  return all.reverse();
}

export async function getMeeting(id: string): Promise<Meeting | undefined> {
  const db = await getDb();
  return db.get("meetings", id);
}

export async function getMeetingAudio(id: string): Promise<Blob | undefined> {
  const db = await getDb();
  const entry = await db.get("audio_blobs", id);
  return entry?.blob;
}

export async function saveMeeting(meeting: Meeting, blob: Blob): Promise<void> {
  const db = await getDb();
  const tx = db.transaction(["meetings", "audio_blobs"], "readwrite");
  await Promise.all([
    tx.objectStore("meetings").put(meeting),
    tx.objectStore("audio_blobs").put({ meetingId: meeting.id, blob }),
    tx.done,
  ]);
}

export async function deleteMeeting(id: string): Promise<void> {
  const db = await getDb();
  const tx = db.transaction(["meetings", "audio_blobs"], "readwrite");
  await Promise.all([
    tx.objectStore("meetings").delete(id),
    tx.objectStore("audio_blobs").delete(id),
    tx.done,
  ]);
}
