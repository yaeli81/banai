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

async function postJson(path, payload, fetchImpl) {
  if (!API_BASE_URL) throw new ApiError('The API base URL is not configured', { code: 'NOT_CONFIGURED' });
  let response;
  try {
    response = await fetchImpl(`${API_BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new ApiError(GENERIC_ERROR);
  }
  let body = null;
  try {
    body = await response.json();
  } catch {
    // Non-JSON error page (proxy, crash): fall through to the generic error below.
  }
  if (response.ok && body?.success === true) return body.data;
  const error = body?.error;
  throw new ApiError(typeof error?.message === 'string' ? error.message : GENERIC_ERROR, {
    status: response.status,
    code: typeof error?.code === 'string' ? error.code : 'HTTP_ERROR',
  });
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
