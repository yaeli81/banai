import { API_BASE_URL } from '../config.js';

/** An API failure. `code` is the server's error code (e.g. 'STALE'), or a client-side one. */
export class ApiError extends Error {
  constructor(message, { status = 0, code = 'NETWORK_ERROR' } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

async function getJson(path, fetchImpl) {
  if (!API_BASE_URL) throw new Error('The API base URL is not configured');
  const response = await fetchImpl(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Request to ${path} failed with status ${response.status}`);
  }
  const body = await response.json();
  if (!body || body.success !== true) {
    throw new Error(`Request to ${path} returned an unsuccessful response`);
  }
  return body.data;
}

const GENERIC_ERROR = 'The design service could not be reached. Please try again.';

async function post(path, init, fetchImpl) {
  if (!API_BASE_URL) throw new ApiError('The API base URL is not configured', { code: 'NOT_CONFIGURED' });
  try {
    return await fetchImpl(`${API_BASE_URL}${path}`, { method: 'POST', ...init });
  } catch {
    throw new ApiError(GENERIC_ERROR);
  }
}

const toApiError = (status, body) => new ApiError(
  typeof body?.error?.message === 'string' ? body.error.message : GENERIC_ERROR,
  { status, code: typeof body?.error?.code === 'string' ? body.error.code : 'HTTP_ERROR' },
);

// Non-JSON bodies (proxy error pages, crashes) read as null and map to the generic error.
const readJson = (response) => response.json().catch(() => null);

/** Throws the server's envelope error (or a generic one) for a failed response. */
async function throwFor(response) {
  throw toApiError(response.status, await readJson(response));
}

async function postJson(path, payload, fetchImpl) {
  const response = await post(path, { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }, fetchImpl);
  const body = await readJson(response);
  if (response.ok && body?.success === true) return body.data;
  throw toApiError(response.status, body);
}

export const getHealth = (fetchImpl = fetch) => getJson('/api/health', fetchImpl).then((data) => ({ success: true, data }));

export const getCatalog = (fetchImpl = fetch) => getJson('/api/catalog', fetchImpl);

/** Returns { design, revision } for the predefined basic wardrobe. */
export const getDefaultDesign = (fetchImpl = fetch) => getJson('/api/designs/default', fetchImpl);

/** One agent turn. Returns { reply, proposal | null }; never changes the design. */
export const sendChat = ({ messages, design, revision }, fetchImpl = fetch) =>
  postJson('/api/chat', { messages, design, revision }, fetchImpl);

/** Apply a signed proposal. Returns { design, revision }; throws ApiError code 'STALE' (409) when outdated. */
export const applyProposal = ({ design, revision, proposal }, fetchImpl = fetch) =>
  postJson('/api/proposals/apply', { design, revision, proposal }, fetchImpl);

/** Recorded audio -> text. The text is then sent to the agent like a typed message. */
export async function transcribeAudio(blob, fetchImpl = fetch) {
  // "audio/webm;codecs=opus" -> "audio/webm" (the server allowlists base types).
  const type = (blob.type || 'audio/webm').split(';', 1)[0];
  const response = await post('/api/voice/transcribe', { headers: { 'Content-Type': type }, body: blob }, fetchImpl);
  if (!response.ok) await throwFor(response);
  const body = await response.json();
  if (body?.success !== true || typeof body.data?.text !== 'string') throw new ApiError(GENERIC_ERROR, { code: 'HTTP_ERROR' });
  return body.data.text;
}

/** The carpenter spec sheet (PDF Blob) for a design and its two 3D images (PNG data URLs). */
export async function downloadCarpenterPdf({ design, images }, fetchImpl = fetch) {
  const response = await post('/api/carpenter/pdf', {
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ design, images }),
  }, fetchImpl);
  if (!response.ok) await throwFor(response);
  return response.blob();
}

/** A short reply -> audio Blob to play. */
export async function speakText(text, fetchImpl = fetch) {
  const response = await post('/api/voice/speech', {
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }),
  }, fetchImpl);
  if (!response.ok) await throwFor(response);
  return response.blob();
}
