"use strict";
const form = document.getElementById("login-form");
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = form.querySelector("button");
  const error = document.getElementById("login-error");
  button.disabled = true;
  error.textContent = "Anmeldung wird geprüft …";
  try {
    const values = new FormData(form);
    const response = await fetch("/internal/login", {
      method: "POST", credentials: "same-origin", cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: values.get("email"), password: values.get("password"), csrf: values.get("csrf") }),
    });
    form.elements.password.value = "";
    if (!response.ok) throw new Error(response.status === 429 ? "Zu viele Versuche. Bitte eine Minute warten." : "Anmeldung nicht möglich. Zugang prüfen.");
    window.location.assign("/internal/jarvis");
  } catch (failure) {
    form.elements.password.value = "";
    error.textContent = failure.message;
    button.disabled = false;
  }
});
