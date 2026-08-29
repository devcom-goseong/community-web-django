/* =============================================================================
   KDU Developer Community — join / contact form
   Submits to the Netlify function with fetch() and reports the result inline.
   If JavaScript is unavailable the form still posts normally and the function
   answers with a plain confirmation page, so nothing is lost.
   ========================================================================== */

(function () {
  "use strict";

  var ENDPOINT = "/api/register";
  var EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

  var form = document.getElementById("join-form");
  if (!form) return;

  var statusBox = document.getElementById("form-status");
  var statusMark = document.getElementById("status-mark");
  var statusTitle = document.getElementById("status-title");
  var statusText = document.getElementById("status-text");
  var button = document.getElementById("submit");
  var stamp = document.getElementById("ts");

  // Records when the page was ready. The function rejects submissions that
  // arrive impossibly fast, which is most of what automated spam looks like.
  if (stamp) stamp.value = String(Date.now());

  var VALIDATED = ["name", "email", "message", "agree", "consent"];

  function fieldEl(name) {
    return form.querySelector('[data-field="' + name + '"]');
  }

  function setInvalid(name, invalid) {
    var wrapper = fieldEl(name);
    if (!wrapper) return;
    wrapper.setAttribute("data-invalid", invalid ? "true" : "false");
    var control = wrapper.querySelector("input, textarea");
    if (control) {
      if (invalid) control.setAttribute("aria-invalid", "true");
      else control.removeAttribute("aria-invalid");
    }
  }

  function clearInvalid() {
    VALIDATED.forEach(function (name) { setInvalid(name, false); });
  }

  function report(state, title, text) {
    statusBox.setAttribute("data-state", state);
    statusMark.textContent = state === "success" ? "OK" : "!";
    statusTitle.textContent = title;
    statusText.textContent = text;
  }

  function focusFirst(names) {
    var wrapper = fieldEl(names[0]);
    if (!wrapper) return;
    var control = wrapper.querySelector("input, textarea");
    if (control && typeof control.focus === "function") control.focus();
  }

  function collect() {
    var data = new FormData(form);
    return {
      intent: data.get("intent") || "join",
      name: (data.get("name") || "").toString().trim(),
      email: (data.get("email") || "").toString().trim(),
      student: (data.get("student") || "").toString(),
      studentId: (data.get("studentId") || "").toString().trim(),
      interests: data.getAll("interests"),
      agree: data.get("agree") ? "yes" : "",
      message: (data.get("message") || "").toString().trim(),
      consent: data.get("consent") ? "yes" : "",
      website: (data.get("website") || "").toString(),
      ts: (data.get("ts") || "0").toString()
    };
  }

  function validate(payload) {
    var problems = [];
    if (!payload.name) problems.push("name");
    if (!EMAIL_PATTERN.test(payload.email)) problems.push("email");
    if (!payload.agree) problems.push("agree");
    if (!payload.consent) problems.push("consent");
    if (payload.intent === "question" && !payload.message) problems.push("message");
    return problems;
  }

  function busy(isBusy) {
    button.setAttribute("data-busy", isBusy ? "true" : "false");
    if (isBusy) button.setAttribute("disabled", "disabled");
    else button.removeAttribute("disabled");
  }

  // Clear a field's error state as soon as the person starts fixing it.
  VALIDATED.forEach(function (name) {
    var wrapper = fieldEl(name);
    if (!wrapper) return;
    wrapper.addEventListener("input", function () { setInvalid(name, false); });
    wrapper.addEventListener("change", function () { setInvalid(name, false); });
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();

    var payload = collect();
    clearInvalid();

    var problems = validate(payload);
    if (problems.length) {
      problems.forEach(function (name) { setInvalid(name, true); });
      report(
        "error",
        "Some details are missing",
        "Check the fields marked below and send it again."
      );
      focusFirst(problems);
      return;
    }

    busy(true);
    report("idle", "", "");

    fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(payload)
    })
      .then(function (response) {
        return response.json()
          .catch(function () { return {}; })
          .then(function (body) { return { status: response.status, body: body }; });
      })
      .then(function (result) {
        busy(false);

        if (result.status >= 200 && result.status < 300 && result.body.ok) {
          form.classList.add("is-sent");
          report(
            "success",
            payload.intent === "question"
              ? "Your message is on its way"
              : "Thanks — your application is in",
            "A confirmation email is on its way to " + payload.email +
              ". Someone on the founding team will read what you wrote and reply to you directly."
          );
          statusBox.setAttribute("tabindex", "-1");
          statusBox.focus();
          return;
        }

        if (result.body && Array.isArray(result.body.fields) && result.body.fields.length) {
          result.body.fields.forEach(function (name) { setInvalid(name, true); });
          focusFirst(result.body.fields);
        }

        report(
          "error",
          "That did not go through",
          (result.body && result.body.message) ||
            "Something went wrong at our end. Please try again in a moment."
        );
      })
      .catch(function () {
        busy(false);
        report(
          "error",
          "We could not reach the server",
          "Check your connection and try again. If it keeps failing, the site may be " +
            "mid-deploy — give it a few minutes."
        );
      });
  });
})();
