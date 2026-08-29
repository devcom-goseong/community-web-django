/* =============================================================================
   KDU Developer Community — site behaviour
   The only two things the site needs JavaScript for: the mobile menu and the
   copyright year. Every page works without it.
   ========================================================================== */

(function () {
  "use strict";

  /* --- Mobile menu -------------------------------------------------------- */
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("site-nav");
  var mobile = window.matchMedia("(max-width: 56rem)");

  function setOpen(open) {
    nav.setAttribute("data-open", open ? "true" : "false");
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.classList.toggle("menu-open", open);
  }

  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      setOpen(nav.getAttribute("data-open") !== "true");
    });

    // Following a link closes the panel (same-page anchors included).
    nav.addEventListener("click", function (event) {
      if (event.target.closest("a")) setOpen(false);
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && nav.getAttribute("data-open") === "true") {
        setOpen(false);
        toggle.focus();
      }
    });

    // Resizing past the breakpoint must not leave the body scroll-locked.
    var onBreakpoint = function (event) {
      if (!event.matches) setOpen(false);
    };

    if (typeof mobile.addEventListener === "function") {
      mobile.addEventListener("change", onBreakpoint);
    } else if (typeof mobile.addListener === "function") {
      mobile.addListener(onBreakpoint);
    }
  }

  /* --- Copyright year ----------------------------------------------------- */
  var year = String(new Date().getFullYear());
  var slots = document.querySelectorAll("[data-current-year]");
  for (var i = 0; i < slots.length; i++) slots[i].textContent = year;
})();
