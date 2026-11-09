// Copy-to-clipboard for any button with data-copy="<text>".
// Delegated on document so it also works on htmx-swapped content.
(function () {
  function legacyCopy(text) {
    var ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }

  function selectText(id) {
    var el = id && document.getElementById(id);
    if (!el || !window.getSelection) return;
    var range = document.createRange();
    range.selectNodeContents(el);
    var sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
  }

  function report(btn, ok) {
    var card = btn.closest(".result") || document;
    var status = card.querySelector(".copy-status");
    var label = btn.getAttribute("data-label") || btn.textContent;
    btn.setAttribute("data-label", label);
    if (ok) {
      btn.textContent = "Copied ✓";
      if (status) status.textContent = "Membership No copied. Now open the voting page and paste it.";
      setTimeout(function () { btn.textContent = label; }, 2500);
    } else {
      selectText(btn.getAttribute("data-copy-target"));
      if (status) status.textContent = "Couldn't copy automatically. The number is selected: long-press or use Ctrl+C to copy it.";
    }
  }

  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest && ev.target.closest("[data-copy]");
    if (!btn) return;
    var text = btn.getAttribute("data-copy");
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(
        function () { report(btn, true); },
        function () { report(btn, legacyCopy(text)); }
      );
    } else {
      report(btn, legacyCopy(text));
    }
  });
})();
