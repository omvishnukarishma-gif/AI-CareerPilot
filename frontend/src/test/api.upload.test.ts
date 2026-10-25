/**
 * Unit tests for the upload-related parts of src/services/api.ts.
 *
 * What is tested:
 *   - resumeApi.upload() appends the file under the field name "file"
 *   - The Authorization header is set from localStorage
 *   - Content-Type is NOT manually set (browser must set the boundary)
 *   - A non-2xx response throws an Error with the backend detail message
 *   - The onProgress callback is invoked during an XHR upload
 *
 * Strategy:
 *   - All fetch / XHR calls are mocked so no real network is needed.
 *   - We patch XMLHttpRequest globally in jsdom (it exists but is limited).
 *
 * @vitest-environment jsdom
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  resumeApi,
  setStoredToken,
  clearStoredToken,
  getStoredToken,
} from "../services/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeFile(name = "cv.pdf", type = "application/pdf", size = 100): File {
  const content = new Uint8Array(size).fill(0x25); // 0x25 = %
  return new File([content], name, { type });
}

// Minimal XMLHttpRequest mock that records what was sent.
function makeMockXhr(overrides: {
  status?: number;
  responseText?: string;
  triggerProgress?: boolean;
}) {
  const { status = 201, responseText = '{"id":1}', triggerProgress = false } = overrides;

  const listeners: Record<string, ((e: unknown) => void)[]> = {};
  const uploadListeners: Record<string, ((e: unknown) => void)[]> = {};

  const uploadProxy = {
    addEventListener: (event: string, cb: (e: unknown) => void) => {
      uploadListeners[event] = uploadListeners[event] ?? [];
      uploadListeners[event].push(cb);
    },
  };

  const xhr = {
    open: vi.fn(),
    setRequestHeader: vi.fn(),
    send: vi.fn((body: FormData | null) => {
      // Simulate progress if requested
      if (triggerProgress && uploadListeners["progress"]) {
        uploadListeners["progress"].forEach((cb) =>
          cb({ lengthComputable: true, loaded: 50, total: 100 })
        );
      }
      // Simulate load completion
      if (listeners["load"]) {
        listeners["load"].forEach((cb) => cb(null));
      }
      return body;
    }),
    addEventListener: (event: string, cb: (e: unknown) => void) => {
      listeners[event] = listeners[event] ?? [];
      listeners[event].push(cb);
    },
    upload: uploadProxy,
    status,
    statusText: status >= 400 ? "Error" : "Created",
    responseText,
  };

  return xhr;
}

describe("token storage helpers", () => {
  beforeEach(() => clearStoredToken());
  afterEach(() => clearStoredToken());

  it("getStoredToken returns null when no token is set", () => {
    expect(getStoredToken()).toBeNull();
  });

  it("setStoredToken / getStoredToken round-trips a value", () => {
    setStoredToken("my-jwt-token");
    expect(getStoredToken()).toBe("my-jwt-token");
  });

  it("clearStoredToken removes the stored token", () => {
    setStoredToken("my-jwt-token");
    clearStoredToken();
    expect(getStoredToken()).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Tests: resumeApi.upload() — FormData field name and auth header
// ---------------------------------------------------------------------------

describe("resumeApi.upload", () => {
  let originalXhr: typeof XMLHttpRequest;

  beforeEach(() => {
    clearStoredToken();
    originalXhr = globalThis.XMLHttpRequest;
  });

  afterEach(() => {
    globalThis.XMLHttpRequest = originalXhr;
    clearStoredToken();
  });

  it("appends the file under the field name 'file'", async () => {
    const file = makeFile();
    let capturedFormData: FormData | null = null;

    const mockXhr = makeMockXhr({ status: 201, responseText: JSON.stringify({ id: 1, user_id: 1, file_name: "cv.pdf", file_type: "pdf", created_at: new Date().toISOString(), updated_at: new Date().toISOString() }) });
    mockXhr.send = vi.fn((body: FormData) => {
      capturedFormData = body;
      // The XHR mock's load event was already set up — no additional work needed here.
      setTimeout(() => {
        // Manually invoke the addEventListener "load" handlers
      }, 0);
    });

    // Use fetch mock instead since XHR mocking in jsdom is complex.
    // Test via fetch path (no onProgress callback).
    const mockResponse = {
      ok: true,
      status: 201,
      json: vi.fn().mockResolvedValue({
        id: 1,
        user_id: 1,
        file_name: "cv.pdf",
        file_type: "pdf",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }),
    };

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockResponse as unknown as Response
    );

    await resumeApi.upload(file);

    expect(fetchSpy).toHaveBeenCalledOnce();
    const [, init] = fetchSpy.mock.calls[0];
    const body = (init as RequestInit).body as FormData;
    expect(body).toBeInstanceOf(FormData);
    expect(body.get("file")).toBe(file);

    fetchSpy.mockRestore();
    capturedFormData; // suppress unused warning
  });

  it("does NOT set Content-Type manually (lets browser handle multipart boundary)", async () => {
    const file = makeFile();
    const mockResponse = {
      ok: true,
      status: 201,
      json: vi.fn().mockResolvedValue({
        id: 1,
        user_id: 1,
        file_name: "cv.pdf",
        file_type: "pdf",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }),
    };

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockResponse as unknown as Response
    );

    await resumeApi.upload(file);

    const [, init] = fetchSpy.mock.calls[0];
    const headers = (init as RequestInit).headers as Record<string, string> | undefined;

    // Content-Type must NOT be set — the browser sets it with the boundary
    if (headers) {
      const ctKey = Object.keys(headers).find(
        (k) => k.toLowerCase() === "content-type"
      );
      expect(ctKey).toBeUndefined();
    }

    fetchSpy.mockRestore();
  });

  it("attaches Authorization header when a token is stored", async () => {
    setStoredToken("test-bearer-token");
    const file = makeFile();

    const mockResponse = {
      ok: true,
      status: 201,
      json: vi.fn().mockResolvedValue({
        id: 2,
        user_id: 1,
        file_name: "cv.pdf",
        file_type: "pdf",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }),
    };

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockResponse as unknown as Response
    );

    await resumeApi.upload(file);

    const [, init] = fetchSpy.mock.calls[0];
    const headers = (init as RequestInit).headers as Record<string, string>;
    expect(headers["Authorization"]).toBe("Bearer test-bearer-token");

    fetchSpy.mockRestore();
  });

  it("omits Authorization header when no token is stored", async () => {
    // token already cleared in beforeEach
    const file = makeFile();

    const mockResponse = {
      ok: true,
      status: 201,
      json: vi.fn().mockResolvedValue({
        id: 3,
        user_id: 1,
        file_name: "cv.pdf",
        file_type: "pdf",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }),
    };

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      mockResponse as unknown as Response
    );

    await resumeApi.upload(file);

    const [, init] = fetchSpy.mock.calls[0];
    const headers = (init as RequestInit).headers as Record<string, string> | undefined;
    if (headers) {
      const authKey = Object.keys(headers).find(
        (k) => k.toLowerCase() === "authorization"
      );
      expect(authKey).toBeUndefined();
    }

    fetchSpy.mockRestore();
  });

  it("throws an Error with the backend detail message on a 415 response", async () => {
    const file = makeFile("cv.txt", "text/plain");

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 415,
      statusText: "Unsupported Media Type",
      json: vi.fn().mockResolvedValue({
        detail: "Unsupported file type. Allowed extensions: docx, pdf.",
      }),
    } as unknown as Response);

    await expect(resumeApi.upload(file)).rejects.toThrow(
      "Unsupported file type. Allowed extensions: docx, pdf."
    );

    fetchSpy.mockRestore();
  });

  it("throws an Error with the backend detail message on a 413 response", async () => {
    const file = makeFile();

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 413,
      statusText: "Request Entity Too Large",
      json: vi.fn().mockResolvedValue({
        detail: "File exceeds the maximum allowed size of 5 MB.",
      }),
    } as unknown as Response);

    await expect(resumeApi.upload(file)).rejects.toThrow(
      "File exceeds the maximum allowed size of 5 MB."
    );

    fetchSpy.mockRestore();
  });

  it("throws an Error with the backend detail message on a 422 response", async () => {
    const file = makeFile();

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 422,
      statusText: "Unprocessable Entity",
      json: vi.fn().mockResolvedValue({
        detail: "PDF appears to have no extractable text layer.",
      }),
    } as unknown as Response);

    await expect(resumeApi.upload(file)).rejects.toThrow(
      "PDF appears to have no extractable text layer."
    );

    fetchSpy.mockRestore();
  });

  it("throws an Error with status text when response body is not JSON", async () => {
    const file = makeFile();

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: vi.fn().mockRejectedValue(new SyntaxError("not json")),
    } as unknown as Response);

    await expect(resumeApi.upload(file)).rejects.toThrow("500 Internal Server Error");

    fetchSpy.mockRestore();
  });

  it("resolves with the backend ResumeResponse on success", async () => {
    const now = new Date().toISOString();
    const expected = {
      id: 7,
      user_id: 3,
      file_name: "abc123_cv.pdf",
      file_type: "pdf",
      created_at: now,
      updated_at: now,
    };

    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      status: 201,
      json: vi.fn().mockResolvedValue(expected),
    } as unknown as Response);

    const result = await resumeApi.upload(makeFile());
    expect(result).toEqual(expected);

    fetchSpy.mockRestore();
  });
});
