// Sends the sheet to the game and shows the sheet it sends back. Every button in the sheet is
// a plain form button whose formaction names the game action, so this script only posts the
// form and swaps the reply in. The HX-Request header is what the server's safety check expects
// (see wid/web/app.py): pages from other sites cannot add it.

const sheet = () => document.getElementById("sheet");

async function send(url, data) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "HX-Request": "true", "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(data),
  });
  const text = await response.text();
  if (!response.ok) {
    sheet().querySelector(".feedback").textContent = text;
    return;
  }
  swap(text);
}

// Replace the sheet, then put the focus back on the same control so typing and keyboard play
// carry on where they were.
function swap(html) {
  const active = document.activeElement;
  const name = active && active.getAttribute("name");
  const value = active && active.getAttribute("value");
  sheet().outerHTML = html;
  // A question from the game (replace a file, discard a game) opens as a modal dialog.
  const ask = sheet().querySelector("dialog[data-ask]");
  if (ask) {
    ask.showModal();
    return;
  }
  if (!name) return;
  const selector = value === null ? `[name="${name}"]` : `[name="${name}"][value="${value}"]`;
  const again = sheet().querySelector(selector);
  if (again) again.focus({ preventScroll: true });
}

document.addEventListener("submit", (event) => {
  if (event.target !== sheet()) return;
  event.preventDefault();
  const button = event.submitter;
  send(button ? button.formAction : event.target.action, new FormData(event.target, button));
});

// Selects and boxes marked data-action send the sheet as soon as they change.
document.addEventListener("change", (event) => {
  const control = event.target;
  if (!control.dataset.action || !sheet().contains(control)) return;
  const data = new FormData(sheet());
  if (control.dataset.index !== undefined) data.set("index", control.dataset.index);
  if (control.type === "checkbox" && control.checked) data.set("marked", "1");
  send(`/actions/${control.dataset.action}`, data);
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

document.addEventListener("click", (event) => {
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
