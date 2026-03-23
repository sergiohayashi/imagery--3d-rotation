// src/features/chat/export.ts
export async function downloadChatExport(
    projectId,
    startIso,
    endIso,
    token
) {
    const url = new URL(`/api/projects/${projectId}/chat-export`, window.location.origin);
    url.searchParams.set("start", startIso);
    url.searchParams.set("end", endIso);

    const response = await fetch(url.toString(), {
        method: "GET",
        headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/zip",
        },
    });

    if (!response.ok) {
        const problem = await response.json().catch(() => null);
        throw new Error(problem?.detail || "Unable to export chats.");
    }

    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);

    const anchor = document.createElement("a");
    anchor.href = downloadUrl;

    // Try to read filename from header; fallback to a default
    const disposition = response.headers.get("Content-Disposition");
    const match = disposition?.match(/filename="?([^"]+)"?/);
    anchor.download = match?.[1] ?? "chat-export.zip";

    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    window.URL.revokeObjectURL(downloadUrl);
}
