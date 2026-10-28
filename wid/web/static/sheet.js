// Sends the sheet to the game and shows the sheet it sends back. Every button in the sheet is
// a plain form button whose formaction names the game action, so this script only posts the
// form and swaps the reply in. The HX-Request header is what the server's safety check expects
// (see wid/web/app.py): pages from other sites cannot add it.

const sheet = () => document.getElementById("sheet");

// Whether the player typed since the last reply: the game has not seen that text yet.
let typed = false;
// Whether a request is waiting for its reply. Anything sent meanwhile is dropped, so a double
// click rolls once.
let pending = false;
// Whether the player changed a box or typed while waiting. The reply redraws the sheet and undoes
// that, so the player is told to make it again rather than left wondering where it went.
let missed = false;
const MISSED = "A change made while wid was busy was not kept; make it again.";

const feedback = (text) => { sheet().querySelector(".feedback").textContent = text; };

async function send(url, data) {
  if (pending) return;
  pending = true;
  let response, text;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: { "HX-Request": "true", "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams(data),
    });
    text = await response.text();
  } catch {
    // A failed fetch means nothing answered: the window running wid --web was closed.
    feedback("wid is not running; start it again and reload this page.");
    missed = false;
    return;
  } finally {
    pending = false;
  }
  if (response.ok) swap(text);
  else feedback(text);
  if (missed) {
    missed = false;
    feedback(`${sheet().querySelector(".feedback").textContent} ${MISSED}`.trim());
  }
}

// Replace the sheet, then put the focus back on the same control so typing and keyboard play
// carry on where they were.
function swap(html) {
  const active = document.activeElement;
  const name = active && active.getAttribute("name");
  // Only buttons and boxes need their value to tell them apart. A text field's value attribute
  // is the text the server last drew, so it no longer matches once the player has typed.
  const keyed = active && ["button", "submit", "radio", "checkbox"].includes(active.type);
  const value = keyed ? active.getAttribute("value") : null;
  sheet().outerHTML = html;
  typed = false;
  // A question from the game (replace a file, discard a game) opens as a modal dialog.
  const ask = sheet().querySelector("dialog[data-ask]");
  if (ask) {
    // Cancel or Escape removes it, so its carried fields (such as an upload) are not sent along
    // with every later action.
    ask.addEventListener("close", () => ask.remove());
    ask.showModal();
    return;
  }
  if (!name) return;
  // A value can hold what the player typed, quotes included, so the selector is escaped.
  const field = `[name="${CSS.escape(name)}"]`;
  const selector = value === null ? field : `${field}[value="${CSS.escape(value)}"]`;
  const again = sheet().querySelector(selector);
  if (again) again.focus({ preventScroll: true });
}

document.addEventListener("submit", (event) => {
  if (event.target !== sheet()) return;
  event.preventDefault();
  const button = event.submitter;
  send(button ? button.formAction : event.target.action, new FormData(event.target, button));
});

// A save chosen in the upload box is read here and sent as text with the sheet, so the game
// needs no file upload handling. The box has no name, so the file itself is not sent.
async function upload(file) {
  const data = new FormData(sheet());
  data.set("session-file", await file.text());
  send("/actions/upload", data);
}

// Selects and boxes marked data-action send the sheet as soon as they change.
document.addEventListener("change", (event) => {
  const control = event.target;
  const file = control.dataset.upload !== undefined ? control.files[0] : undefined;
  if (!file && (!control.dataset.action || !sheet().contains(control))) return;
  if (pending) {
    missed = true;
    return;
  }
  if (file) {
    upload(file);
    return;
  }
  const data = new FormData(sheet());
  if (control.dataset.index !== undefined) data.set("index", control.dataset.index);
  if (control.type === "checkbox" && control.checked) data.set("marked", "1");
  send(`/actions/${control.dataset.action}`, data);
});

document.addEventListener("input", (event) => {
  if (!sheet().contains(event.target)) return;
  typed = true;
  if (pending) missed = true;
});

// Closing or reloading the page asks first while something would be lost, as Ctrl+Q does in
// the terminal.
window.addEventListener("beforeunload", (event) => {
  if (sheet().dataset.unsaved === undefined && !typed) return;
  event.preventDefault();
  event.returnValue = "";
});

document.addEventListener("keydown", (event) => {
  // Enter in a text field would press the form's first button (a Roll button once the game
  // has started); it only sends what was typed instead.
  if (event.key === "Enter" && event.target.tagName === "INPUT" && sheet().contains(event.target)) {
    event.preventDefault();
    sheet().requestSubmit();
    return;
  }
  // Ctrl+R repeats the last roll, as in the terminal, instead of reloading the page.
  if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "r") return;
  event.preventDefault();
  // While the game asks a question, the answer comes first, as in the terminal.
  if (sheet().querySelector("dialog[open]")) return;
  const repeat = sheet().querySelector('button[formaction="/actions/roll"]:not([name])');
  if (repeat && !repeat.disabled) sheet().requestSubmit(repeat);
});

// The notes buttons, with the terminal's rules: wrap the selection (or a placeholder) in ** or
// *, or start each selected line with "# ".
const FORMATS = {
  bold: (text) => `**${text || "bold text"}**`,
  italic: (text) => `*${text || "italic text"}*`,
};

function heading(notes) {
  const { value, selectionStart, selectionEnd } = notes;
  const start = value.lastIndexOf("\n", selectionStart - 1) + 1;
  // A selection that ends at the start of a line does not take that line along.
  const end = selectionEnd > selectionStart && value[selectionEnd - 1] === "\n"
    ? selectionEnd - 1 : selectionEnd;
  const stop = value.indexOf("\n", end) === -1 ? value.length : value.indexOf("\n", end);
  notes.setSelectionRange(start, stop);
  return value.slice(start, stop).split("\n").map((line) => `# ${line}`).join("\n");
}

// The colours switch: Auto (the browser's setting), then the opposite of that setting, then the
// same as it, then Auto again, so the first click always changes what shows. The choice is
// remembered in this browser only.
function toggleTheme() {
  const root = document.documentElement;
  const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const order = ["auto", systemDark ? "light" : "dark", systemDark ? "dark" : "light"];
  const next = order[(order.indexOf(root.dataset.theme || "auto") + 1) % order.length];
  try {
    if (next === "auto") localStorage.removeItem("wid-theme");
    else localStorage.setItem("wid-theme", next);
  } catch {
    // Storage can be blocked; the switch still holds until the page is reloaded.
  }
  if (next === "auto") delete root.dataset.theme;
  else root.dataset.theme = next;
}

// Copy result: the result as text, which the sheet carries on the button.
async function copyResult(button) {
  try {
    await navigator.clipboard.writeText(button.dataset.copy);
    feedback("Copied the result.");
  } catch {
    feedback("The browser did not let wid copy; select the result and copy it instead.");
  }
}

document.addEventListener("click", (event) => {
  if (event.target.closest("[data-theme-toggle]")) toggleTheme();
  const copy = event.target.closest("[data-copy]");
  if (copy) copyResult(copy);
  const close = event.target.closest("[data-close]");
  if (close) close.closest("dialog").close();
  const button = event.target.closest("[data-format]");
  if (!button) return;
  const notes = sheet().elements.notes;
  const format = button.dataset.format;
  const selected = notes.value.slice(notes.selectionStart, notes.selectionEnd);
  const replacement = format === "heading" ? heading(notes) : FORMATS[format](selected);
  notes.focus();
  // insertText keeps the change in the browser's undo history; setRangeText is the fallback.
  if (!document.execCommand("insertText", false, replacement)) {
    notes.setRangeText(replacement, notes.selectionStart, notes.selectionEnd, "end");
  }
});
