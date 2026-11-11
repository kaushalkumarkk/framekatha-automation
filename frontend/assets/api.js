export async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : data.detail?.code || "Please check the fields and try again.";
    const error = new Error(detail);
    error.status = response.status;
    if (response.status === 401 && path !== "/auth/session")
      window.dispatchEvent(new Event("session-expired"));
    throw error;
  }
  return response.status === 204 ? null : response.json();
}
export const post = (path, body = {}) =>
  api(path, { method: "POST", body: JSON.stringify(body) });
export const patch = (path, body) =>
  api(path, { method: "PATCH", body: JSON.stringify(body) });
export const escape = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
export const money = (amount, currency = "INR") => {
  try {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(Number(amount));
  } catch {
    return `${currency} ${amount}`;
  }
};
export const date = (value, full = false) =>
  value
    ? new Intl.DateTimeFormat("en-IN", {
        day: "numeric",
        month: "short",
        ...(full ? { year: "numeric" } : {}),
        timeZone: "Asia/Kolkata",
      }).format(
        new Date(value.includes("T") ? value : `${value}T00:00:00+05:30`),
      )
    : "Not scheduled";
export const human = (value) => String(value ?? "").replaceAll("_", " ");
