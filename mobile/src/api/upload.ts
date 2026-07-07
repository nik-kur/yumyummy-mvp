import * as FileSystem from 'expo-file-system/legacy';
import * as ImageManipulator from 'expo-image-manipulator';

import { API_BASE_URL, USE_MOCKS, getToken } from './client';
import { presignMealPhoto } from './endpoints';

/**
 * Uploads a local image to object storage via a presigned PUT URL and returns
 * the public URL to pass to `/app/agent/run` as `image_url`.
 *
 * Why this is not a simple `fetch(localUri).blob()` + PUT:
 *  - In React Native, `fetch()` of a `file://` URI followed by `.blob()` often
 *    produces an empty body, so R2 stored a 0-byte object and the vision model
 *    replied "I can't view the photo". We instead stream the real file bytes
 *    with `expo-file-system`'s native `uploadAsync` (BINARY_CONTENT).
 *  - iOS photos are frequently HEIC, which vision models reject. We normalize
 *    every photo to JPEG (and downscale it) so uploads are small and readable.
 *
 * Throws on failure so callers can surface a clear error instead of silently
 * logging a 0-kcal meal.
 */
export async function uploadMealPhoto(localUri: string): Promise<string> {
  // 1) Normalize to a downscaled JPEG (HEIC-safe, faster upload).
  let uploadUri = localUri;
  try {
    const out = await ImageManipulator.manipulateAsync(
      localUri,
      [{ resize: { width: 1280 } }],
      { compress: 0.7, format: ImageManipulator.SaveFormat.JPEG },
    );
    if (out?.uri) uploadUri = out.uri;
  } catch {
    // Fall back to the original file if manipulation isn't available.
  }

  // 2) Ask the backend for a short-lived presigned PUT URL.
  const presign = await presignMealPhoto('image/jpeg', 'jpg');
  if (USE_MOCKS) return presign.public_url ?? 'https://example.com/mock-meal.jpg';

  // 3) Stream the actual bytes to storage (native binary PUT).
  const res = await FileSystem.uploadAsync(presign.upload_url, uploadUri, {
    httpMethod: 'PUT',
    uploadType: FileSystem.FileSystemUploadType.BINARY_CONTENT,
    headers: { 'Content-Type': 'image/jpeg' },
  });

  if (res.status < 200 || res.status >= 300) {
    throw new Error(`Photo upload failed (HTTP ${res.status}).`);
  }
  if (!presign.public_url) {
    throw new Error('Photo storage is missing a public URL. Contact support.');
  }
  return presign.public_url;
}

async function uploadForTranscript(
  path: string,
  localUri: string,
  headers?: Record<string, string>,
): Promise<{ status: number; body: string }> {
  const res = await FileSystem.uploadAsync(`${API_BASE_URL}${path}`, localUri, {
    httpMethod: 'POST',
    uploadType: FileSystem.FileSystemUploadType.MULTIPART,
    fieldName: 'audio',
    mimeType: 'audio/m4a',
    headers,
  });
  return { status: res.status, body: res.body };
}

/**
 * Sends a recorded voice note to the backend's Whisper STT and returns the
 * transcript. We upload the real file bytes as multipart (the same reason as
 * photos — a `fetch().blob()` of a `file://` URI is unreliable in RN). The
 * caller drops the transcript into the composer so the user can review/edit it
 * before the normal source-checked `/app/agent/run` logging runs.
 *
 * Prefers the fast, JWT-scoped `/app/voice/transcribe` (STT only) and falls
 * back to the public `/ai/voice_parse_meal` if that isn't deployed yet — both
 * return `{ transcript }`.
 */
export async function transcribeAudio(localUri: string): Promise<string> {
  if (USE_MOCKS) return 'grilled chicken with rice and salad';

  const token = await getToken();
  const authHeaders = token ? { Authorization: `Bearer ${token}` } : undefined;

  let res = await uploadForTranscript('/app/voice/transcribe', localUri, authHeaders);
  if (res.status === 404 || res.status === 405) {
    res = await uploadForTranscript('/ai/voice_parse_meal', localUri);
  }

  if (res.status < 200 || res.status >= 300) {
    throw new Error(`Couldn’t transcribe that (HTTP ${res.status}).`);
  }
  try {
    const data = JSON.parse(res.body) as { transcript?: string };
    return (data.transcript ?? '').trim();
  } catch {
    throw new Error('Couldn’t read the transcription response.');
  }
}
