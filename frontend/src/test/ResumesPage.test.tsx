/**
 * Component tests for ResumesPage.
 *
 * What is tested:
 *   - Loading state while the resume list is being fetched
 *   - Error state when the list fetch fails
 *   - Empty state when the server returns an empty array
 *   - Success state showing the resume table
 *   - Upload button is enabled when idle and disabled while uploading
 *   - Client-side validation: wrong extension shows an error banner
 *   - Client-side validation: oversized file shows an error banner
 *   - Successful upload shows a success banner and refreshes the list
 *   - Failed upload shows an error banner
 *   - Banners can be dismissed
 *
 * Strategy:
 *   - resumeApi is mocked at the module level.
 *   - AuthContext is mocked via a lightweight wrapper so the page can
 *     call useAuth() without a real provider.
 *   - File selection is simulated by setting the files property and firing
 *     a change event on the hidden input (userEvent.upload does not work on
 *     aria-hidden inputs).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

// ---------------------------------------------------------------------------
// Mock the api module before importing the component
// ---------------------------------------------------------------------------

vi.mock("../services/api", () => ({
  resumeApi: {
    list: vi.fn(),
    upload: vi.fn(),
  },
}));

// ---------------------------------------------------------------------------
// Mock AuthContext so useAuth() works without a real provider
// ---------------------------------------------------------------------------

vi.mock("../contexts/AuthContext", () => ({
  useAuth: () => ({
    user: { id: 1, email: "test@example.com", full_name: "Test User", is_active: true },
    isLoading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}));

// ---------------------------------------------------------------------------
// Import after mocks are registered
// ---------------------------------------------------------------------------

import { ResumesPage } from "../pages/ResumesPage";
import { resumeApi } from "../services/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mockedList = vi.mocked(resumeApi.list);
const mockedUpload = vi.mocked(resumeApi.upload);

function renderPage() {
  return render(
    <MemoryRouter>
      <ResumesPage />
    </MemoryRouter>
  );
}

function makeResumeResponse(overrides = {}) {
  const now = new Date().toISOString();
  return {
    id: 1,
    user_id: 1,
    file_name: "abc123_cv.pdf",
    file_type: "pdf",
    created_at: now,
    updated_at: now,
    ...overrides,
  };
}

function makePdfFile(name = "cv.pdf", size = 1024) {
  const content = new Uint8Array(size);
  content[0] = 0x25; // %PDF magic bytes
  content[1] = 0x50;
  content[2] = 0x44;
  content[3] = 0x46;
  return new File([content], name, { type: "application/pdf" });
}

/**
 * Simulate selecting a file on the hidden file input.
 *
 * userEvent.upload() requires the element to be pointer-accessible.
 * Our input is aria-hidden (programmatically opened), so we fire the
 * change event directly using fireEvent.
 */
function selectFile(file: File) {
  const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement;
  Object.defineProperty(fileInput, "files", {
    value: Object.assign([file], { item: (i: number) => [file][i] }),
    writable: false,
    configurable: true,
  });
  fireEvent.change(fileInput);
}

// ---------------------------------------------------------------------------
// Tests: list state rendering
// ---------------------------------------------------------------------------

describe("ResumesPage — resume list", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a loading spinner while fetching resumes", () => {
    mockedList.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByRole("status", { name: /loading resumes/i })).toBeInTheDocument();
  });

  it("shows an error message when list fetch fails", async () => {
    mockedList.mockRejectedValue(new Error("Network error"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.getByText(/network error/i)).toBeInTheDocument();
  });

  it("shows empty state when there are no resumes", async () => {
    mockedList.mockResolvedValue([]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/no resumes yet/i)).toBeInTheDocument();
    });
  });

  it("renders a table row for each resume", async () => {
    mockedList.mockResolvedValue([
      makeResumeResponse({ id: 1, file_name: "abc123_cv.pdf", file_type: "pdf" }),
      makeResumeResponse({ id: 2, file_name: "xyz789_resume.docx", file_type: "docx" }),
    ]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("abc123_cv.pdf")).toBeInTheDocument();
      expect(screen.getByText("xyz789_resume.docx")).toBeInTheDocument();
    });
  });

  it("shows a PDF badge for a PDF resume", async () => {
    mockedList.mockResolvedValue([makeResumeResponse({ file_type: "pdf" })]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("PDF")).toBeInTheDocument();
    });
  });

  it("shows a DOCX badge for a DOCX resume", async () => {
    mockedList.mockResolvedValue([
      makeResumeResponse({ file_name: "cv.docx", file_type: "docx" }),
    ]);
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("DOCX")).toBeInTheDocument();
    });
  });

  it("retry button refreshes the list after an error", async () => {
    mockedList
      .mockRejectedValueOnce(new Error("Temporary error"))
      .mockResolvedValueOnce([makeResumeResponse()]);

    renderPage();
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: /retry/i }));
    await waitFor(() => {
      expect(screen.getByText("abc123_cv.pdf")).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Tests: upload button state
// ---------------------------------------------------------------------------

describe("ResumesPage — upload button", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedList.mockResolvedValue([]);
  });

  it("renders an enabled Upload resume button by default", async () => {
    renderPage();
    await waitFor(() => screen.getByText(/no resumes yet/i));
    const btn = screen.getByRole("button", { name: /upload resume/i });
    expect(btn).not.toBeDisabled();
  });

  it("disables the upload button while uploading", async () => {
    mockedUpload.mockReturnValue(new Promise(() => {}));

    renderPage();
    await waitFor(() => screen.getByText(/no resumes yet/i));

    const btn = screen.getByRole("button", { name: /upload resume/i });
    selectFile(makePdfFile());

    await waitFor(() => {
      expect(btn).toBeDisabled();
    });
  });
});

// ---------------------------------------------------------------------------
// Tests: client-side validation
// ---------------------------------------------------------------------------

describe("ResumesPage — client-side file validation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedList.mockResolvedValue([]);
  });

  it("shows an error banner when a .txt file is selected", async () => {
    renderPage();
    await waitFor(() => screen.getByText(/no resumes yet/i));

    const txtFile = new File(["text content"], "notes.txt", { type: "text/plain" });
    selectFile(txtFile);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.getByText(/unsupported file type/i)).toBeInTheDocument();
    expect(mockedUpload).not.toHaveBeenCalled();
  });

  it("shows an error banner when a file exceeds 5 MB", async () => {
    renderPage();
    await waitFor(() => screen.getByText(/no resumes yet/i));

    const bigContent = new Uint8Array(6 * 1024 * 1024); // 6 MB
    const bigFile = new File([bigContent], "huge.pdf", { type: "application/pdf" });
    selectFile(bigFile);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.getByText(/5 mb/i)).toBeInTheDocument();
    expect(mockedUpload).not.toHaveBeenCalled();
  });

  it("shows an error banner for an empty file", async () => {
    renderPage();
    await waitFor(() => screen.getByText(/no resumes yet/i));

    const emptyFile = new File([], "empty.pdf", { type: "application/pdf" });
    selectFile(emptyFile);

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.getByText(/empty/i)).toBeInTheDocument();
    expect(mockedUpload).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Tests: successful upload
// ---------------------------------------------------------------------------

describe("ResumesPage — successful upload", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls resumeApi.upload with the selected file", async () => {
    mockedList.mockResolvedValue([]);
    mockedUpload.mockResolvedValue(makeResumeResponse());

    renderPage();
    await waitFor(() => screen.getByText(/no resumes yet/i));

    const file = makePdfFile("my_cv.pdf");
    selectFile(file);

    await waitFor(() => {
      expect(mockedUpload).toHaveBeenCalledWith(file, expect.any(Function));
    });
  });

  it("shows a success banner after upload completes", async () => {
    mockedList.mockResolvedValue([]);
    mockedUpload.mockResolvedValue(makeResumeResponse());

    renderPage();
    await waitFor(() => screen.getByText(/no resumes yet/i));

    selectFile(makePdfFile("my_cv.pdf"));

    await waitFor(() => {
      expect(screen.getByText(/uploaded successfully/i)).toBeInTheDocument();
    });
  });

  it("refreshes the resume list after a successful upload", async () => {
    const resume = makeResumeResponse({ file_name: "newly_uploaded.pdf" });
    mockedList
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([resume]);
    mockedUpload.mockResolvedValue(resume);

    renderPage();
    await waitFor(() => screen.getByText(/no resumes yet/i));

    selectFile(makePdfFile());

    await waitFor(() => {
      expect(screen.getByText("newly_uploaded.pdf")).toBeInTheDocument();
    });
    expect(mockedList).toHaveBeenCalledTimes(2);
  });

  it("does NOT expose content_text in the success banner", async () => {
    mockedList.mockResolvedValue([]);
    mockedUpload.mockResolvedValue({
      ...makeResumeResponse(),
      content_text: "SUPER SECRET RESUME CONTENT",
    } as never);

    renderPage();
    await waitFor(() => screen.getByText(/no resumes yet/i));

    selectFile(makePdfFile());

    await waitFor(() => screen.getByText(/uploaded successfully/i));

    expect(screen.queryByText(/super secret resume content/i)).not.toBeInTheDocument();
  });

  it("re-enables the upload button after a successful upload", async () => {
    mockedList.mockResolvedValue([]);
    mockedUpload.mockResolvedValue(makeResumeResponse());

    renderPage();
    await waitFor(() => screen.getByText(/no resumes yet/i));

    const btn = screen.getByRole("button", { name: /upload resume/i });
    selectFile(makePdfFile());

    await waitFor(() => {
      expect(btn).not.toBeDisabled();
    });
  });
});

// ---------------------------------------------------------------------------
// Tests: failed upload (server-side errors)
// ---------------------------------------------------------------------------

describe("ResumesPage — server-side upload errors", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedList.mockResolvedValue([]);
  });

  it("shows an error banner when the upload API call throws", async () => {
    mockedUpload.mockRejectedValue(
      new Error("File content does not match the declared type 'pdf'.")
    );

    renderPage();
    await waitFor(() => screen.getByText(/no resumes yet/i));

    selectFile(makePdfFile());

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
    expect(screen.getByText(/file content does not match/i)).toBeInTheDocument();
  });

  it("shows 'Upload failed' heading in the error banner", async () => {
    mockedUpload.mockRejectedValue(new Error("Server error"));

    renderPage();
    await waitFor(() => screen.getByText(/no resumes yet/i));

    selectFile(makePdfFile());

    await waitFor(() => {
      expect(screen.getByText(/upload failed/i)).toBeInTheDocument();
    });
  });

  it("re-enables the upload button after a failed upload", async () => {
    mockedUpload.mockRejectedValue(new Error("Server error"));

    renderPage();
    await waitFor(() => screen.getByText(/no resumes yet/i));

    const btn = screen.getByRole("button", { name: /upload resume/i });
    selectFile(makePdfFile());

    await waitFor(() => {
      expect(btn).not.toBeDisabled();
    });
  });
});

// ---------------------------------------------------------------------------
// Tests: banner dismissal
// ---------------------------------------------------------------------------

describe("ResumesPage — banner dismissal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockedList.mockResolvedValue([]);
  });

  it("dismisses the success banner when X is clicked", async () => {
    mockedUpload.mockResolvedValue(makeResumeResponse());

    renderPage();
    await waitFor(() => screen.getByText(/no resumes yet/i));

    selectFile(makePdfFile());

    await waitFor(() => screen.getByText(/uploaded successfully/i));

    await userEvent.click(screen.getByRole("button", { name: /dismiss/i }));

    await waitFor(() => {
      expect(screen.queryByText(/uploaded successfully/i)).not.toBeInTheDocument();
    });
  });

  it("dismisses the error banner when X is clicked", async () => {
    const txtFile = new File(["text"], "notes.txt", { type: "text/plain" });

    renderPage();
    await waitFor(() => screen.getByText(/no resumes yet/i));

    selectFile(txtFile);

    await waitFor(() => screen.getByRole("alert"));

    await userEvent.click(screen.getByRole("button", { name: /dismiss/i }));

    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
  });
});
